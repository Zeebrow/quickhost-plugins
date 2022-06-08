# AWS plugin for quickhost

`NOTE`
This is a comprehensive setup - several steps will be automated in the future.

`quickhost` is a plugin-driven program.

## Getting started

To use quickhost, you will also need a plugin for the cloud/hosting provider
you wish to use (AWS is free ;)


## 7 June 2021

You will create the following resources:

* [ ] AWS account (15 minutes, free)
* [ ] AWS linked account setup (5 minutes, free, optional, recommended)
* [ ] AWS User permissions (X minutes, free)
* [ ] Break (at least 15 minutes, FREE!)
* [ ] vpc id, subnet id (5 mintes, free)
* [ ] linkages (5 minutes, free)

### AWS root account setup

(15 minutes)

Seems like a lot, but 1-5 are just so you know what you'll be asked and when.

* [ ] email #1: Root account
* [ ] email #2: Governed account (optional)
* [ ] SMS telephone number
* [ ] Credit card info

You can sign up for an account at <https://aws.amazon.com>.

#### 1 Link email to root account
* [ ] Account name (for example, MyRootAccount)
* [ ] Email address
* [ ] password
* [ ] verify

#### 2

* [ ] Your full name
* [ ] Your phone number
* [ ] Your address
* [ ] agree to the [customer agreement](https://aws.amazon.com/agreement/)

#### 3

* [ ] Credit card info (can you use visa gift cards?)
* You WILL NOT pay until using non-free-tier resources. For quickhost, we're
  interested in the `750 hours` of EC2 usage (for the first 12 months). See
  <https://aws.amazon.com/free> 

#### 4 Confirm your identity

* [ ] ok

#### 5 Choose a support plan

I will be your support plan. Make an issue with your question, and I'll
do my best to answer accurately, as soon as possible.

Click the go to the console button to continue getting your VPC ID

### AWS linked account setup (optional, recommended)

AWS Organizations --> AWS accounts/Invitations --> Invite AWS account -->
create new

* Once you receive email, sign out of your root account, and login again with
your 2nd email (use the 'root account' bubble on the sign-in page)
* set your password with the "forgot password" link
* sign in

### AWS User setup (IAM)

NOTE: In a future release, all operations performed by this user will be
delegated to an IAM Role instead.

NOTHER NOTE: a lot of the data here is for me to automate. I need to think
about the right way to go about setting up permissions, transparently and
effectively.

Create a set of credentials for quickhost to use to initialize itself (delete
when done)

* visit
  <https://us-east-1.console.aws.amazon.com/iam/home#/security_credentials> for
  your region
* Access Keys --> Create Access key
  - download keyfile? or prompt at cli?
* run one of the following: 
  - `main.py init aws --root-key-file`
  - `main.py init aws --access-key-id ABC --secret XYZ`
  - `main.py init aws` and follow the prompts (protected by Python3's `getpass`)



#### IAM Policy: quickhost-describe

E.g:

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
* [ ] group-name - quickhost-admin
* [ ] policy - quickhost-create
* [ ] policy - quickhost-describe
* [ ] policy - quickhost-update
* [ ] policy - quickhost-destroy

#### IAM user - quickhost

Click the IAM service --> Users --> Create User

* [ ] Username = quickhost
* [ ] Access Type = Access Key - Programatic Access
* [ ] groups - quickhost-admin
* [ ] get and store aws credentials


### VPC ID

Upon logging into the aws console, you will probably be redirected to the
`us-east-1` region. If not, make a note of what region you're using!

Click the `VPC` service -> Create new.

* "VPC Only" (idk what the other option sets up behind your back)

* [ ] tag (for example, quickhost)
* [ ] cidr block (for example, 10.11.0.0/16) (use big ranges here, these confine your options for public subnet cidrs)

* the rest default (quickhost doesn't support ipv6)

Output: your `vpc-id` (for example, vpc-0e855b6315b73c33d)

### Subnet ID

From the VPC service's console, click Subnets --> Create Subnet

* [ ] Select the VPC created above from the dropdown
* [ ] Tag with `quickhost` for Name
* [ ] Enter/select the desired cidr range (for example, 10.11.12.0/24)

Output: your `subnet-id` (for example, subnet-083c35291b743face)

### Linkages 

All free

Required for EC2 hosts to connect to the internet. *This step alone does not
make them publically accessible!*

#### Internet Gateway
From the VPC service's console, click Internet Gateways --> Create Internet
Gateway

* [ ] Tag with `quickhost` for Name

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



