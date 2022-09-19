
install the CDK stack, user data should have fixed up the requirements like java



Must allow list credentials endpoint as well as the yum updates so you can install java. You'll see in your CDK output, cut off the prefix and add to allow when installing the Cfn from this blog
https://aws.amazon.com/blogs/security/how-to-set-up-an-outbound-vpc-proxy-with-domain-whitelisting-and-content-filtering/

NOte this stack doesn't tear down well, it leaves the role and it leaves the IPs, maybe redo with CDK to fix and automate the params


choose VPC, public and private subnets, update CIDR, whitelist the credentials, like below match your region
.credentials.iot.us-east-1.amazonaws.com
can whitelist yum, something like: .s3.dualstack.us-east-1.amazonaws.com


you may need to go into Service Quotas and increase the EC2 VPC quota above 5. I used 10
The proxy uses 4, the greengrass uses 3 (two for IG and one for NAT), the VPN uses 1 

not required but consider to edit yum.conf, you'd have to put your mirror into the secrets for the allow list


SKIPPED
vim /etc/yum.conf
proxy=<YOUR PROXY LB ENDPOINT>


do this before you start greengrass install
sudo visudo 
root ALL=(ALL:ALL) ALL



greengrass endpoints, we solved most of these with VPC Endpoints/PrivateLink but you can also use a proxy and we'll have to do this for the credential provider

https://docs.aws.amazon.com/greengrass/v2/developerguide/allow-device-traffic.html



Now install the greengrass
Create the resources based on workshop to get started
https://iot.awsworkshops.com/aws-greengrassv2/lab35-greengrassv2-basics/

GreengrassPrivatePolicy
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["iot:Connect","iot:Publish", "iot:Subscribe", "iot:Receive", "greengrass:*"],
      "Resource": "*"
    }
  ]
}
```

create iot thing (if automate put the certs in secrets manager and add endpoint for it)
Name: PrivateGreengrassCore
Thing Group Name: PrivateGreengrass
Attach: PrivateGreengrassPolicy
Download all the certs

make an account id bucket
greengrass-setup-258899050475

copy up the certificates to a folder called certificates
pull it to your machine
aws s3 sync s3://greengrass-setup-258899050475/ .


setup python/pip and install awsiot SKIPPED
Download the greengrass software


setup greengrass config file and before installing greengrass go ahead and turn on proxy, swap route tables 
iot endpoints are in CDK output so don't need to run CLI commands or run them from CDK shell
If this fails we'll install then we'll do deployments once out there. 

now turn on the proxy settings and remove the NAT routes by swapping to main route table
MUST setup proxy endpoints var from Stack output