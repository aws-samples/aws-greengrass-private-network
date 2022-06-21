#!/bin/bash 

# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0


echo "setup greengrass"
yum update -y
adduser --system ggc_user
groupadd --system ggc_group

# confirms hardlinks and softlinks are set to one, review logs if suspected issues
sysctl -a | grep fs.protected

cd /home/ssm-user

# mount linux control groups
curl https://raw.githubusercontent.com/tianon/cgroupfs-mount/951c38ee8d802330454bdede20d85ec1c0f8d312/cgroupfs-mount > cgroupfs-mount.sh
chmod +x cgroupfs-mount.sh 
bash ./cgroupfs-mount.sh

# install java
yum install java-1.8.0-openjdk -y

yum install git -y
yum install pip -y

yum remove awscli -y 
curl "https://awscli.amazonaws.com/awscli-exe-linux-aarch64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
./aws/install
aws --version

# run greengrass dependency checker, review logs if suspected issues
mkdir greengrass-dependency-checker-GGCv1.11.x
cd greengrass-dependency-checker-GGCv1.11.x
wget https://github.com/aws-samples/aws-greengrass-samples/raw/master/greengrass-dependency-checker-GGCv1.11.x.zip
unzip greengrass-dependency-checker-GGCv1.11.x.zip
cd greengrass-dependency-checker-GGCv1.11.x
./check_ggc_dependencies
#Note:
#1. It looks like the kernel uses 'systemd' as the init process. Be sure to set the
#'useSystemd' field in the file 'config.json' to 'yes' when configuring Greengrass core.
