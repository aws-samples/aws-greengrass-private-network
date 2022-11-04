#!/bin/bash 

# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

echo "setup greengrassv2 environment"
adduser --system ggc_user
groupadd --system ggc_group


yum update -y
sudo amazon-linux-extras install java-openjdk11 -y
java -version
