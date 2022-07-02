from typing import List
import time
import logging
import json
from datetime import datetime

import boto3
from botocore.exceptions import ClientError

import quickhost
from quickhost import APP_CONST as QHC
from quickhost.temp_data_collector import store_test_data

from .AWSSG import SG
from .constants import AWSConstants as AWS

logger = logging.getLogger(__name__)

class AWSHost:
    def __init__(self, client: any, ec2_resource, app_name):
        self.client = client
        self.ec2 = ec2_resource
        self.app_name=app_name
#        return 
#        self.num_hosts=num_hosts
#        self.image_id=image_id
#        self.instance_type=instance_type
#        self.sgid=sgid
#        self.subnet_id=subnet_id
#        self.key_name = key_name
#        if key_name is None:
#            self.key_name = app_name
#        self.userdata=userdata
#        self.dry_run=dry_run
#        self.app_instances = []

    def destroy(self):
        instance_ids = self.get_instance_ids()
        print(f"{instance_ids=}")
        #self.describe()
        instances = []
        print(instance_ids)
        for i in instance_ids:
            instances.append(i['instance-id'])
        print(instances)
        self.client.terminate_instances(
            InstanceIds=instances
        )


    def get_instance_ids(self, state_list=['running', 'starting']) -> List[str]:
        """Given the app_name, returns the instance id off all instances with a State of 'running'"""
        running_instances = []
        _app_hosts = self.client.describe_instances(
            Filters=[
                { 'Name': f"tag:{QHC.DEFAULT_APP_NAME}", 'Values': [ self.app_name, ] },
                { 'Name': 'instance-state-name', 'Values': state_list },
            ],
            DryRun=False,
            MaxResults=10,
            #NextToken='string'
        )
        #print(json.dumps(convert_datetime_to_string(_app_hosts),indent=2))
        store_test_data(resource='AWSHost', action='describe', response_data=quickhost.convert_datetime_to_string(_app_hosts))
        for r in _app_hosts['Reservations']:
            for host in r['Instances']:
                if host['State']['Name'] in state_list:
                    running_instances.append({'instance-id': host['InstanceId'], 'state': host['State']['Name']})
                    inst = self._descibe_instance(host_from_response=host)
                    continue
        return running_instances

    @classmethod
    def get_latest_image(self, client, os=QHC.DEFAULT_APP_NAME):
        """
        Get the latest amazon linux 2 ami
        TODO: see source-aliases and make an Ubuntu option
        """
        response = client.describe_images(
            Filters=[
                {
                    'Name': 'name',
                    'Values': [ 'amzn2-ami-hvm-2.0.????????-x86_64-gp2', ]
                },
                {
                    'Name': 'state',
                    'Values': [ 'available', ]
                },
            ],
            IncludeDeprecated=False,
            DryRun=False
        )
        sortedimages = sorted(response['Images'], key=lambda x: datetime.strptime(x['CreationDate'], '%Y-%m-%dT%H:%M:%S.%fZ'))
        return sortedimages[-1]['ImageId']

    def _descibe_instance(self, host_from_response: dict):
        _app_name = None
        for tag in host_from_response['Tags']:
            if tag['Key'] == QHC.DEFAULT_APP_NAME:
                if tag['Value'] == self.app_name:
                    break
        return {
            'app_name': self.app_name,
            'ami': host_from_response['ImageId'],
            'instance_id': host_from_response['InstanceId'],
            'instance_type': host_from_response['InstanceType'],
            'public_ip': host_from_response['PublicIpAddress'],
            'subnet_id': host_from_response['SubnetId'],
            'vpc_id': host_from_response['VpcId'],
            '_state': host_from_response['State']['Name'],
            '_platform': host_from_response['PlatformDetails'],
        }

    def get_hosts_for_app(self, app_name: str):
        """Given the app_name, returns a list of instance ids for a particular app, where the instance state is 'running'"""
        _instances = []
        _app_hosts = self.client.describe_instances(
            Filters=[
                { 'Name': f"tag:{QHC.DEFAULT_APP_NAME}", 'Values': [ self.app_name, ] },
            ],
            DryRun=False,
            MaxResults=10,
            #NextToken='string'
        )
        #print(json.dumps(convert_datetime_to_string(_app_hosts),indent=2))
        store_test_data(resource='AWSHost', action='describe', response_data=quickhost.convert_datetime_to_string(_app_hosts))
        for r in _app_hosts['Reservations']:
            for host in r['Instances']:
                if host['State']['Name'] in ['running', 'starting']:
                    _instances.append({'instance-id': host['InstanceId'], 'state': host['State']['Name']})
                    inst = self._descibe_instance(host_from_response=host)
                    continue
        return _instances

    def describe(self):
        _instances = []
        _app_hosts = self.client.describe_instances(
            Filters=[
                { 'Name': f"tag:{QHC.DEFAULT_APP_NAME}", 'Values': [ self.app_name, ] },
            ],
            DryRun=False,
            MaxResults=100,
        )
        store_test_data(resource='AWSHost', action='describe', response_data=quickhost.convert_datetime_to_string(_app_hosts))
        for r in _app_hosts['Reservations']:
            for host in r['Instances']:
                if host['State']['Name'] in ['running', 'pending']:
                    #_instances.append(host['InstanceId'])
                    #inst = self.get_hosts_for_app(app_name=self.app_name)
                    _instances.append(self._descibe_instance(host_from_response=host))
                    continue
        self.app_instances = _instances
        return _instances


    def create(self, num_hosts, instance_type, sgid, subnet_id, userdata, key_name, dry_run=False, image_id=AWS.DEFAULT_HOST_OS):
        ## this was moved from __init__ after causing describe() problems
        if image_id is None:
            print("No ami specified, getting latest al2...", end='')
            image_id = self.get_latest_image()
            print("Done. ({image_id})")
        ##
        print(f"starting hosts...")
        _run_instances_params = {
            'ImageId': image_id,
            'InstanceType': instance_type,
            'KeyName': key_name,
            'Monitoring':{ 'Enabled': False },
            'MaxCount':int(num_hosts),
            'MinCount':1,
            'DisableApiTermination':False,
            'DryRun':dry_run,
            'InstanceInitiatedShutdownBehavior':'terminate',
            'NetworkInterfaces':[
                {
                    'AssociatePublicIpAddress': True,
                    'DeviceIndex': 0,
                    'SubnetId': subnet_id,
                    'Groups': [
                        sgid
                    ],
                }
            ],
            'TagSpecifications':[
                {
                    'ResourceType': 'instance',
                    'Tags': [
                        { 'Key': QHC.DEFAULT_APP_NAME, 'Value': self.app_name},
                    ]
                },
            ],
        }
        if userdata:
            _run_instances_params['UserData'] = self.get_userdata(userdata)
        response = self.client.run_instances(**_run_instances_params)
        r_cleaned = quickhost.convert_datetime_to_string(response)
        store_test_data(resource='AWSHost', action='create', response_data=r_cleaned)
        return response

    def get_userdata(self, filename: str):
        data=None
        with open(filename, 'r') as ud:
            data = ud.read()
        return data

    def wait_for_hosts(self, num_hosts):
        """'blocks' until a the specified hosts tagged as 'app_name' have a State Name of 'running'"""
        print(f"===================Waiting on hosts for '{self.app_name}'=========================")
        while True:
            _waiting_on_hosts = []
            _running_hosts = []
            _other_hosts = []
            _app_hosts = quickhost.convert_datetime_to_string(self.client.describe_instances(
                Filters=[
                    { 'Name': f"tag:{QHC.DEFAULT_APP_NAME}", 'Values': [ self.app_name, ] },
                    { 'Name': f"instance-state-name", 'Values': ['pending', 'running'] },
                ],
                DryRun=False,
                MaxResults=10,
            ))
            for r in _app_hosts['Reservations']:
                for i,host in enumerate(r['Instances']):
                    if host['State']['Name'] in ['running', ]:
                        if not (host['InstanceId'] in _running_hosts):
                            self.app_instances.append(self._descibe_instance(host))
                            _running_hosts.append(host['InstanceId'])
                    elif host['State']['Name'] in ['pending']:
                        if not (host['InstanceId'] in _waiting_on_hosts):
                            _waiting_on_hosts.append(host['InstanceId'])
                    else:
                        if not (host['InstanceId'] in _other_hosts):
                            _other_hosts.append(host['InstanceId'])
            print(f"""({len(_running_hosts)}/{num_hosts}) Running: {_running_hosts} Waiting ({len(_waiting_on_hosts)}): {[l for l in _waiting_on_hosts]}\r""", end='')
            if num_hosts == len(_running_hosts):
                print()
                break
            time.sleep(1)
        return self.app_instances 


    def get_ssh(self):
        _app_hosts = self.client.describe_instances(
            Filters=[
                { 'Name': f"tag:{QHC.DEFAULT_APP_NAME}", 'Values': [ self.app_name, ] },
                { 'Name': f"state", 'Values': ['running'] },
            ],
            DryRun=False,
            MaxResults=10,
        )
        print(f"ssh -i {self.key_name} ec2-user@{_app_hosts['PublicIpAddress']}")
        

