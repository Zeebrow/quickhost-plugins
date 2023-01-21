import logging
import json
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

import quickhost as qh
from quickhost import APP_CONST as C, store_test_data, scrub_datetime

from .utilities import get_single_result_id, check_running_as_user, QuickhostUnauthorized, quickmemo
from .constants import AWSConstants
from .AWSResource import AWSResourceBase


logger = logging.getLogger(__name__)

class AWSNetworking(AWSResourceBase):
    DefaultFilter = { 'Name': 'tag:Name', 'Values': [ C.DEFAULT_APP_NAME ] }
    DefaultTag = { 'Value': f"{C.DEFAULT_APP_NAME}", 'Key': 'Name' }
    TagSpec = lambda resource: { 'ResourceType': resource, 'Tags': [ AWSNetworking.DefaultTag ] }

    def __init__(self, app_name, profile, region, dry_run=False):
        self.app_name = app_name
        self._client_caller_info, self.client = self.get_client('ec2', profile=profile, region=region)
        self._resource_caller_info, self.ec2 = self.get_resource('ec2', profile=profile, region=region)
        if self._client_caller_info == self._resource_caller_info:
            self.caller_info = self._client_caller_info
        self.dry_run = dry_run
        self.vpc_id = None
        self.igw_id = None
        self.subnet_id = None
        self.rt_id = None

    def create(self, cidr_block=C.DEFAULT_VPC_CIDR):
        self.__dict__.update(self.describe())
        ####################################################
        # vpc
        ####################################################
        vpc = None 
        if not self.vpc_id:
            logger.debug("creating vpc...")
            vpc = self.ec2.create_vpc(
                CidrBlock=cidr_block,
                DryRun=self.dry_run,
                TagSpecifications=[ AWSNetworking.TagSpec('vpc'), ]
            )
            vpc.wait_until_available()
            vpc.create_tags(Tags=[AWSNetworking.DefaultTag])
            self.vpc_id = vpc.id
            vpc.reload()
            logger.info(f"Created VPC: {self.vpc_id}")
        else:
            logger.warning(f"Found existing vpc: {self.vpc_id}")
            vpc = self.ec2.Vpc(self.vpc_id)

        ####################################################
        # igw
        ####################################################
        igw = None
        igw_status = 'Not OK'
        if not self.igw_id:
            logger.debug("creating igw...")
            igw_id = self.client.create_internet_gateway(
                DryRun=self.dry_run,
                TagSpecifications=[ AWSNetworking.TagSpec('internet-gateway'), ]
            )
            self.igw_id = get_single_result_id("InternetGateway", igw_id, plural=False)
            igw = self.ec2.InternetGateway(self.igw_id)
            logger.debug(f"...attaching igw ({self.igw_id}) to vpc ({self.vpc_id})...")
            igw.attach_to_vpc(DryRun=False, VpcId=self.vpc_id)
            igw.reload()
            logger.info(f"Created Internet Gateway: {self.igw_id}")
        else:
            logger.debug(f"Have igw: {self.igw_id}")
            igw_status = 'Check attachment'
            igw = self.ec2.InternetGateway(self.igw_id)
            # fixes attachment issue
            if len(igw.attachments) == 0:
                igw.attach_to_vpc(DryRun=False, VpcId=self.vpc_id)
                igw.reload()
            if len(igw.attachments) == 1 and igw.attachments[0]['VpcId'] == self.vpc_id:
                igw_status = f"Attached to vpc {self.vpc_id}"
            logger.warning(f"Found existing internet gateway with id: {self.igw_id} ({igw_status})")

        ####################################################
        # subnet
        ####################################################
        subnet = None
        if not self.subnet_id:
            logger.debug("creating subnet...")
            subnet = vpc.create_subnet(
                CidrBlock=C.DEFAULT_SUBNET_CIDR,
                VpcId=self.vpc_id,
                DryRun=self.dry_run,
                TagSpecifications=[ AWSNetworking.TagSpec('subnet'), ]
            )
            subnet.create_tags(Tags=[AWSNetworking.DefaultTag])
            self.subnet_id = subnet.id
            subnet.reload()
            logger.info(f"Created subnet: {self.subnet_id}")
        else:
            logger.warning(f"Found existing subnet: {self.subnet_id}")
            subnet = self.ec2.Subnet(self.subnet_id)

        ####################################################
        # route-table
        ####################################################
        rt_ok = 'Not OK'
        route_table = None
        if not self.rt_id:
            logger.debug("creating route table...")
            route_table = vpc.create_route_table(
                VpcId=self.vpc_id,
                DryRun=self.dry_run,
                TagSpecifications=[ AWSNetworking.TagSpec('route-table'), ]
            )
            logger.debug(f"creating route for igw ({self.igw_id})..")
            route = route_table.create_route(
                DestinationCidrBlock='0.0.0.0/0',
                DryRun=False,
                GatewayId=self.igw_id,
                # neat
                #NetworkInterfaceId='string',
            )
            self.rt_id = route_table.id
            rt_ok = 'Check association'
            logger.debug(f"associating route table ({self.rt_id}) with subnet ({self.subnet_id})...")
            route_table_association = route_table.associate_with_subnet(
                DryRun=False,
                SubnetId=self.subnet_id,
            )
            route_table.reload()
            if route_table.associations_attribute[0]['SubnetId']  == self.subnet_id and route_table.associations_attribute[0]['AssociationState']['State'] == "associated":
                rt_ok = f"Associated with subnet {self.subnet_id}"
            logger.info(f"Created Route Table. {self.rt_id=} ({rt_ok})")
        else:
            rt_ok = 'Check association'
            route_table = self.ec2.RouteTable(self.rt_id)
            if len(route_table.associations_attribute) == 0:
                route_table_association = route_table.associate_with_subnet(
                    DryRun=False,
                    SubnetId=self.subnet_id,
                )
                route_table.reload()
                rt_ok = 'ok'
            if route_table.associations_attribute[0]['SubnetId']  == self.subnet_id and route_table.associations_attribute[0]['AssociationState']['State'] == "associated":
                rt_ok = f"Associated with subnet {self.subnet_id}"
            logger.warning(f"Found existing route table: {self.rt_id} ({rt_ok})")
        # rt = self.ec2.RouteTable(self.rt_id)
        return {
            "vpc_id": self.vpc_id,
            "subnet_id": self.subnet_id,
            "rt_id": self.rt_id,
            "igw_id": self.igw_id,
        }

    @quickmemo
    def describe(self, use_cache=True):
        logger.debug("AWSNetworking.describe")
        try: 
            # permissions exceptions are normally caught in AWSApp.py
            # these are special because they are called for all actions
            existing_vpcs = self.client.describe_vpcs( Filters=[ AWSNetworking.DefaultFilter ],)
            vpc_id = get_single_result_id("Vpc", existing_vpcs)
            existing_subnets = self.client.describe_subnets( Filters=[ AWSNetworking.DefaultFilter ],)
            subnet_id = get_single_result_id("Subnet",existing_subnets)
            store_test_data(resource='AWSNetworking', action='describe_vpcs', response_data=scrub_datetime(existing_vpcs))
            store_test_data(resource='AWSNetworking', action='describe_subnets', response_data=scrub_datetime(existing_subnets))
        except ClientError as e:
            code = e.response['Error']['Code']
            if code == 'UnauthorizedOperation' or code == 'AccessDenied':
                logger.critical(f"The user {self.caller_info['username']} couldn't perform the operation '{e.operation_name}'.")
                raise QuickhostUnauthorized(username=self.caller_info['username'], operation=e.operation_name) 
        existing_igws = self.client.describe_internet_gateways( Filters=[ AWSNetworking.DefaultFilter ],)
        igw_id = get_single_result_id("InternetGateway",existing_igws)
        if igw_id is not None:
            igw = self.ec2.InternetGateway(igw_id)
            if igw.attachments == []:
                logger.warn(f"Internet Gateway '{igw_id}' is not attached to a vpc!")
            else:
                if igw.attachments[0]['VpcId'] != vpc_id:
                    logger.error(f"Internet Gateway '{igw_id}' is not attached to the correct vpc!")
        existing_rts = self.client.describe_route_tables( Filters=[ AWSNetworking.DefaultFilter ],)
        rt_id = get_single_result_id("RouteTable",existing_rts)
        store_test_data(resource='AWSNetworking', action='describe_route_tables', response_data=scrub_datetime(existing_rts))
        store_test_data(resource='AWSNetworking', action='describe_internet_gateways', response_data=scrub_datetime(existing_igws))
        return {
            "vpc_id": vpc_id,
            "subnet_id": subnet_id,
            "rt_id": rt_id,
            "igw_id": igw_id,
        }
        
    def destroy(self):
        """
        Destroy all networking-related AWS resources. Requires that no apps be running.
        - Dissociate and delete route table
        - Detatch and delete internet gateway
        - Delete subnet
        - Delete VPC
        """
        self.__dict__.update(self.describe())
        print(self.describe())
        if self.rt_id:
            rt = self.ec2.RouteTable(self.rt_id)
            rt_assoc_ids = [rtid['RouteTableAssociationId'] for rtid in rt.associations_attribute]
            logger.debug(f"deleting {len(rt_assoc_ids)} associations on route table '{self.rt_id}'...")
            for rtai in rt_assoc_ids:
                self.ec2.RouteTableAssociation(rtai).delete(DryRun=False)
            logger.debug(f"deleting route table '{self.rt_id}'...")
            rt.delete(DryRun=False)
            
        if self.igw_id:
            igw = self.ec2.InternetGateway(self.igw_id)
            logger.debug(f"detaching igw '{self.igw_id}' from '{self.vpc_id}'...")
            igw.detach_from_vpc(
                DryRun=False,
                VpcId=self.vpc_id
            )
            logger.debug(f"deleting igw '{self.igw_id}'...")
            igw.delete(DryRun=False)
        if self.subnet_id:
            subnet = self.ec2.Subnet(self.subnet_id)
            logger.debug(f"deleting subnet '{self.subnet_id}'...")
            subnet.delete(DryRun=False)
        if self.vpc_id:
            logger.debug(f"deleting vpc '{self.vpc_id}'...")
            vpc = self.ec2.Vpc(self.vpc_id)
            vpc.delete(DryRun=False)
        logger.debug(f"Done.")

