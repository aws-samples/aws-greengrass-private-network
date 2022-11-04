#!/usr/bin/env python3

# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import aws_cdk as cdk
import os

from greengrass_private_network.greengrass_private_network_stack_vpn import (
    GreengrassPrivateNetworkStackVPN,
)


app = cdk.App()
# tgw = TgwStack(
#     app,
#     "greengrass-private-network-tgw",
#     env=cdk.Environment(
#         account=os.environ.get("CDK_DEPLOY_ACCOUNT"),
#         region=os.environ.get("CDK_DEPLOY_REGION"),
#     ),
# )
stack = GreengrassPrivateNetworkStackVPN(
    app,
    "greengrass-private-network-vpn",
    env=cdk.Environment(
        account=os.environ.get("CDK_DEPLOY_ACCOUNT"),
        region=os.environ.get("CDK_DEPLOY_REGION"),
    ),
)
# routes = GreengrassTgwRoutes(
#     app,
#     "greengrass-private-network-tgw-routes",
#     tgw_id=tgw.get_tgw_id,
#     env=cdk.Environment(
#         account=os.environ.get("CDK_DEPLOY_ACCOUNT"),
#         region=os.environ.get("CDK_DEPLOY_REGION"),
#     ),
# )

app.synth()
