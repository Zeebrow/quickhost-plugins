import json
import logging
from configparser import ConfigParser
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

from quickhost import convert_datetime_to_string

from .utilities import get_single_result_id, check_running_as_user
from .constants import AWSConstants

logger = logging.getLogger(__name__)

class Iam:
    def __init__(self):
        self.client = boto3.client('iam')
        self.iam_user = AWSConstants.DEFAULT_IAM_USER
        self.iam_group = f"{AWSConstants.DEFAULT_IAM_USER}s"

    def create(self):
        self.create_user_group()
        self._create_user_credentials()
        self.create_policies()
        self.attach_policies_and_group()

    def destroy(self):
        iam = boto3.resource('iam')
        policy_arns = self.qh_policy_arns()
        user = iam.User(self.iam_user)
        group = iam.Group(self.iam_group)

        ########################################################
        try:
            group.remove_user(UserName=self.iam_user)
            logger.info(f"Removed user '{self.iam_user}' from group '{self.iam_group}'")
        except ClientError as e:
            code = e.__dict__['response']['Error']['Code']
            if code == 'NoSuchEntity':
                logger.info(f"User '{self.iam_user}' was removed from Group '{self.iam_group}'")
            else:
                logger.error(f"Unknown error caught while deleting group: {e}")
        ########################################################
        for action,arn in policy_arns.items():
            if arn is None:
                logger.info(f"Policy for '{action}' not found.")
                continue
            p = iam.Policy(arn)
            if p.attachment_count == 0:
                logger.info(f"Policy '{p.arn}' is not attached.")
            else:
                p.detach_group(GroupName=group.name)
                logger.info(f"Detatched policy {arn} from {group.name}... ")
            p.delete()
            logger.info(f"Deleted policy {p.arn}... ")
        ########################################################
        try:
            group.delete()
            logger.info(f"Deleted group {group.arn}... ")
        except ClientError as e:
            code = e.__dict__['response']['Error']['Code']
            if code == 'NoSuchEntity':
                logger.info(f"Group '{self.iam_group}' doesn't exist")
            else:
                logger.error(f"Unknown error caught while deleting group: {e}")
        ########################################################
        try:
            user.delete()
            self._delete_user_credentials()
            logger.info(f"Deleted user {user.arn}... ")
        except ClientError as e:
            code = e.__dict__['response']['Error']['Code']
            if code == 'NoSuchEntity':
                logger.info(f"User '{self.iam_user}' doesn't exist")
            else:
                logger.error(f"Unknown error caught while deleting user: {e}")

    def create_policies(self):
        iam = boto3.resource('iam')
        policy_arns = self.qh_policy_arns()
        for action,arn in policy_arns.items():
            arn = self._create_qh_policy(action)

    def attach_policies_and_group(self):
        iam = boto3.resource('iam')
        group = iam.Group(self.iam_group)
        policy_arns = self.qh_policy_arns()
        for action,arn in policy_arns.items():
            if arn is None:
                logger.warning(f"Not attaching a policy for action '{action}': Does not exist.")
                continue
            group.attach_policy(PolicyArn=policy_arns[action])
            logger.info(f"Policy '{policy_arns[action]}' is attached to group '{group.name}'")
        group.add_user(UserName=self.iam_user)
        logger.info(f"User '{self.iam_user}' is attached to group '{group.name}'")

    def create_user_group(self):
        iam = boto3.resource('iam')
        existing_policies = self.qh_policy_arns()
        user = iam.User(self.iam_user)
        group = iam.Group(self.iam_group)
        try:
            user = user.create(
                Path='/',
                Tags=[ { 'Key': 'quickhost', 'Value': 'aws' }, ]
            )
            logger.info(f"Created user '{self.iam_user}'")
        except ClientError as e:
            code = e.__dict__['response']['Error']['Code']
            if code == 'EntityAlreadyExists':
                logger.info(f"User '{self.iam_user}' already exists.")

        try: 
            group.create(Path='/')
            logger.info(f"Created group '{self.iam_group}'")
        except ClientError as e:
            code = e.__dict__['response']['Error']['Code']
            if code == 'EntityAlreadyExists':
                logger.info(f"Group '{self.iam_group}' already exists.")


    def qh_policy_arns(self):
        rtn = {
            'create': None,
            'describe': None,
            'update': None,
            'destroy': None,
        }
        qh_policies = convert_datetime_to_string(self.client.list_policies(
            PathPrefix='/quickhost/',
        ))['Policies']
        describe_policy_arn = None
        for policy in qh_policies:
            if policy['PolicyName'] == 'quickhost-create':
                rtn['create'] = policy['Arn']
            elif policy['PolicyName'] == 'quickhost-describe':
                rtn['describe'] = policy['Arn']
            elif policy['PolicyName'] == 'quickhost-update':
                rtn['update'] = policy['Arn']
            elif policy['PolicyName'] == 'quickhost-destroy':
                rtn['destroy'] = policy['Arn']
            else:
                logger.warning(f"Found unknown quickhost policy {policy['PolicyName']}")
                continue
        return rtn

    def _create_qh_policy(self, action: str) -> str:
        iam = boto3.resource('iam')
        existing_policies = self.qh_policy_arns()
        arn = None
        try: 
            new_policy = self.client.create_policy(
                PolicyName=f"quickhost-{action}",
                Path='/quickhost/',
                PolicyDocument=json.dumps(PolicyData[action]),
                Description=f"Allow quickhost-users to {action} apps",
                Tags=[ { 'Key': 'quickhost', 'Value': 'aws' }, ]
            )
            arn = new_policy['Policy']['Arn']
            logger.info(f"created '{action}' policy '{arn}'")
        except ClientError as e:
            code = e.__dict__['response']['Error']['Code']
            if code == 'EntityAlreadyExists':
                logger.info(f"Policy '{action}' already exists.")
                arn = existing_policies[action]
        return arn

    def _delete_user_credentials(self):
        aws_config_dir = Path.home() / '.aws'
        aws_credentials_file = aws_config_dir / "credentials"
        aws_config_file = aws_config_dir / "config"
        iam = boto3.resource('iam')
        user = iam.User(self.iam_user)
        keys = user.access_keys.all()
        for k in keys:
            logger.info(f"Deleting access key: {k.id}...")
            k.delete()

        config_parser = ConfigParser()
        config_parser.read(aws_config_file)
        cfg_deleted = config_parser.remove_section(f"profile {self.iam_user}")
        if cfg_deleted:
            with aws_config_file.open('w') as aws_cfg:
                aws_cfg.write(config_parser)
            logger.info(f"deleted {self.iam_user} from aws config file.")

        credentials_parser = ConfigParser()
        credentials_parser.read(aws_credentials_file)
        creds_deleted = config_parser.remove_section(f"profile {self.iam_user}")
        if creds_deleted:
            with aws_credentials_file.open('w') as aws_creds:
                aws_cfg.write(config_parser)
            logger.info(f"deleted {self.iam_user} from aws credentials file.")
        return 

    def _create_user_credentials(self, region='us-east-1', output='json'):
        aws_config_dir = Path.home() / '.aws'
        iam = boto3.resource('iam')
        user = iam.User(self.iam_user)
        access_key_pair = user.create_access_key_pair()

        if not aws_config_dir.exists():
            logger.info(f"Creating new directory for aws credentials: {aws_config_dir.absolute()}")
            logger.warning(f"(not really)")
        aws_credentials_file = aws_config_dir / "credentials"
        aws_config_file = aws_config_dir / "config"

        config_parser = ConfigParser()
        config_parser.read(aws_config_file)
        if not self.iam_user in config_parser:
            config_parser[f"profile {self.iam_user}"] = {
                'region': region,
                'output': output,
            }
            with aws_config_file.open('w') as aws_cfg:
                config_parser.write(aws_cfg)

        credentials_parser = ConfigParser()
        credentials_parser.read(aws_credentials_file)
        if not self.iam_user in credentials_parser:
            credentials_parser[self.iam_user] = {
                'aws_access_key_id': access_key_pair.id,
                'aws_secret_access_key': access_key_pair.secret,
            }
            with aws_credentials_file.open('w') as aws_creds:
                credentials_parser.write(aws_creds)
            aws_credentials_file.chmod(0o0600)




PolicyData = {
    'create':{
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "quickhostCreate",
                "Effect": "Allow",
                "Action": [
                    "ec2:CreateKeyPair",
                    "ec2:AuthorizeSecurityGroupIngress",
                    "ec2:CreateSecurityGroup"
                ],
                "Resource": "*"
            }
        ]
    },
    'describe': {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "quickhostDescribe",
                "Effect": "Allow",
                "Action": [
                    "iam:ListUsers",
                    "ec2:DescribeInstances",
                    "ec2:DescribeVpcs",
                    "ec2:DescribeSubnets",
                    "ec2:DescribeInternetGateways",
                    "ec2:DescribeRouteTables",
                    "ec2:DescribeImages"
                ],
                "Resource": "*"
            }
        ]
    },
    'update': {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "quickhostUpdate",
                "Effect": "Allow",
                "Action": [],
                "Resource": "*"
            }
        ]
    },
    'destroy': {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "quickhostDelete",
                "Effect": "Allow",
                "Action": [
                    "ec2:DescribeSecurityGroups",
                    "ec2:DeleteSecurityGroup",

                    "ec2:DeleteKeyPair",
                    "ec2:DescribeKeyPairs",
                    
                    "ec2:TerminateInstances"
                ],
                "Resource": "*"
            }
        ]
    }
}
