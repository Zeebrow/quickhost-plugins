from typing import List, Any
import time
import logging
import json
from datetime import datetime
from copy import copy
from collections import defaultdict

import boto3
from botocore.exceptions import ClientError

import quickhost
from quickhost import APP_CONST as QHC
from quickhost.temp_data_collector import store_test_data

from .AWSSG import SG
from .constants import AWSConstants
from .AWSResource import AWSResourceBase
from .AWSConfig import AWSHostConfig


logger = logging.getLogger(__name__)

class AWSHost(AWSResourceBase):
    """
    Class for AWS host operations.
    """
    def __init__(self, app_name, profile, region):
        self._client_caller_info, self.client = self.get_client('ec2', profile=profile, region=region)
        self._resource_caller_info, self.ec2 = self.get_resource('ec2', profile=profile, region=region)
        if self._client_caller_info == self._resource_caller_info:
            self.caller_info = self._client_caller_info
        self.app_name=app_name
        self.host_count = None

    def create(self, num_hosts, instance_type, sgid, subnet_id, userdata, key_name, _os, dry_run=False):
        image_id = self.get_latest_image(_os)
        self.host_count = num_hosts
        if self.get_host_count() > 0:
            logger.error(f"Hosts for app '{self.app_name}' already exist")
            return False
        run_instances_params = {
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
                    'Groups': [ sgid ],
                }
            ],
            'TagSpecifications':[
                { 'ResourceType': 'instance', 'Tags': [
                    { 'Key': QHC.DEFAULT_APP_NAME, 'Value': self.app_name}, 
                    { 'Key': "Name", 'Value': self.app_name}, 
                ]},
                { 'ResourceType': 'volume', 'Tags': [
                    { 'Key': QHC.DEFAULT_APP_NAME, 'Value': self.app_name}, 
                ]},
            ],
        }
        if userdata:
            run_instances_params['UserData'] = self.get_userdata(userdata)
        response = self.client.run_instances(**run_instances_params)
        r_cleaned = quickhost.scrub_datetime(response)
        store_test_data(resource='AWSHost', action='create', response_data=r_cleaned)
        self.wait_for_hosts_to_start(num_hosts)
        ssh_strings = []
        app_insts_thingy = self._get_app_instances()
        for i in app_insts_thingy:
            inst = self._parse_host_output(i)
            logger.debug(f"match {_os}") 
            match _os:
                case "ubuntu":
                        ssh_strings.append(f"ssh -i {key_name} ubuntu@{inst['public_ip']}")
                case "amazon-linux-2":
                        ssh_strings.append(f"ssh -i {key_name} ec2-user@{inst['public_ip']}")
                case "windows":
                        ssh_strings.append(f"*{inst['public_ip']}")
                case "windows-core":
                        ssh_strings.append(f"*{inst['public_ip']}")
                case _:
                    logger.warning(f"invalid os '{_os}'") 
        [ print(f"host {i}) {ssh}") for i,ssh in enumerate(ssh_strings) ]
        return True

    def describe(self) -> List[Any] | None:
        logger.debug("AWSHost.describe")
        instances = []
        try: 
            app_hosts = self.client.describe_instances(
                Filters=[
                    { 'Name': f"tag:{QHC.DEFAULT_APP_NAME}", 'Values': [ self.app_name, ] },
                    { 'Name': 'instance-state-name', 'Values': ['running', 'pending']},
                ],
                DryRun=False,
                MaxResults=10,
            )
            store_test_data(resource='AWSHost', action='describe_instances', response_data=quickhost.scrub_datetime(app_hosts))
            for r in app_hosts['Reservations']:
                for host in r['Instances']:
                    if host['State']['Name'] in ['running', 'pending']:
                        instances.append(self._parse_host_output(host=host))
        except ClientError as e:
            logger.error(f"(Security Group) Unhandled botocore client exception: ({e.response['Error']['Code']}): {e.response['Error']['Message']}")
            raise e
        if len(instances) == 0:
            return None
        else:
            return instances

    def destroy(self) -> bool:
        logger.debug(f"destroying instnaces: ")
        tgt_instances = self.get_instance_ids('running')
        if tgt_instances is None:
            logger.debug(f"No instances found for app '{self.app_name}'")
            return None
        try:
            response = self.client.terminate_instances(
                InstanceIds=tgt_instances
            )
            store_test_data(resource='AWSHost', action='terminate_instances', response_data=quickhost.scrub_datetime(response))
        except ClientError as e:
            logger.error(e)
            return False
        return self.wait_for_hosts_to_terminate(tgt_instances=tgt_instances)
    
    @classmethod
    def get_all_running_apps(self, region) -> List[Any] | None:
        dummy_awshost_instance_client = AWSHost(
            app_name='list-all',
            profile=AWSConstants.DEFAULT_IAM_USER,
            region=region,
        ).get_client(
            "ec2", 
            profile=AWSConstants.DEFAULT_IAM_USER,
            region=region,
        )[1]
        all_running_hosts = dummy_awshost_instance_client.describe_instances( 
            Filters=[
                { 'Name': f"tag-key", 'Values': [QHC.DEFAULT_APP_NAME] },
                { 'Name': 'instance-state-name', 'Values': ['running']},
            ],
            DryRun=False,
            MaxResults=101,
        )
        app_names = []
        for r in all_running_hosts['Reservations']:
            for host in r['Instances']:
                for t in host['Tags']:
                    if t['Key'] == 'Name':
                        app_names.append(t['Value'])
        if len(app_names) == 0:
            return None
        else:
            app_name_count = defaultdict(int)
            for app_name in app_names:
                app_name_count[app_name] += 1
            _rtn = []
            for k,v in app_name_count.items():
                if v >1:
                    _rtn.append("{} ({})".format(k, v))
                else:
                    _rtn.append(k)
            return _rtn 

    def _get_app_instances(self) -> List[Any] | None:
        """
        TODO: Create a type to replace List[Any]
        NOTE: to get 'describe' data, feed the output of this into self._parse_host_output()
        """
        app_instances = []
        all_hosts = self.client.describe_instances(
            Filters=[
                { 'Name': f"tag:{QHC.DEFAULT_APP_NAME}", 'Values': [ self.app_name, ] },
                { 'Name': 'instance-state-name', 'Values': ['running']},
            ],
            DryRun=False,
            MaxResults=10,
        )
        instance_ids = []
        for r in all_hosts['Reservations']:
            for host in r['Instances']:
                app_instances.append(quickhost.scrub_datetime(host))
                inst = self._parse_host_output(host=host)
                instance_ids.append(inst['instance_id'])
        if len(app_instances) == 0:
            return None
        else:
            return app_instances

    def get_instance_ids(self, *states):
        """Given the app_name, returns the instance id off all instances with a State of 'running'"""
        logger.debug(f"{states=}")
        app_instances = []
        all_hosts = self.client.describe_instances(
            Filters=[
                { 'Name': f"tag:{QHC.DEFAULT_APP_NAME}", 'Values': [ self.app_name, ] },
                { 'Name': 'instance-state-name', 'Values': list(states)},
            ],
            DryRun=False,
            MaxResults=10,
        )
        store_test_data(resource='AWSHost', action='describe_instances', response_data=quickhost.scrub_datetime(all_hosts))
        # fishy
        instance_ids = []
        for r in all_hosts['Reservations']:
            for host in r['Instances']:
                if host['State']['Name'] in states:
                    app_instances.append(quickhost.scrub_datetime(host))
                    inst = self._parse_host_output(host=host)
                    instance_ids.append(inst['instance_id'])
        if instance_ids == []:
            return None
        return instance_ids

    def get_latest_image(self, os='amazon-linux-2'):
        """
        NOTE: (us-east-1, 12/19/2022) Free tier eligible customers can get up to 30 GB of 
        EBS General Purpose (SSD) or Magnetic storage
        """
        filterset = [
            _new_filter('state', 'available'),
            _new_filter('architecture', 'x86_64'),
        ]
        match os:
            case 'amazon-linux-2':
                filterset.append(_new_filter('name', 'amzn2-ami-hvm-2.0.*-x86_64-gp2'),)
            case 'ubuntu':
                filterset.append(_new_filter('name', '*ubuntu*22.04*'),)
            case 'windows':
                filterset.append(_new_filter('name', 'Windows_Server-2022-English-Full-Base*'),)
            case 'windows-core':
                filterset.append(_new_filter('name', 'Windows_Server-2022-English-Core-Base*'),)
            case _:
                raise Exception(f"no such image type '{os}'")
        response = self.client.describe_images(
            Filters=filterset,
            IncludeDeprecated=False,
            DryRun=False
        )
        sortedimages = sorted(response['Images'], key=lambda x: datetime.strptime(x['CreationDate'], '%Y-%m-%dT%H:%M:%S.%fZ'))
        return sortedimages[-1]['ImageId']

    def _parse_host_output(self, host: dict, none_val=None):
        """
        Parse the output of boto3's "ec2.describe_instances()" Reservations.Instances for data. 
        If a property cannot be retrieved, it will be replaced with `none_val`.
        """
        none_val = None
        _try_get_attr = lambda d,attr: d[attr] if attr in d.keys() else none_val
        return {
            'app_name': self.app_name,
            'ami': _try_get_attr(host,'ImageId'),
            'security_group': _try_get_attr(host,'SecurityGroups')[0]['GroupId'],
            'instance_id': _try_get_attr(host,'InstanceId'),
            'instance_type': _try_get_attr(host,'InstanceType'),
            'public_ip': _try_get_attr(host,'PublicIpAddress'),
            'subnet_id': _try_get_attr(host,'SubnetId'),
            'vpc_id': _try_get_attr(host,'VpcId'),
            'state': host['State']['Name'],
            'platform': _try_get_attr(host,'PlatformDetails'),
        }

    def get_userdata(self, filename: str):
        data=None
        with open(filename, 'r') as ud:
            data = ud.read()
        return data

    def get_host_count(self):
        app_hosts = quickhost.scrub_datetime(self.client.describe_instances(
            Filters=[
                { 'Name': f"tag:{QHC.DEFAULT_APP_NAME}", 'Values': [ self.app_name, ] },
                { 'Name': f"instance-state-name", 'Values': ['running'] },
            ],
            DryRun=False,
            MaxResults=10,
        ))
        count = 0
        for r in app_hosts['Reservations']:
            logger.debug(f"got {len(r['Instances'])} instances")
            for i,host in enumerate(r['Instances']):
                if host['State']['Name'] == 'running':
                    count += 1
        return count
        
    def wait_for_hosts_to_terminate(self, tgt_instances):
        """'blocks' until hosts tagged 'app_name' have a State Name of 'running'"""
        print(f"===================Waiting on hosts for '{self.app_name}'=========================")
        ready_hosts = []
        waiting_on_hosts = []
        other_hosts = []
        tgt_count = len(tgt_instances)
        while True:
            app_hosts = quickhost.scrub_datetime(self.client.describe_instances(
                Filters=[
                    { 'Name': f"tag:{QHC.DEFAULT_APP_NAME}", 'Values': [ self.app_name, ] },
                    { 'Name': f"instance-state-name", 'Values': ['running', 'terminated', 'shutting-down'] },
                ],
                DryRun=False,
                MaxResults=10,
            ))
            for r in app_hosts['Reservations']:
                for host in r['Instances']:
                    if host['InstanceId'] in tgt_instances:
                        match host['State']['Name']:
                            case 'terminated':
                                if not (host['InstanceId'] in ready_hosts):
                                    ready_hosts.append(host['InstanceId'])
                            case 'shutting-down':
                                if not (host['InstanceId'] in waiting_on_hosts):
                                    waiting_on_hosts.append(host['InstanceId'])
                            case _:
                                if not (host['InstanceId'] in other_hosts):
                                    other_hosts.append(host['InstanceId'])
                                #@@@
            print(f"""other: {other_hosts} ({len(ready_hosts)}/{tgt_count}) Ready: {ready_hosts} Waiting: {waiting_on_hosts}\r""", end='')
            if len(ready_hosts) == tgt_count:
                print()
                return True
            time.sleep(1)

    def wait_for_hosts_to_start(self, tgt_count):
        """loops until a the specified hosts tagged as 'app_name' have a State Name of 'running'"""
        print(f"===================Waiting on hosts for '{self.app_name}'=========================")
        ready_hosts = []
        waiting_on_hosts = []
        other_hosts = []
        while True:
            if len(ready_hosts) == int(tgt_count):
                print()
                return True
            app_hosts = quickhost.scrub_datetime(self.client.describe_instances(
                Filters=[
                    { 'Name': f"tag:{QHC.DEFAULT_APP_NAME}", 'Values': [ self.app_name, ] },
                    { 'Name': f"instance-state-name", 'Values': ['running', 'pending'] },
                ],
                DryRun=False,
                MaxResults=10,
            ))
            for r in app_hosts['Reservations']:
                for host in r['Instances']:
                    match host['State']['Name']:
                        case 'running':
                            if not (host['InstanceId'] in ready_hosts):
                                if host['InstanceId'] in waiting_on_hosts: #should always be True
                                    ready_hosts.append(host['InstanceId'])
                                    waiting_on_hosts.remove(host['InstanceId'])
                        case 'pending':
                            if not (host['InstanceId'] in waiting_on_hosts):
                                waiting_on_hosts.append(host['InstanceId'])
                        case _:
                            if not (host['InstanceId'] in other_hosts):
                                print(f"host {host['InstanceId']} in state {host['State']['Name']}")
                                logger.debug("HERE BUG")
                                other_hosts.append(host['InstanceId'])
                            #@@@
            print(f"""other: {other_hosts} ({len(ready_hosts)}/{tgt_count}) Ready: {ready_hosts} Waiting: ({len(waiting_on_hosts)}): {waiting_on_hosts}\r""", end='')
            time.sleep(1)

def _new_filter(name: str, values: list|str):
    if (type(values) == type("")):
        return {'Name': name, 'Values': [values]}
    elif (type(values) == type([])):
        return {'Name': name, 'Values': values}
    else:
        raise Exception(f"invalid type '{type(values)}' in filter expression")