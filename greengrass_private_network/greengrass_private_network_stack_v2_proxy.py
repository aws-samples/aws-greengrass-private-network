# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0


from os import stat
from constructs import Construct
import boto3
import aws_cdk as cdk
from aws_cdk import (
    aws_ec2 as ec2,
    Stack,
    aws_route53 as route53,
    aws_route53_targets as targets,
    aws_iam as iam,
)


class GreengrassPrivateNetworkStackV2Proxy(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        gg_vpc = ec2.Vpc(
            self,
            "GreengrassPrivateNetwork",
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    subnet_type=ec2.SubnetType.PUBLIC,
                    name="Public",
                ),
                ec2.SubnetConfiguration(
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_NAT,
                    name="Private Greengrass traffic VPC",
                ),
            ],
            max_azs=2,
        )

        gg_vpc.add_flow_log("GreengrassPrivateVpcFlowLog")

        amzn_linux = ec2.MachineImage.latest_amazon_linux(
            generation=ec2.AmazonLinuxGeneration.AMAZON_LINUX_2,
            edition=ec2.AmazonLinuxEdition.STANDARD,
            cpu_type=ec2.AmazonLinuxCpuType.ARM_64,
        )

        # ToDo: Pair down the permissions on this instance profile,
        # you should not need much outside of SSM and logging

        ec2_role = iam.Role(
            self, "InstanceSSM", assumed_by=iam.ServicePrincipal("ec2.amazonaws.com")
        )

        ec2_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "AmazonSSMManagedInstanceCore"
            )
        )
        iam.Policy(
            self,
            "AllowsGreengrassToRequiredArtifacts",
            roles=[ec2_role],
            policy_name="AllowsGreengrassToRequiredArtifacts",
            statements=[
                iam.PolicyStatement(
                    actions=[
                        "s3:Get*",
                        "s3:List*",
                        "s3-object-lambda:Get*",
                        "s3-object-lambda:List*",
                    ],
                    effect=iam.Effect.ALLOW,
                    resources=[
                        "arn:aws:s3:::{}-greengrass-updates".format(
                            Stack.of(self).region
                        ),
                        "arn:aws:s3:::{}-greengrass-updates/*".format(
                            Stack.of(self).region
                        ),
                        "arn:aws:s3:::prod-{}-gg-deployment-agent".format(
                            Stack.of(self).region
                        ),
                        "arn:aws:s3:::prod-{}-gg-deployment-agent/*".format(
                            Stack.of(self).region
                        ),
                        "arn:aws:s3:::prod-04-2014-tasks",
                        "arn:aws:s3:::prod-04-2014-tasks/*",
                        # customer manged bucket for GG deploy resources, update the naming accordingly
                        "arn:aws:s3:::greengrass-setup-*",
                        "arn:aws:s3:::greengrass-setup-*/*",
                    ],
                )
            ],
        )

        iam.Policy(
            self,
            "AllowGreengrassDeviceLogging",
            roles=[ec2_role],
            policy_name="AllowGreengrassDeviceLogging",
            statements=[
                iam.PolicyStatement(
                    actions=[
                        "logs:CreateLogGroup",
                        "logs:CreateLogStream",
                        "logs:PutLogEvents",
                        "logs:DescribeLogStreams",
                    ],
                    effect=iam.Effect.ALLOW,
                    resources=[
                        "arn:aws:logs:{}:{}:/aws/greengrass/*".format(
                            Stack.of(self).region, Stack.of(self).account
                        )
                    ],
                )
            ],
        )

        peer = ec2.Peer.ipv4(gg_vpc.vpc_cidr_block)

        greengrass_sg = ec2.SecurityGroup(
            self,
            "greengrass-runtime-security-group",
            vpc=gg_vpc,
            description="Securing the Greengrass runtime",
            allow_all_outbound=True,
        )
        greengrass_sg.add_ingress_rule(
            peer, ec2.Port.tcp(8883), "Allow incoming MQTT from other devices"
        )

        with open("./user_data/userdata_v2.sh") as f:
            USER_DATA = f.read()

        greengrass_instance = ec2.Instance(
            self,
            "Greengrass Instance",
            vpc=gg_vpc,
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.BURSTABLE4_GRAVITON, ec2.InstanceSize.MICRO
            ),
            machine_image=amzn_linux,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_NAT,
            ),
            role=ec2_role,
            security_group=greengrass_sg,
            user_data=ec2.UserData.custom(USER_DATA),
            detailed_monitoring=True,
        )

        endpoints_sg = ec2.SecurityGroup(
            self,
            "endpoints-security-group",
            vpc=gg_vpc,
            description="Securing the endpoints used to create private connection with Greengrass",
            allow_all_outbound=True,
        )

        cloudwatch_endpoints_sg = ec2.SecurityGroup(
            self,
            "cloudwatch-endpoints-security-group",
            vpc=gg_vpc,
            description="Securing the endpoints used to create private connection with Greengrass",
            allow_all_outbound=True,
        )

        # endpoint services: https://docs.aws.amazon.com/vpc/latest/privatelink/integrated-services-vpce-list.html

        iot_core_endpoint = gg_vpc.add_interface_endpoint(
            "IotCoreEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService("iot.data", port=443),
            private_dns_enabled=False,
            security_groups=[endpoints_sg],
            lookup_supported_azs=True,
        )
        cdk.Tags.of(iot_core_endpoint).add("Name", "iot-endpoint")

        greengrass_endpoint = gg_vpc.add_interface_endpoint(
            "GreengrassEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService("greengrass", port=443),
            private_dns_enabled=True,
            security_groups=[endpoints_sg],
            lookup_supported_azs=True,
        )
        cdk.Tags.of(greengrass_endpoint).add("Name", "greengrass-endpoint")

        s3_endpoint = gg_vpc.add_interface_endpoint(
            "S3Endpoint",
            service=ec2.InterfaceVpcEndpointAwsService("s3", port=443),
            private_dns_enabled=False,
            security_groups=[endpoints_sg],
            lookup_supported_azs=True,
        )
        cdk.Tags.of(s3_endpoint).add("Name", "s3-endpoint")

        logs_endpoint = gg_vpc.add_interface_endpoint(
            "LogsEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService("logs", port=443),
            private_dns_enabled=True,
            security_groups=[cloudwatch_endpoints_sg],
            lookup_supported_azs=True,
        )
        cdk.Tags.of(logs_endpoint).add("Name", "logs-endpoint")

        ssm_endpoint = gg_vpc.add_interface_endpoint(
            "SsmEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService("ssm", port=443),
            private_dns_enabled=True,
            security_groups=[endpoints_sg],
            lookup_supported_azs=True,
        )
        cdk.Tags.of(ssm_endpoint).add("Name", "ssm-endpoint")

        ssm_messages_endpoint = gg_vpc.add_interface_endpoint(
            "SsmMessagesEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService("ssmmessages", port=443),
            private_dns_enabled=True,
            security_groups=[endpoints_sg],
            lookup_supported_azs=True,
        )
        cdk.Tags.of(ssm_messages_endpoint).add("Name", "ssm-messages-endpoint")

        ec2_messages_endpoint = gg_vpc.add_interface_endpoint(
            "Ec2MessagesEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService("ec2messages", port=443),
            private_dns_enabled=True,
            security_groups=[endpoints_sg],
            lookup_supported_azs=True,
        )
        cdk.Tags.of(ec2_messages_endpoint).add("Name", "ec2-messages-endpoint")

        s3_endpoint_uri = "s3.{}.amazonaws.com".format(Stack.of(self).region)

        s3_hosted_zone = route53.HostedZone(
            self,
            "SeHostedZone",
            zone_name=s3_endpoint_uri,
            vpcs=[gg_vpc],
        )

        route53.ARecord(
            self,
            "S3Record",
            zone=s3_hosted_zone,
            target=route53.RecordTarget.from_alias(
                targets.InterfaceVpcEndpointTarget(s3_endpoint)
            ),
            record_name=s3_endpoint_uri,
        )

        route53.ARecord(
            self,
            "WildcardS3Record",
            zone=s3_hosted_zone,
            target=route53.RecordTarget.from_alias(
                targets.InterfaceVpcEndpointTarget(s3_endpoint)
            ),
            record_name="*." + s3_endpoint_uri,
        )

        hosted_zone = route53.HostedZone(
            self,
            "IotCoreHostedZone",
            zone_name="iot.{}.amazonaws.com".format(Stack.of(self).region),
            vpcs=[gg_vpc],
        )

        iot_client = boto3.client("iot", Stack.of(self).region)
        iot_endpoint_data = iot_client.describe_endpoint(endpointType="iot:Data-ATS")
        iot_endpoint_data_address = iot_endpoint_data["endpointAddress"]
        iot_credentials_endpoint = iot_client.describe_endpoint(
            endpointType="iot:CredentialProvider"
        )

        route53.ARecord(
            self,
            "IotCoreRecord",
            zone=hosted_zone,
            target=route53.RecordTarget.from_alias(
                targets.InterfaceVpcEndpointTarget(iot_core_endpoint)
            ),
            record_name=iot_endpoint_data_address,
        )

        route53.ARecord(
            self,
            "GreengrassRecord",
            zone=hosted_zone,
            target=route53.RecordTarget.from_alias(
                targets.InterfaceVpcEndpointTarget(iot_core_endpoint)
            ),
            record_name="greengrass-ats.iot.{}.amazonaws.com".format(
                Stack.of(self).region
            ),
        )

        endpoints_sg.add_ingress_rule(
            greengrass_sg, ec2.Port.tcp(8883), "Greengrass secure MQTT to IoT core"
        )

        endpoints_sg.add_ingress_rule(
            greengrass_sg, ec2.Port.tcp(8443), "Secure MQTT to iot core endpoint"
        )
        endpoints_sg.add_ingress_rule(greengrass_sg, ec2.Port.tcp(443), "HTTPS to S3")

        cloudwatch_endpoints_sg.add_ingress_rule(
            peer, ec2.Port.tcp(443), "logging from Greengrass"
        )

        cdk.CfnOutput(
            self, "Greengrass Ec2 Instance:", value=greengrass_instance.instance_id
        )

        cdk.CfnOutput(self, "Greengrass Vpc CIDR Block:", value=gg_vpc.vpc_cidr_block)
        cdk.CfnOutput(
            self,
            "IoT CredentialEndpoint:",
            value=iot_credentials_endpoint["endpointAddress"],
        )
        cdk.CfnOutput(
            self,
            "IoT DataEndpoint:",
            value=iot_endpoint_data["endpointAddress"],
        )

        # ToDo - Setup IoT thing, policy, execution role and alias. Have to put the certs somewhere
        # so they can be retrieved and loaded onto the device - probably an S3 bucket or secrets manager.
