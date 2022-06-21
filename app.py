#!/usr/bin/env python3

# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import aws_cdk as cdk
import os

from greengrass_private_network.greengrass_private_network_stack import (
    GreengrassPrivateNetworkStack,
)


# Cannot look up VPC endpoint availability zones if account/region are not specified

app = cdk.App()
stack = GreengrassPrivateNetworkStack(
    app,
    "greengrass-private-network",
    env=cdk.Environment(
        account=os.environ.get("CDK_DEPLOY_ACCOUNT"),
        region=os.environ.get("CDK_DEPLOY_REGION"),
    ),
)

app.synth()
