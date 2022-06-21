# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import aws_cdk as cdk
import aws_cdk.assertions as assertions
from greengrass_private_network.greengrass_private_network_stack import (
    GreengrassPrivateNetworkStack,
)
from cdk_nag import AwsSolutionsChecks, NagSuppressions
import os


def test_vpc_endpoints_created():
    app = cdk.App()
    stack = GreengrassPrivateNetworkStack(
        app,
        "greengrass-private-network",
        env=cdk.Environment(
            account=os.environ.get("CDK_DEPLOY_ACCOUNT"),
            region=os.environ.get("CDK_DEPLOY_REGION"),
        ),
    )
    template = assertions.Template.from_stack(stack)

    template.resource_count_is("AWS::EC2::VPCEndpoint", 7)


def test_ec2_test_instance_created():
    app = cdk.App()
    stack = GreengrassPrivateNetworkStack(
        app,
        "greengrass-private-network",
        env=cdk.Environment(
            account=os.environ.get("CDK_DEPLOY_ACCOUNT"),
            region=os.environ.get("CDK_DEPLOY_REGION"),
        ),
    )
    template = assertions.Template.from_stack(stack)

    template.has_resource_properties(
        "AWS::EC2::Instance", {"InstanceType": "t4g.micro"}
    )


def test_cdk_nag_passes():
    app = cdk.App()
    stack = GreengrassPrivateNetworkStack(
        app,
        "greengrass-private-network",
        env=cdk.Environment(
            account=os.environ.get("CDK_DEPLOY_ACCOUNT"),
            region=os.environ.get("CDK_DEPLOY_REGION"),
        ),
    )
    cdk.Aspects.of(app).add(AwsSolutionsChecks(verbose=True))
    NagSuppressions.add_stack_suppressions(
        stack,
        suppressions=[
            {
                "id": "AwsSolutions-EC29",
                "reason": "EC2 instance is for testing only, Greengrass will be installed at the edge in implementation",
            },
            {
                "id": "AwsSolutions-IAM4",
                "reason": "EC2 instance is for testing only with logging and instance connect, must read from Greengrass bucket and bucket created manually if used to upload archive files to test Greengrass",
            },
        ],
    )
