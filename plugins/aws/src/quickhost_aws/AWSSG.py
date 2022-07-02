from typing import List, Union
from dataclasses import dataclass
import logging
import json

import boto3
import botocore.exceptions

from .constants import *
from .utilities import QH_Tag
#from .temp_data_collector import store_test_data
from quickhost.temp_data_collector import store_test_data


logger = logging.getLogger(__name__)

class AWSPort:
    """This will be fun"""
    pass

class SG:
    #def __init__(self, client: any, ec2_resource: any, app_name: str, vpc_id: str, ports: List[int], cidrs: List[str], dry_run: bool):
    def __init__(self, client: any, ec2_resource: any, app_name: str, vpc_id: str):
        self.client = client
        self.ec2 = ec2_resource
        self.app_name = app_name
        self.vpc_id = vpc_id
#        self.ports = None
#        self.cidrs = None
#        self.dry_run = dry_run
        self.sgid = self.get_security_group_id()

    def get_security_group_id(self) -> str:
        logger.debug(f"{self.vpc_id=}")
        dsg = None
        try:
            dsg = self.client.describe_security_groups(
                Filters=[
                    { 'Name': 'vpc-id', 'Values': [ self.vpc_id, ] },
                    { 'Name': 'group-name', 'Values': [ self.app_name, ] },
                ],
            )
        except botocore.exceptions.ClientError as e:
            logger.debug(f"Could not get sg for app '{self.app_name}':\n{e}")
            return None
        if len(dsg['SecurityGroups']) > 1:
            raise RuntimeError(f"More than 1 security group was found with the name '{self.app_name}': {sg['GroupId'] for sg in dsg['SecurityGroups']}")
        elif len(dsg['SecurityGroups']) < 1:
            logger.debug(f"No security groups found for app '{self.app_name}'")
            return None

        #store_test_data(resource='SG', action='describe', response_data=_dsg)
        return dsg['SecurityGroups'][0]['GroupId']

    def create(self, cidrs, ports, dry_run=False):
        print('creating sg...', end='')
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
        print(f"done ({sg['GroupId']})")
        self.sgid = sg['GroupId']
        self._add_ingress(cidrs, ports)
        #store_test_data(resource='SG', action='create', response_data=_sg)
        return sg['GroupId']

    def destroy(self):
        sg_id = self.get_security_group_id()
        if not sg_id:
            logger.debug(f"No security group found for app '{self.app_name}'")
            return None
        self.client.delete_security_group( GroupId=sg_id)
        print(f"deleting security group '{sg_id}'")
        return

    def _add_ingress(self, cidrs, ports):
        print('adding sg ingress...', end='')
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
        print(f"done ({[i for i in cidrs]}:{[p for p in ports]})")
        #store_test_data(resource='SG', action='_add_ingress', response_data=response)

    def describe(self):
        response = None
        ports = []
        cidrs = []
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

        except botocore.exceptions.ClientError as e:
            if 'InvalidGroup.NotFound' in e.response:
                self.sgid = None
                logger.error(f"No security group found for app '{self.app_name}' (does the app exist?)")
        #print(json.dumps(response['SecurityGroups'][0], indent=2))
        logger.debug(f"{ports=}")
        logger.debug(f"{cidrs=}")
        for ip in cidrs:
            print(f"{ip}:{[p for p in ports]}")
        return response

if __name__ == '__main__':
    import boto3
    import json
    try:
        from .utilities import get_my_public_ip
    except:
        from utilities import get_my_public_ip

    client = boto3.client('ec2')
    sg = SG(
        client=client,
        app_name='test-sg',
        vpc_id='vpc-7c31a606',
        ports=['22'],
        cidrs=[f"{get_my_public_ip()}/32"],
        dry_run=False
    )
    print(json.dumps(sg.describe(), indent=2))
