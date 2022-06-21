
# AWS IoT Greengrass Private Networking with AWS PrivateLink

This is a python 3 based CDK solution that will build out the resources required to establish a private network between an OT site and cloud basedAWS IoT services using AWS IoT Greengrass. You can learn more about how this solution helps secure industry 4.0 architectures by visiting the companion AWS IoT Blog (To be released soon) [Secure Industry 4.0 networks with AWS IoT Greengrass and AWS PrivateLink](https://aws.amazon.com/blogs/iot/)

## Overview

This solution creates a multi AZ VPC with public and private subnets. It also configures PrivateLink VPC Endpoints for the AWS services that AWS IoT Greengrass interacts with. In addition an EC2 instance is setup in a private subnet that you can use to test things out before customizing or integrating this solution for your workloads. Before you start be sure to choose a [region](https://docs.aws.amazon.com/general/latest/gr/greengrass.html) that supports AWS IoT Greengrass. 

![Architecture Diagram](GreengrassPrivateNetwork.drawio.png)

## Prerequisites
Ensure that you have a base understanding of AWS IoT, AWS VPC, AWS EC2 and AWS CDK. You can learn how to install and configure the AWS CDK with this [getting started guide](https://docs.aws.amazon.com/cdk/v2/guide/getting_started.html) before running this solution. 

## Instructions

You can install this solution into your environment by first cloning this Git repository, then cd into `greengrass-private-network` directory. 
Next create a Python3 virtual environment and activate it. 
 
```
$ python3 -m venv .venv
```

After the init process completes and the virtualenv is created, you can use the following
step to activate your virtualenv.

```
$ source .venv/bin/activate
```

Once the virtualenv is activated, you can install the required dependencies.

```
$ pip install -r requirements.txt
```

In addition this stack requires you to set two environment variables to properly configure VPC details. Make sure you replace the values between the brackets <> with your valid values. Note that the below example is for common linux shells like sh, bash, or zsh.

```
export CDK_DEPLOY_ACCOUNT=<AWS_ACCOUNT>
export CDK_DEPLOY_REGION=<AWS_REGION>
```

You are now ready to bootstrap the CDK in your account if you have not already done so. 

```
cdk bootstrap
```

And deploy the greengrass private network stack

``` 
cdk deploy
```

## AWS IoT Greengrass Configuration

Once the stack is fully deployed you'll be able to login to your EC2 testing instance to configure the AWS IoT Greengrass runtime. This instance is setup for Systems Manger Session Manager so that you can easily connect from the AWS Console. On the EC2 console select the Greengrass EC2 instance then choose Connect and once on the Connect screen choose the Session Manager tab. It is best to first install AWS IoT Greengrass, then remove routes to the NAT Gateway, then begin your testing. Note that as of today AWS Greengrass v2 will not run in a completely isolated subnet, so for the time being this solutions configures IoT GreenGrass v1. To install AWS IoT Greengrass v1, go to the console and connect to your instance using AWS Systems Manager. Then you can follow [Module 2: Installing the AWS IoT Greengrass Core software](https://docs.aws.amazon.com/greengrass/v1/developerguide/module2.html). 

You are able to skip Module 1 as the CDK stack already setup the EC2 instance with required dependencies. I found that when you get to step 9. Download your core's security resources and configuration file, it is easiest to upload the xxxxxxxxx-setup.tar.gz file and the AWS Iot Greengrass to an S3 bucket. You'll need the "Armv8 (AArch64) Linux" version for the EC2 instance setup in this solution. 

Create an S3 bucket called greengrass-setup-<account_id> substituting your account id. Then upload the setup file and the AWS IoT Greengrass runtime. Next you can download these files from your bucket to EC2 and proceed with the setup instructions. Run below in your EC2 Systems Manager CLI session. Be sure to replace your account id and file name for setup before running these.

```
cd ~
aws s3 cp s3://greengrass-setup-<account_id>/<hash>-setup.tar.gz .
aws s3 cp s3://greengrass-setup-<account_id>/greengrass-linux-aarch64-1.11.6.tar.gz .

```

Now that you have the required files in place, resume with the instructions [Start AWS IoT Greengrass on the core device](https://docs.aws.amazon.com/greengrass/v1/developerguide/gg-device-start.html) at Step 4. Install the AWS IoT Greengrass Core software and the security resources. Once you've successfully installed and started Greengrass, it's time to setup your private network and test out connectivity to your VPC Endpoints. You may also want to navigate to the settings of your AWS Greengrass group in the IoT Core console to [enable local and CloudWatch logs](https://docs.aws.amazon.com/greengrass/v1/developerguide/greengrass-logs-overview.html#config-logs). 

## Private Network Validation

First stop Greengrass
```
cd /greengrass/ggc/core/
sudo ./greengrassd stop
```

Next we'll remove the NAT Gateways from our private subnets to isolate them from the internet. At this point they will only be able to interact with internal VPC resources including endpoints and any peered connections like your OT environment over a VPN or Direct Connect. In the AWS VPC Console navigate to VPC, then to subnets. For each subnet named like `greengrass-private-network/GreengrassPrivateNetwork/Private with NATSubnet` select the checkbox next to one of the private subnets, then on the lower half of the screen choose on Route table and choose the hyperlinked route table name. This will bring you to the route table screen when you can choose routes and remove the route to the NAT Gateway. It will be a route with a destination of `0.0.0.0/0` and a target of `nat-<hash>`. Choose edit routes and remove this route. You'll need to do this for each private subnet. 

Once you've completed these steps terminate your Session Manger session with the Greengrass instance if it is still running. Then from the EC2 console start a new Session Manager connection. This time you'll make a connection to Systems Manager using your SSM VPC Endpoints setup by the CDK. We can validate the other endpoints with nslookup before firing up Greengrass as well. For the last value you'll need to replace the hash with your IoT Core endpoint value which you can find on your IoT Core Console on the Setting page. 

```
nslookup greengrass-setup-<account_id>.s3.<region>.amazonaws.com
nslookup greengrass-ats.iot.<region>.amazonaws.com
nslookup logs.<region>.amazonaws.com
nslookup <hash>-ats.iot.<region>.amazonaws.com
```

For each lookup, once you've replaced the values in brackets, you will see endpoints resolve inside the VPC CIDR block range for your private network. You can see this CIDR block range printed in the CDK output, the value will be similar to `greengrass-private-network.GreengrassVpcCIDRBlock = 10.0.0.0/16`

Output from nslookup commands that show endpoint addresses in your private network VPC CIDR Range will look similar to the following with an entry for each associated subnet:

```
$ nslookup greengrass-ats.iot.us-west-2.amazonaws.com
Server:  10.0.0.2
Address: 10.0.0.2#53

Non-authoritative answer:
Name:    greengrass-ats.iot.us-west-2.amazonaws.com
Address: 10.0.111.120
Name:    greengrass-ats.iot.us-west-2.amazonaws.com
Address: 10.0.175.96
Name:    greengrass-ats.iot.us-west-2.amazonaws.com
Address: 10.0.154.211
```

Next on the IoT Core console, browse to Test and choose MQTT Test Client and subscribe to the **Topic filter** with a value of **#** which will echo all messages. Now in your EC2 instance SSM session, start Greegrass again

```
cd /greengrass/ggc/core/
sudo ./greengrassd start
```

You should see several MQTT messages from Greengrass showing your private connectivity flowing through your VPC Endpoints in your isolated subnets. You have validated your endpoints and Greengrass connectivity, but have only exercised the IoT Core endpoint for MQTT communications. 

<!-- You can take this a step further by working through Module 3 parts 1 and 2 [Lambda Functions on AWS IoT Greengrass](https://docs.aws.amazon.com/greengrass/v1/developerguide/module3-I.html). -->

You are now ready to connect your OT network to your greengrass-private-network VPC. You can also opt to delete your NAT Gateway, Internet Gateway and public subnets, or customize the CDK stack to align with your networking requirements.
