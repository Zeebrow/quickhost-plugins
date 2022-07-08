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
from .AWSResource import AWSResourceBase
from .constants import AWSConstants

logger = logging.getLogger(__name__)

class HostState:
    running = 'running'
    pending = 'pending' 
    shutting_down = 'shutting-down' 
    terminated = 'terminated' 
    stopping = 'stopping' 
    stopped = 'stopped' 
    @classmethod
    def allofem(self):
        return [
            "running",
            "pending",
            "shutting_down",
            "terminated",
            "stopping",
            "stopped",
        ]
    @classmethod
    def butnot(self,*states):
        rtn = list(HostState.allofem())
        [rtn.remove(i) for i in states]
        return rtn


class AWSHost(AWSResourceBase):
    def __init__(
            self,
            app_name,
#            vpc_id,
#            subnet_id,
            profile=AWSConstants.DEFAULT_IAM_USER,
            region=AWSConstants.DEFAULT_REGION
        ): #sigh
        self._client_caller_info, self.client = self.get_client('ec2', profile=profile, region=region)
        self._resource_caller_info, self.ec2 = self.get_resource('ec2', profile=profile, region=region)
        if self._client_caller_info == self._resource_caller_info:
            self.caller_info = self._client_caller_info
        self.app_name=app_name
        self.host_count = None
#        self.vpc_id = vpc_id,
#        self.subnet_id = subnet_id,

    def create(self, num_hosts, instance_type, sgid, subnet_id, userdata, key_name, dry_run=False, image_id=AWS.DEFAULT_HOST_OS):
        self.host_count = num_hosts
        if self.get_host_count() > 0:
            logger.error(f"Hosts for app '{self.app_name}' already exist")
            return False
        if image_id is None:
            print("No ami specified, getting latest al2...", end='')
            image_id = self.get_latest_image()
            print("Done. ({image_id})")
        print()
        print(f"starting hosts...")
        print( "*****************")
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
                { 'ResourceType': 'instance', 'Tags': [ { 'Key': QHC.DEFAULT_APP_NAME, 'Value': self.app_name}, ] },
            ],
        }
        if userdata:
            run_instances_params['UserData'] = self.get_userdata(userdata)
        response = self.client.run_instances(**run_instances_params)
        r_cleaned = quickhost.scrub_datetime(response)
        store_test_data(resource='AWSHost', action='create', response_data=r_cleaned)
        self.wait_for_hosts_to_start(tgt_count=num_hosts)
        return True

    def describe(self):
        instances = []
        try: 
            app_hosts = self.client.describe_instances(
                Filters=[
                    { 'Name': f"tag:{QHC.DEFAULT_APP_NAME}", 'Values': [ self.app_name, ] },
                    { 'Name': 'instance-state-name', 'Values': [HostState.running, HostState.pending]},
                ],
                DryRun=False,
                MaxResults=10,
            )
            store_test_data(resource='AWSHost', action='describe', response_data=quickhost.scrub_datetime(app_hosts))
            for r in app_hosts['Reservations']:
                for host in r['Instances']:
                    if host['State']['Name'] in ['running', 'pending']:
                        instances.append(self._descibe_instance(host=host))
        except ClientError as e:
            logger.error(f"(Security Group) Unhandled botocore client exception: ({e.response['Error']['Code']}): {e.response['Error']['Message']}")
            raise e
        return instances

    def destroy(self):
        logger.debug(f"destroying instnaces: ")
        tgt_instances = self.get_instance_ids(HostState.running)
        if tgt_instances is None:
            logger.debug(f"No instances found for app '{self.app_name}'")
            return None
        try:
            response = self.client.terminate_instances(
                InstanceIds=tgt_instances
            )
            self.wait_for_hosts_to_terminate(tgt_instances=tgt_instances)
        except ClientError as e:
            logger.error(f"(Security Group) Unhandled botocore client exception: ({e.response['Error']['Code']}): {e.response['Error']['Message']}")
            raise e
        # {'TerminatingInstances': [{'CurrentState': {'Code': 32, 'Name': 'shutting-down'}, 'InstanceId': 'i-090ab1a37ba8583bd', 'PreviousState': {'Code': 16, 'Name': 'running'}}], 'ResponseMetadata': {'RequestId': 'bf923b37-a043-4150-8654-d4fcbca4b0bc', 'HTTPStatusCode': 200, 'HTTPHeaders': {'x-amzn-requestid': 'bf923b37-a043-4150-8654-d4fcbca4b0bc', 'cache-control': 'no-cache, no-store', 'strict-transport-security': 'max-age=31536000; includeSubDomains', 'vary': 'accept-encoding', 'content-type': 'text/xml;charset=UTF-8', 'transfer-encoding': 'chunked', 'date': 'Sun, 03 Jul 2022 00:31:55 GMT', 'server': 'AmazonEC2'}, 'RetryAttempts': 0}}
        print(f"{response=}")

    def get_instance_ids(self, *states): #state_list=[AWSHostState.running]) -> List[str]:
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
        store_test_data(resource='AWSHost', action='describe', response_data=quickhost.scrub_datetime(all_hosts))
        # fishy
        instance_ids = []
        for r in all_hosts['Reservations']:
            for host in r['Instances']:
                if host['State']['Name'] in states:
                    #running_instances.append({'instance-id': host['InstanceId'], 'state': host['State']['Name']})
                    app_instances.append(quickhost.scrub_datetime(host))
                    inst = self._descibe_instance(host=host)
                    print(json.dumps(inst))
                    instance_ids.append(inst['instance_id'])
                    continue
        if instance_ids == []:
            return None
        return instance_ids

    def get_latest_image(self, os=QHC.DEFAULT_APP_NAME):
        """
        Get the latest amazon linux 2 ami
        TODO: see source-aliases and make an Ubuntu option
        """
        response = self.client.describe_images(
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

    def _descibe_instance(self, host: dict, none_val=None):
        """
        get the pertinent data to one of the hosts in an app
        If a property cannot be retrieved, it will be replaced with `none_val`.
        """
        none_val = None
        _try_get_attr = lambda d,attr: none_val if not attr in d.keys() else d[attr]
        return {
            'app_name': self.app_name,
            'ami': _try_get_attr(host,'ImageId'),
            'instance_id': _try_get_attr(host,'InstanceId'),
            'instance_type': _try_get_attr(host,'InstanceType'),
            'public_ip': _try_get_attr(host,'PublicIpAddress'),
            'subnet_id': _try_get_attr(host,'SubnetId'),
            'vpc_id': _try_get_attr(host,'VpcId'),
            '_state': host['State']['Name'],
            '_platform': _try_get_attr(host,'PlatformDetails'),
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
                { 'Name': f"instance-state-name", 'Values': [HostState.running] },
            ],
            DryRun=False,
            MaxResults=10,
        ))
        count = 0
        for r in app_hosts['Reservations']:
            logger.debug(f"got {len(r['Instances'])} instances")
            for i,host in enumerate(r['Instances']):
                if host['State']['Name'] == HostState.running:
                    count += 1
        return count
        
    def wait_for_hosts_to_terminate(self, tgt_instances):
        """'blocks' until a the specified hosts tagged as 'app_name' have a State Name of 'running'"""
        print(f"===================Waiting on hosts for '{self.app_name}'=========================")
        #instances = []
        ready_hosts = []
        waiting_on_hosts = []
        other_hosts = []
        tgt_count = len(tgt_instances)
        while not True:
            app_hosts = quickhost.scrub_datetime(self.client.describe_instances(
                Filters=[
                    { 'Name': f"tag:{QHC.DEFAULT_APP_NAME}", 'Values': [ self.app_name, ] },
                    { 'Name': f"instance-state-name", 'Values': [HostState.terminated, HostState.shutting_down] },
                ],
                DryRun=False,
                MaxResults=10,
            ))
            for r in app_hosts['Reservations']:
                for i,host in enumerate(r['Instances']):
                    if host['InstanceId'] in tgt_instances:
                        if host['State']['Name'] == HostState.terminated:
                            if not (host['InstanceId'] in ready_hosts):
                                #instances.append(self._descibe_instance(host))
                                ready_hosts.append(host['InstanceId'])
                        elif host['State']['Name'] == HostState.shutting_down:
                            if not (host['InstanceId'] in waiting_on_hosts):
                                waiting_on_hosts.append(host['InstanceId'])
                        else:
                            if not (host['InstanceId'] in other_hosts):
                                logger.debug("Y U HERE BUG")
                                other_hosts.append(host['InstanceId'])
            print(f"""({len(ready_hosts)}/{tgt_count}) Ready ({len(ready_hosts)}): {ready_hosts} Waiting: ({len(waiting_on_hosts)}): {[l for l in waiting_on_hosts]}\r""", end='')
            if tgt_count == len(ready_hosts):
                print()
                return True
            time.sleep(1)
        return False

    def wait_for_hosts_to_start(self, tgt_count):
        """'blocks' until a the specified hosts tagged as 'app_name' have a State Name of 'running'"""
        print(f"===================Waiting on hosts for '{self.app_name}'=========================")
        #instances = []
        ready_hosts = []
        waiting_on_hosts = []
        other_hosts = []
        while True:
            app_hosts = quickhost.scrub_datetime(self.client.describe_instances(
                Filters=[
                    { 'Name': f"tag:{QHC.DEFAULT_APP_NAME}", 'Values': [ self.app_name, ] },
                    { 'Name': f"instance-state-name", 'Values': [HostState.running, HostState.pending] },
                ],
                DryRun=False,
                MaxResults=10,
            ))
            for r in app_hosts['Reservations']:
                for i,host in enumerate(r['Instances']):
                    if host['State']['Name'] == HostState.running:
                        if not (host['InstanceId'] in ready_hosts):
                            #instances.append(self._descibe_instance(host))
                            ready_hosts.append(host['InstanceId'])
                    elif host['State']['Name'] == HostState.pending:
                        if not (host['InstanceId'] in waiting_on_hosts):
                            waiting_on_hosts.append(host['InstanceId'])
                    else:
                        if not (host['InstanceId'] in other_hosts):
                            logger.debug("Y U HERE BUG")
                            other_hosts.append(host['InstanceId'])
            print(f"""({len(ready_hosts)}/{tgt_count}) Ready: {ready_hosts} Waiting: ({len(waiting_on_hosts)}): {[l for l in waiting_on_hosts]}\r""", end='')
            if tgt_count == len(ready_hosts):
                print()
                return True
            time.sleep(1)
        return False

