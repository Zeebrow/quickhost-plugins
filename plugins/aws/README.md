# AWS plugin for quickhost

`NOTE`
A better way to do this would be to *not* use a root account. This should be
done outside of `quickhost`.

`quickhost` is a plugin-driven program.

## Getting started

To use quickhost, you will also need a plugin for the cloud/hosting provider
you wish to use (AWS is free ;)


## 7 June 2021

You will need the following resources:

* [ ] AWS account (15 minutes, free)

* [ ] vpc id (5 minutes, free)

* [ ] subnet id (5 mintes, free)

* [ ] linkages (5 minutes, free)

### AWS account

(15 minutes)

You can sign up for an account at <https://aws.amazon.com>.

#### 1
[ ] Email address
[ ] password
[ ] verify

#### 2

[ ] Your full name
[ ] Your phone number
[ ] Your address
[ ] agree to the [customer agreement](https://aws.amazon.com/agreement/)

#### 3

[ ] Credit card info (can you use visa gift cards?)
* You WILL NOT pay until using non-free-tier resources. For quickhost, we're
  interested in the `750 hours` of EC2 usage (for the first 12 months). See
  <https://aws.amazon.com/free> 

#### 4 Confirm your identity

* You will be prompted to enter another phone number to confirm.
[ ] ok

#### 5 Choose your support plan

I will be your support plan. Make a pull-request with your question, and I'll
do my best to answer accurately, as soon as possible.

[ ] free

Click the go to the console button to continue getting your VPC ID

### AWS User (IAM)

NOTE: In a future release, all operations performed by this user will be
delegated to an IAM Role instead.

#### IAM Policy: quickhost-describe

E.g.

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "VisualEditor0",
            "Effect": "Allow",
            "Action": [
                "ec2:DescribeAddresses",
                "ec2:DescribeInstances",
                "ec2:DescribeSecurityGroups",
                "ec2:DescribeImages",
                "ec2:DescribeInternetGateways",
                "ec2:DescribeSecurityGroupRules",
                "ec2:DescribeNetworkInterfaces",
                "ec2:DescribeInstanceTypeOfferings",
                "ec2:DescribeAvailabilityZones",
                "ec2:DescribeSecurityGroupReferences",
                "ec2:DescribeInstanceTypes",
                "ec2:DescribeSubnets",
                "ec2:DescribeKeyPairs",
                "ec2:DescribeInstanceStatus"
            ],
            "Resource": "*"
        }
    ]
}
```

#### IAM group - quickhost-admin
[ ] group-name - quickhost-admin
[ ] policy - quickhost-create
[ ] policy - quickhost-describe
[ ] policy - quickhost-update
[ ] policy - quickhost-destroy

#### IAM user - quickhost

Click the IAM service --> Users --> Create User

[ ] Username = quickhost
[ ] Access Type = Access Key - Programatic Access
[ ] groups - quickhost-admin
[ ] get and store aws credentials


### VPC ID

Upon logging into the aws console, you will probably be redirected to the
`us-east-1` region. If not, make a note of what region you're using!

Click the `VPC` service -> Create new.

* "VPC Only" (idk what the other option sets up behind your back)

[ ] tag (for example, quickhost)
[ ] cidr block (for example, 10.11.0.0/16) (use big ranges here, these confine your options for public subnet cidrs)

* the rest default (quickhost doesn't support ipv6)

Output: your `vpc-id` (for example, vpc-0e855b6315b73c33d)

### Subnet ID

From the VPC service's console, click Subnets --> Create Subnet

[ ] Select the VPC created above from the dropdown
[ ] Tag with `quickhost` for Name
[ ] Enter/select the desired cidr range (for example, 10.11.12.0/24)

Output: your `subnet-id` (for example, subnet-083c35291b743face)

### Linkages 

All free

Required for EC2 hosts to connect to the internet. *This step alone does not
make them publically accessible!*

#### Internet Gateway
From the VPC service's console, click Internet Gateways --> Create Internet
Gateway

[ ] Tag with `quickhost` for Name

Click create --> Output: Internet Gateway (igw-04ccfe98927415391)

Click Actions --> Attach Internet Gateway and select your quickhost gateway

* If you're curious, there is a record of this action, returned if you were to
  do this step from the aws command line

#### Route table

Tell AWS that traffic originating from with in the VPC NOT destined locally to
create a stateful connection with our favorite source of memes (0.0.0.0/0)

1. Click Route Tables and find the Route table associated with your VPC (this was
created when you created the quickhost vpc)
2. Select it by ticking the check box to its left
3. Find the `Routes` tab below, click it, and then click Edit Routes
4. Click Add Route
  * target - 0.0.0.0/0
  * destination - Internet Gateway (the one you just created)

### Configure quickhost.conf

Open `/opt/etc/quickhost/quickhost.conf` and create an app:

```
[demoapp:aws]
vpc_id = vpc-0e855b6315b73c33d
subnet_id = subnet-083c35291b743face
```



