import logging

import boto3

import quickhost
from quickhost import APP_CONST as C

logger = logging.getLogger(__name__)

class AWSVpc:
    DefaultFilter = { 'Name': 'tag:Name', 'Values': [ C.DEFAULT_APP_NAME ] }
    DefaultTag = { 'Value': f"{C.DEFAULT_APP_NAME}", 'Key': 'Name' }
    TagSpec = lambda resource: { 'ResourceType': resource, 'Tags': [ AWSVpc.DefaultTag ] }

    def __init__(self, app_name: str, client: boto3.client, dry_run=False):
        self.app_name = app_name
        self.client = client
        self.dry_run = dry_run
        self.vpc_id = None
        self.igw_id = None
        self.igw_ok = False
        self.subnet_id = None
        self.rt_id = None
        self.rt_ok = False

    def create(self, cidr_block=C.DEFAULT_VPC_CIDR):
        self.__dict__.update(self.get())
        ec2 = boto3.resource('ec2')

        vpc = None 
        if not self.vpc_id:
            logger.debug("creating vpc...")
            vpc = ec2.create_vpc(
                CidrBlock=cidr_block,
                DryRun=self.dry_run,
                TagSpecifications=[ AWSVpc.TagSpec('vpc'), ]
            )
            vpc.wait_until_available()
            vpc.create_tags(Tags=[AWSVpc.DefaultTag])
            self.vpc_id = vpc.id
            vpc.reload()
            logger.debug(f"Done. {self.vpc_id=}")
        else:
            logger.debug(f"Found existing vpc: {self.vpc_id}")
            vpc = ec2.Vpc(self.vpc_id)

        igw = None
        igw_ok = 'Not OK'
        if not self.igw_id:
            logger.debug("creating igw...")
            igw_id = self.client.create_internet_gateway(
                #VpcId=self.vpc_id,
                DryRun=self.dry_run,
                TagSpecifications=[ AWSVpc.TagSpec('internet-gateway'), ]
            )
            self.igw_id = _get_single_result_id("InternetGateway", igw_id, plural=False)
            igw = ec2.InternetGateway(self.igw_id)
            logger.debug(f"...attaching igw ({self.igw_id}) to vpc ({self.vpc_id})...")
            igw.attach_to_vpc(DryRun=False, VpcId=self.vpc_id)

            igw.reload()
            logger.debug(f"Done. {self.igw_id=}")
        else:
            igw_ok = 'Check attachment'
            igw = ec2.InternetGateway(self.igw_id)
            # Do we want to 'fix' the attachment?
#            if len(igw.attachments) == 0:
#                igw.attach_to_vpc(DryRun=False, VpcId=self.vpc_id)
#                igw.reload()
            if len(igw.attachments) == 1 and igw.attachments[0]['VpcId'] == self.vpc_id:
                igw_ok = f"Attached to vpc {self.vpc_id}"
            logger.debug(f"Found existing internet gateway with id: {self.igw_id} ({igw_ok})")

        subnet = None
        if not self.subnet_id:
            logger.debug("creating subnet...")
            subnet = vpc.create_subnet(
                CidrBlock=C.DEFAULT_SUBNET_CIDR,
                VpcId=self.vpc_id,
                DryRun=self.dry_run,
                TagSpecifications=[ AWSVpc.TagSpec('subnet'), ]
            )
            subnet.create_tags(Tags=[AWSVpc.DefaultTag])
            self.subnet_id = subnet.id
            subnet.reload()
            logger.debug(f"Done. {self.subnet_id=}")
        else:
            logger.debug(f"Found existing subnet: {self.subnet_id}")
            subnet = ec2.Subnet(self.subnet_id)

        rt_ok = 'Not OK'
        route_table = None
        if not self.rt_id:
            logger.debug("creating route table...")
            route_table = vpc.create_route_table(
                VpcId=self.vpc_id,
                DryRun=self.dry_run,
                TagSpecifications=[ AWSVpc.TagSpec('route-table'), ]
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
            logger.debug(f"Done. {self.rt_id=} ({rt_ok})")
        else:
            rt_ok = 'Check association'
            route_table = ec2.RouteTable(self.rt_id)
            if route_table.associations_attribute[0]['SubnetId']  == self.subnet_id and route_table.associations_attribute[0]['AssociationState']['State'] == "associated":
                rt_ok = f"Associated with subnet {self.subnet_id}"
            logger.debug(f"Found existing route table: {self.rt_id} ({rt_ok})")
        rt = ec2.RouteTable(self.rt_id)

    def get(self):
        ec2 = boto3.resource('ec2')

        existing_vpcs = self.client.describe_vpcs( Filters=[ AWSVpc.DefaultFilter ],)
        vpc_id = _get_single_result_id("Vpc", existing_vpcs)

        existing_subnets = self.client.describe_subnets( Filters=[ AWSVpc.DefaultFilter ],)
        subnet_id = _get_single_result_id("Subnet",existing_subnets)

        existing_igws = self.client.describe_internet_gateways( Filters=[ AWSVpc.DefaultFilter ],)
        igw_id = _get_single_result_id("InternetGateway",existing_igws)

        if igw_id is not None:
            igw = ec2.InternetGateway(igw_id)
            if igw.attachments == []:
                logger.warn(f"Internet Gateway '{igw_id}' is not attached to a vpc!")
            else:
                if igw.attachments[0]['VpcId'] != vpc_id:
                    logger.error(f"Internet Gateway '{igw_id}' is not attached to the correct vpc!")


        existing_rts = self.client.describe_route_tables( Filters=[ AWSVpc.DefaultFilter ],)
        rt_id = _get_single_result_id("RouteTable",existing_rts)

        return {
            "vpc_id": vpc_id,
            "subnet_id": subnet_id,
            "rt_id": rt_id,
            "igw_id": igw_id,
        }

    def destroy(self):
        ec2 = boto3.resource('ec2')
        self.__dict__.update(self.get())
        vpc = ec2.Vpc(self.vpc_id)
        subnet = ec2.Subnet(self.subnet_id)
        igw = ec2.InternetGateway(self.igw_id)
        rt = ec2.RouteTable(self.rt_id)
        rt_assoc_ids = [rtid['RouteTableAssociationId'] for rtid in rt.associations_attribute]
        logger.debug(f"deleting {len(rt_assoc_ids)} associations on route table '{self.rt_id}'...")
        for rtai in rt_assoc_ids:
            ec2.RouteTableAssociation(rtai).delete(DryRun=False)
        logger.debug(f"deleting route table '{self.rt_id}'...")
        rt.delete(DryRun=False)

        logger.debug(f"detaching igw '{self.igw_id}' from '{self.vpc_id}'...")
        igw.detach_from_vpc(
            DryRun=False,
            VpcId=self.vpc_id
        )
        logger.debug(f"deleting igw '{self.igw_id}'...")
        igw.delete(DryRun=False)
        logger.debug(f"deleting subnet '{self.subnet_id}'...")
        subnet.delete(DryRun=False)
        logger.debug(f"deleting vpc '{self.vpc_id}'...")
        vpc.delete(DryRun=False)
        logger.debug(f"Done.")


def _get_single_result_id(resource_type, resource, plural=True):
    """
    get the aws resource id for a specified aws resource
    example "InternetGateways" (plural is not implied) resource:
{'InternetGateways': [{'Attachments': [{'State': 'available', 'VpcId': 'vpc-0658d36368c863e33'}], 'InternetGatewayId': 'igw-02f85f5e5c6400320', 'OwnerId': '188154480716', 'Tags': []}, {'Attachments': [], 'InternetGatewayId': 'igw-0850d03a5ab4fbed4', 'OwnerId': '188154480716', 'Tags': [{'Key': 'Name', 'Value': 'quickhost'}]}, {'Attachments': [{'State': 'available', 'VpcId': 'vpc-7c31a606'}], 'InternetGatewayId': 'igw-c10bf1ba', 'OwnerId': '188154480716', 'Tags': []}], 'ResponseMetadata': {'RequestId': 'abe5dbdf-02bf-48db-83cc-ef4f523f8103', 'HTTPStatusCode': 200, 'HTTPHeaders': {'x-amzn-requestid': 'abe5dbdf-02bf-48db-83cc-ef4f523f8103', 'cache-control': 'no-cache, no-store', 'strict-transport-security': 'max-age=31536000; includeSubDomains', 'content-type': 'text/xml;charset=UTF-8', 'content-length': '1355', 'date': 'Mon, 27 Jun 2022 16:09:04 GMT', 'server': 'AmazonEC2'}, 'RetryAttempts': 0}}
    """
    if plural:
        _l = resource[f"{resource_type}s"]
    else:
        return resource[f"{resource_type}"][f"{resource_type}Id"]

    if len(_l) == 1:
        logger.debug(f"Found 1 {resource_type}.")#: {resource}")
        return _l[0][f"{resource_type}Id"]
    if len(_l) < 1:
        logger.info(f"No {resource_type}s were found.")
        return None
    if len(_l) > 1:
        logger.warning(f"{len(resource_type[resource])} {resource_type}s were found with the name '{C.DEFAULT_APP_NAME}'")
        return None
    logger.error("something went wrong getting resource id")
    return None

