from typing import List, Union
from dataclasses import dataclass
import logging
import json

import boto3
import botocore.exceptions

from quickhost.temp_data_collector import store_test_data

from .constants import *
from .utilities import QH_Tag, Null
#from .temp_data_collector import store_test_data
from .AWSResource import AWSResourceBase


logger = logging.getLogger(__name__)

class SG(AWSResourceBase):
    #def __init__(self, client: any, ec2_resource: any, app_name: str, vpc_id: str, ports: List[int], cidrs: List[str], dry_run: bool):
    def __init__(self, app_name: str, vpc_id: str):
        self.client = self.get_client('ec2')
        self.ec2 = self.get_resource('ec2')
        self.app_name = app_name
        self.vpc_id = vpc_id

    def get_security_group_id(self) -> str:
        dsg = None
        try:
            dsg = self.client.describe_security_groups(
                Filters=[
                    { 'Name': 'vpc-id', 'Values': [ self.vpc_id, ] },
                    { 'Name': 'group-name', 'Values': [ self.app_name, ] },
                ],
            )
            return dsg['SecurityGroups'][0]['GroupId']
        except botocore.exceptions.ClientError as e:
            logger.debug(f"Could not get sg for app '{self.app_name}':\n{e}")
            return None
        if len(dsg['SecurityGroups']) > 1:
            raise RuntimeError(f"More than 1 security group was found with the name '{self.app_name}': {sg['GroupId'] for sg in dsg['SecurityGroups']}")
        elif len(dsg['SecurityGroups']) < 1:
            logger.debug(f"No security groups found for app '{self.app_name}'")
            return None

    def create(self, cidrs, ports, dry_run=False):
        try:
            sg = self.client.create_security_group(
                Description="Made by quickhost",
                GroupName=self.app_name,
                VpcId=self.vpc_id,
                TagSpecifications=[{ 'ResourceType': 'security-group',
                    'Tags': [
                        { 'Key': 'Name', 'Value': self.app_name },
                        QH_Tag(self.app_name)
                ]}],
                DryRun=dry_run
            )
            self.sgid = sg['GroupId']
            self._add_ingress(cidrs, ports)
            #store_test_data(resource='SG', action='create', response_data=_sg)
            return sg['GroupId']
        except botocore.exceptions.ClientError as e:
            logger.debug(f"Security Group already exists for '{self.app_name}':\n{e}")
            return self.get_security_group_id()

    def destroy(self):
        try:
            sg_id = self.get_security_group_id()
            if not sg_id:
                logger.debug(f"No security group found for app '{self.app_name}'")
                return None
            self.client.delete_security_group( GroupId=sg_id)
            logger.info(f"deleting security group '{sg_id}'")
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == 'InvalidGroup.NotFound':
                logger.info(f"No security group found for app '{self.app_name}', skipping...")
                return
            elif e.response['Error']['Code'] == 'UnauthorizedOperation':
                logger.error(f"({e.response['Error']['Code']}): {e.operation_name}")
                return
            else:
                logger.error(f"(Security Group) Unhandled botocore client exception: ({e.response['Error']['Code']}): {e.response['Error']['Message']}")
                return
        return

    def _add_ingress(self, cidrs, ports):
        try:
            perms = []
            for port in ports:
                perms.append({
                    'FromPort': int(port),
                    'IpProtocol': 'tcp',
                    'IpRanges': [ { 'CidrIp': cidr, 'Description': 'made with quickhosts' } for cidr in cidrs ],
                    'ToPort': int(port),
                })
            response = self.client.authorize_security_group_ingress(
                GroupId=self.sgid,
                IpPermissions=perms,
                DryRun=False
            )
            #print(f"done ({[i for i in cidrs]}:{[p for p in ports]})")
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == 'InvalidGroup.NotFound':
                logger.info(f"No security group found for app '{self.app_name}', skipping...")
                return
            elif e.response['Error']['Code'] == 'UnauthorizedOperation':
                logger.error(f"Unauthorized to get security group info: {e.response['Error']['Code']}: {e.response['Error']['Message']}")
                return
            else:
                logger.error(f"(Security Group) Unhandled botocore client exception: ({e.response['Error']['Code']}): {e.response['Error']['Message']}")
                return

    def describe(self):
        rtn = {
            'sgid': Null, #giving this a try
            'ports': [],
            'cidrs': [],
        }
        try:
            response = self.client.describe_security_groups(
                Filters=[
                    { 'Name': 'vpc-id', 'Values': [ self.vpc_id, ] },
                    { 'Name': 'group-name', 'Values': [ self.app_name, ] },
                ],
            )
            self.sgid = response['SecurityGroups'][0]['GroupId']
            for p in response['SecurityGroups'][0]['IpPermissions']:
                for ipr in p['IpRanges']:
                    cidrs.append(ipr['CidrIp'])
                if p['ToPort'] == p['FromPort']:
                    ports.append("{}/{}".format(
                        p['ToPort'],
                        p['IpProtocol']
                    ))
                else:
                    ports.append("{0}/{2}-{1}/{2}".format(
                        p['ToPort'],
                        p['FromPort'],
                        p['IpProtocol']
                    ))
            rtn['sgid']     = response['SecurityGroups'][0]['GroupId'] 
            rtn['ports']    = ports
            rtn['cidrs']    = cidrs
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == 'InvalidGroup.NotFound':
                self.sgid = None
                logger.error(f"No security group found for app '{self.app_name}' (does the app exist?)")
                rtn['sgid'] = None
            if e.response['Error']['Code'] == 'UnauthorizedOperation':
                logger.error(f"Unauthorized to get security group info: {e.response['Error']['Code']}: {e.response['Error']['Message']}")
            else:
                logger.error(f"(Security Group) Unhandled botocore client exception: ({e.response['Error']['Code']}): {e.response['Error']['Message']}")
        finally:
            return rtn
