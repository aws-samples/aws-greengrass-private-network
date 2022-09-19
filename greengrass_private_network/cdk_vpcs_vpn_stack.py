from aws_cdk import (
    # Duration,
    Stack,
    aws_ec2 as ec2,
)
from constructs import Construct

class CdkVpcsVpnStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        tgw = ec2.CfnTransitGateway(self, id="TGW",
            amazon_side_asn=64512,
            dns_support="enable",
            vpn_ecmp_support="enable",
            default_route_table_association="enable",
            default_route_table_propagation="enable",
        ) 

        remote_vpc = ec2.Vpc(self, "RemoteSiteVPC",
            cidr="172.16.0.0/24",
            subnet_configuration=[ec2.SubnetConfiguration(
                subnet_type=ec2.SubnetType.PUBLIC,
                name="Public"
            ), ec2.SubnetConfiguration(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_NAT,
                name="Isolated",
            )]
        )
        
        remote_security_group = ec2.SecurityGroup(self, "PingRemoteBastion",
            vpc=remote_vpc,
            description="Allow pings",
            allow_all_outbound=True
        )
        remote_security_group.add_ingress_rule(ec2.Peer.ipv4("172.16.0.0/16"), ec2.Port.all_icmp(), "pingable")
        
        remote_host = ec2.BastionHostLinux(self, "RemoteBastionHost",
            vpc=remote_vpc,
            subnet_selection=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_NAT),
            security_group=remote_security_group
        )
        
        
        eip = ec2.CfnEIP(self, "remoteEIP",  )
        
        customer_gateway = ec2.CfnCustomerGateway(self, "CustomerGateway",
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
            type='ipsec.1'
        )
       
        cloud_vpc = ec2.Vpc(self, "PrivateCloudVPC",
            cidr="172.16.1.0/24",
            subnet_configuration=[ec2.SubnetConfiguration(
                subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                name="Isolated"
            )]
        )
        
        #cloud_vpc.node.add_dependency(tgw)
        
        cloud_security_group = ec2.SecurityGroup(self, "PingCloudBastion",
            vpc=cloud_vpc,
            description="Allow pings",
            allow_all_outbound=True
        )
        #ipv4("172.16.0.0/16")
        cloud_security_group.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.all_icmp(), "pingable")
        cloud_security_group.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(22), "allow ssh")
        
        cloud_host = ec2.BastionHostLinux(self, "CloudBastionHost",
            vpc=cloud_vpc,
            subnet_selection=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
            security_group=cloud_security_group
        )
        
        
        tgw_attachment = ec2.CfnTransitGatewayAttachment(self, "Tgw2Cloud",
            vpc_id=cloud_vpc.vpc_id,
            transit_gateway_id=tgw.attr_id,
            subnet_ids=[subnet.subnet_id for subnet in cloud_vpc.isolated_subnets]
        )
        tgw_attachment.add_depends_on(tgw)
        
        
        #this fails first run, depends on doesn't work. maybe need to expose tgw id to a dependent stack - haven't tried it yet
        for subnet in cloud_vpc.isolated_subnets:
            subnet.add_route("VpnVpcRoute",
                router_id=tgw.attr_id,
                router_type=ec2.RouterType.TRANSIT_GATEWAY,
                destination_cidr_block=remote_vpc.vpc_cidr_block
            )

    