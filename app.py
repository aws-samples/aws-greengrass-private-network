#!/usr/bin/env python3

# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import aws_cdk as cdk
import os

from greengrass_private_network.greengrass_private_network_stack import (
    GreengrassPrivateNetworkStack,
)

from greengrass_private_network.greengrass_private_network_stack_vpn import (
    GreengrassPrivateNetworkStackVPN,
)

# Cannot look up VPC endpoint availability zones if account/region are not specified

app = cdk.App()
if "VPN" in os.environ.get("GREENGRASS_MODE"):
    print("Greengrass v1 VPN mode")
    stack = GreengrassPrivateNetworkStackVPN(
        app,
        "greengrass-private-network-vpn",
        env=cdk.Environment(
            account=os.environ.get("CDK_DEPLOY_ACCOUNT"),
            region=os.environ.get("CDK_DEPLOY_REGION"),
        ),
    )
else:
    print("Greengrass v1 mode")
    stack = GreengrassPrivateNetworkStack(
        app,
        "greengrass-private-network",
        env=cdk.Environment(
            account=os.environ.get("CDK_DEPLOY_ACCOUNT"),
            region=os.environ.get("CDK_DEPLOY_REGION"),
        ),
    )

app.synth()
