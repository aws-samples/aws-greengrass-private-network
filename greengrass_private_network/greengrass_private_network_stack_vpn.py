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

# transit gateway and VPN configuration borrowed from this blog:
# https://aws.amazon.com/blogs/networking-and-content-delivery/simulating-site-to-site-vpn-customer-gateways-strongswan/


class GreengrassPrivateNetworkStackVPN(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        gg_vpc = ec2.Vpc(
            self,
            "GreengrassPrivateNetwork",
            cidr="172.16.1.0/24",
            subnet_configuration=[
                # ec2.SubnetConfiguration(
                #    subnet_type=ec2.SubnetType.PUBLIC,
                #    name="Public",
                # ),
                ec2.SubnetConfiguration(
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                    name="Private Isolated Cloud Subnet",
                ),
            ],
            max_azs=2,
        )

        gg_vpc.add_flow_log("GreengrassPrivateVpcFlowLog")

        endpoints_sg = ec2.SecurityGroup(
            self,
            "endpoints-security-group",
            vpc=gg_vpc,
            description="Securing the endpoints used to create private connection with Greengrass",
            allow_all_outbound=True,
        )

        ######################## REMOTE VPC SIDE,  FOR GREENGRASS RUNTIME #######################

        remote_vpc = ec2.Vpc(
            self,
            "RemoteSiteVPC",
            cidr="172.16.0.0/24",
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    subnet_type=ec2.SubnetType.PUBLIC, name="Remote DMZ"
                ),
                ec2.SubnetConfiguration(
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_NAT,
                    name=" Remote Secure Zone",
                ),
            ],
        )

        remote_endpoints_sg = ec2.SecurityGroup(
            self,
            "remote-endpoints-security-group",
            vpc=remote_vpc,
            description="Not applicable in a real world remote environment, for SSM to manage demo instances",
            allow_all_outbound=True,
        )

        #########################################################################################

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

        greengrass_endpoint = gg_vpc.add_interface_endpoint(
            "GreengrassEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService("greengrass", port=443),
            private_dns_enabled=True,
            security_groups=[endpoints_sg],
            lookup_supported_azs=True,
        )

        s3_endpoint = gg_vpc.add_interface_endpoint(
            "S3Endpoint",
            service=ec2.InterfaceVpcEndpointAwsService("s3", port=443),
            private_dns_enabled=False,
            security_groups=[endpoints_sg],
            lookup_supported_azs=True,
        )

        logs_endpoint = gg_vpc.add_interface_endpoint(
            "LogsEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService("logs", port=443),
            private_dns_enabled=True,
            security_groups=[cloudwatch_endpoints_sg],
            lookup_supported_azs=True,
        )

        ssm_endpoint = remote_vpc.add_interface_endpoint(
            "SsmEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService("ssm", port=443),
            private_dns_enabled=True,
            security_groups=[remote_endpoints_sg],
        )

        ssm_messages_endpoint = remote_vpc.add_interface_endpoint(
            "SsmMessagesEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService("ssmmessages", port=443),
            private_dns_enabled=True,
            security_groups=[remote_endpoints_sg],
        )

        ec2_messages_endpoint = remote_vpc.add_interface_endpoint(
            "Ec2MessagesEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService("ec2messages", port=443),
            private_dns_enabled=True,
            security_groups=[remote_endpoints_sg],
        )

        # this doesn't work - certificate not valid. You have to get group.json over NAT
        # s3_w_endpoint_uri = "s3-w.{}.amazonaws.com".format(Stack.of(self).region)

        # s3_w_hosted_zone = route53.HostedZone(
        #     self,
        #     "s3-wHostedZone",
        #     zone_name=s3_w_endpoint_uri,
        #     vpcs=[gg_vpc, remote_vpc],
        # )

        s3_endpoint_uri = "s3.{}.amazonaws.com".format(Stack.of(self).region)

        s3_hosted_zone = route53.HostedZone(
            self,
            "S3HostedZone",
            zone_name=s3_endpoint_uri,
            vpcs=[gg_vpc, remote_vpc],
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
            "IotDataHostedZone",
            zone_name="iot.{}.amazonaws.com".format(Stack.of(self).region),
            vpcs=[gg_vpc, remote_vpc],
        )

        iot_client = boto3.client("iot", Stack.of(self).region)
        iot_endpoint = iot_client.describe_endpoint(endpointType="iot:Data-ATS")
        iot_endpoint_address = iot_endpoint["endpointAddress"]

        route53.ARecord(
            self,
            "IotCoreRecord",
            zone=hosted_zone,
            target=route53.RecordTarget.from_alias(
                targets.InterfaceVpcEndpointTarget(iot_core_endpoint)
            ),
            record_name=iot_endpoint_address,
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
            ec2.Peer.any_ipv4(),
            ec2.Port.tcp(8883),
            "Greengrass secure MQTT to IoT core",
        )

        # PEERS should be updated to CIDR of remote VPC

        endpoints_sg.add_ingress_rule(
            ec2.Peer.any_ipv4(), ec2.Port.tcp(8443), "Secure MQTT to iot core endpoint"
        )
        endpoints_sg.add_ingress_rule(
            ec2.Peer.any_ipv4(), ec2.Port.tcp(443), "HTTPS to S3"
        )

        cloudwatch_endpoints_sg.add_ingress_rule(
            ec2.Peer.any_ipv4(), ec2.Port.tcp(443), "logging from Greengrass"
        )

        # to test basic VPN connectivity between subnets

        tgw = ec2.CfnTransitGateway(
            self,
            id="TGW",
            amazon_side_asn=64512,
            dns_support="enable",
            vpn_ecmp_support="enable",
            default_route_table_association="enable",
            default_route_table_propagation="enable",
        )

        ## GREENGRASS HOST

        amzn_linux = ec2.MachineImage.latest_amazon_linux(
            generation=ec2.AmazonLinuxGeneration.AMAZON_LINUX_2,
            edition=ec2.AmazonLinuxEdition.STANDARD,
            cpu_type=ec2.AmazonLinuxCpuType.ARM_64,
        )

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
                        "s3:Put*",
                        "s3:CreateMultipartUpload",
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

        # This only allows MQTT from cloud, it doesn't account for internal network
        peer = ec2.Peer.ipv4(gg_vpc.vpc_cidr_block)

        greengrass_sg = ec2.SecurityGroup(
            self,
            "greengrass-runtime-security-group",
            vpc=remote_vpc,
            description="Securing the Greengrass runtime",
            allow_all_outbound=True,
        )
        greengrass_sg.add_ingress_rule(
            peer, ec2.Port.tcp(8883), "Allow incoming MQTT from other devices"
        )

        with open("./user_data/userdata.sh") as f:
            USER_DATA = f.read()

        greengrass_instance = ec2.Instance(
            self,
            "Greengrass Instance",
            vpc=remote_vpc,
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

        eip = ec2.CfnEIP(
            self,
            "remoteEIP",
        )

        customer_gateway = ec2.CfnCustomerGateway(
            self,
            "CustomerGateway",
            bgp_asn=65000,
            ip_address=eip.ref,
            type="ipsec.1",
        )

        vpn = ec2.CfnVPNConnection(
            self,
            "SiteToSiteVPN",
            customer_gateway_id=customer_gateway.attr_customer_gateway_id,
            static_routes_only=False,
            transit_gateway_id=tgw.attr_id,
            type="ipsec.1",
        )

        tgw_attachment = ec2.CfnTransitGatewayAttachment(
            self,
            "Tgw2Cloud",
            vpc_id=gg_vpc.vpc_id,
            transit_gateway_id=tgw.attr_id,
            subnet_ids=[subnet.subnet_id for subnet in gg_vpc.isolated_subnets],
        )
        tgw_attachment.add_depends_on(tgw)

        # this fails first run, depends on doesn't work. maybe need to expose tgw id to a dependent stack - haven't tried it yet
        # need to report as an issue to CDK, potentially solve with a custom resource.
        # UGLY HACK: For now deploy twice and uncomment on 2nd run
        for subnet in gg_vpc.isolated_subnets:
            subnet.add_route(
                "VpnVpcRoute",
                router_id=tgw.attr_id,
                router_type=ec2.RouterType.TRANSIT_GATEWAY,
                destination_cidr_block=remote_vpc.vpc_cidr_block,
            )

        cdk.CfnOutput(
            self, "Greengrass Ec2 Instance:", value=greengrass_instance.instance_id
        )
        cdk.CfnOutput(self, "Remote Vpc CIDR Block:", value=remote_vpc.vpc_cidr_block)
        cdk.CfnOutput(self, "remoteEip Allocation ID", value=eip.attr_allocation_id)
        cdk.CfnOutput(self, "IoT Data Endpoint: ", value=iot_endpoint_address)


# ToDo - create secrets manager secrets for PSKs
# ToDo - print out BGP ASN
