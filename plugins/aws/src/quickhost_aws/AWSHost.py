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

class HostState:
    running = 'running'
    pending = 'pending' 
    shutting_down = 'shutting-down' 
    terminated = 'terminated' 
    stopping = 'stopping' 
    stopped = 'stopped' 

    # @@@TODO: dunders?
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

    # @@@TODO: dunders?
    @classmethod
    def butnot(self,*states):
        rtn = list(HostState.allofem())
        [rtn.remove(i) for i in states]
        return rtn


class AWSHost:
    def __init__(self, client: any, ec2_resource, app_name):
        self.client = client
        self.ec2 = ec2_resource
        self.app_name=app_name
        self.host_count = None

    def create(self, num_hosts, instance_type, sgid, subnet_id, userdata, key_name, dry_run=False, image_id=AWS.DEFAULT_HOST_OS):
        ## this was moved from __init__ after causing describe() problems
        self.get_host_count()
        if self.get_host_count() > 0:
            logger.error(f"Hosts for app '{self.app_name}' already exist")
            return False
        if image_id is None:
            print("No ami specified, getting latest al2...", end='')
            image_id = self.get_latest_image()
            print("Done. ({image_id})")
        ##
        print(f"starting hosts...")
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
        r_cleaned = quickhost.convert_datetime_to_string(response)
        store_test_data(resource='AWSHost', action='create', response_data=r_cleaned)
        self.wait_for_hosts_to_start(tgt_count=num_hosts)
        return True

    def describe(self):
        instances = []
        app_hosts = self.client.describe_instances(
            Filters=[
                { 'Name': f"tag:{QHC.DEFAULT_APP_NAME}", 'Values': [ self.app_name, ] },
                { 'Name': 'instance-state-name', 'Values': [HostState.running, HostState.pending]},
            ],
            DryRun=False,
            MaxResults=10,
        )
        store_test_data(resource='AWSHost', action='describe', response_data=quickhost.convert_datetime_to_string(app_hosts))
        for r in app_hosts['Reservations']:
            for host in r['Instances']:
                if host['State']['Name'] in ['running', 'pending']:
                    instances.append(self._descibe_instance(host=host))
        self.app_instances = instances
        return instances

    def destroy(self):
        logger.debug(f"destroying instnaces: ")
        tgt_instances = self.get_instance_ids(HostState.running)
        if tgt_instances is None:
             logger.debug(f"No instances found for app '{self.app_name}'")
             return None
        response = self.client.terminate_instances(
            InstanceIds=tgt_instances
        )
        self.wait_for_hosts_to_terminate(tgt_instances=tgt_instances)
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
        store_test_data(resource='AWSHost', action='describe', response_data=quickhost.convert_datetime_to_string(all_hosts))
        # fishy
        instance_ids = []
        for r in all_hosts['Reservations']:
            for host in r['Instances']:
                if host['State']['Name'] in states:
                    #running_instances.append({'instance-id': host['InstanceId'], 'state': host['State']['Name']})
                    app_instances.append(quickhost.convert_datetime_to_string(host))
                    inst = self._descibe_instance(host=host)
                    print(json.dumps(inst))
                    instance_ids.append(inst['instance_id'])
                    continue
        if instance_ids == []:
            return None
        return instance_ids

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

    def _descibe_instance(self, host: dict):
        noneval = None
        _try_get_attr = lambda d,attr: noneval if not attr in d.keys() else d[attr]

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
#        return {
#            'app_name': self.app_name,
#            'ami': host_from_response['ImageId'],
#            'instance_id': host_from_response['InstanceId'],
#            'instance_type': host_from_response['InstanceType'],
#            'public_ip': host_from_response['PublicIpAddress'],
#            'subnet_id': host_from_response['SubnetId'],
#            'vpc_id': host_from_response['VpcId'],
#            '_state': host_from_response['State']['Name'],
#            '_platform': host_from_response['PlatformDetails'],
#        }

    def get_userdata(self, filename: str):
        data=None
        with open(filename, 'r') as ud:
            data = ud.read()
        return data

    def get_host_count(self):
        if self.host_count is not None:
            logger.debug(f"got self.host_count")
            return self.host_count 
        else:
            app_hosts = quickhost.convert_datetime_to_string(self.client.describe_instances(
                Filters=[
                    { 'Name': f"tag:{QHC.DEFAULT_APP_NAME}", 'Values': [ self.app_name, ] },
                    { 'Name': f"instance-state-name", 'Values': [HostState.running] },
                ],
                DryRun=False,
                MaxResults=10,
            ))
            count = 0
            print(f"{len(app_hosts['Reservations'])=}")
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
        done = False
        while not done:
            app_hosts = quickhost.convert_datetime_to_string(self.client.describe_instances(
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
                return done
            time.sleep(1)
        return done

    def wait_for_hosts_to_start(self, tgt_count):
        """'blocks' until a the specified hosts tagged as 'app_name' have a State Name of 'running'"""
        print(f"===================Waiting on hosts for '{self.app_name}'=========================")
        #instances = []
        ready_hosts = []
        waiting_on_hosts = []
        other_hosts = []
        done = False
        while not done:
            app_hosts = quickhost.convert_datetime_to_string(self.client.describe_instances(
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
                return done
            time.sleep(1)
        return done

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
        
