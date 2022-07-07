from typing import List
from dataclasses import dataclass
from argparse import Namespace, SUPPRESS, ArgumentParser, _ArgumentGroup
from abc import ABCMeta, abstractmethod
import configparser
import logging
import os
import json

import boto3
from botocore.exceptions import ClientError

import quickhost
from quickhost import APP_CONST as QHC, QHExit

from .AWSIam import Iam
from .AWSSG import SG
from .AWSHost import AWSHost
from .AWSKeypair import KP
from .AWSNetworking import AWSNetworking
from .constants import AWSConstants
from .utilities import check_running_as_user, get_ssh
from .AWSResource import AWSResourceBase

logger = logging.getLogger(__name__)

class AWSApp(quickhost.AppBase, AWSResourceBase):
    """
    AWSApp
    Sort-of a dataclass, sort-of not.
    I've tried putting all the 'None' arguments that aren't an __init__() parameter into
    their own class, but I found it to be a headache.
    Although, it might be way more testable to have a configuration class... I think we're past that point.

    Args need to be evaluated on their own terms, because context is so important... e.g.
    * 'ports' is not technically needed, but should be *settable* from CLI or Config
    * 'config_file' is absolutely needed, and *cannot* be set from Config (environment variables are an interesting option)
    * 'ssh_key_filepath' is arguably not even a plugin argument
    """
    plugin_name = 'aws'

    def __init__(self, app_name, config_file=None):
        self._client = boto3.client('ec2')
        self._ec2_resource = boto3.resource('ec2')
        self.config_file = config_file
        if config_file is None:
            config_file = QHC.DEFAULT_CONFIG_FILEPATH
        super().__init__('aws', app_name, config_file)
        self._config_file_parser = quickhost.AppConfigFileParser()
        self._config_file_parser.read(self.config_file)
        self.userdata = None
        self.ssh_key_filepath = None
        self.ami = None
        self.num_hosts = None
        self.instance_type = None
        self.userdata = None
        self.ports = []
        self.cidrs = []
        self.dry_run = None
        self.vpc_id = None
        self.subnet_id = None
        self.sgid = None
        #self.load_default_config()

    def plugin_init(self, init_args: dict):
        """
        Setup the following:
        - IAM user/group/policies/credentials
        - .aws/config and .aws/credentials files
        - VPC/Subnet/Routing/networking per-region
        """
        params = self._parse_init(init_args)
        iam_client = self.get_client(resource='iam', profile=params['profile'])
        sts_client = self.get_client(resource='sts', profile=params['profile'])
        ec2_client = self.get_client(resource='ec2', profile=params['profile'])

        caller_id = sts_client.get_caller_identity()
        username = quickhost.scrub_datetime(iam_client.get_user())['User']['UserName']
        user_id = quickhost.scrub_datetime(iam_client.get_user())['User']['UserId']
        acct = caller_id['Account']
        
        caller_id.pop('ResponseMetadata')
        inp = input(f"About to initialize quickhost using:\nuser:\t\t{username} ({user_id})\naccount:\t{acct}\n\nContinue? (y/n)")
        if not inp.lower() == ('y' or 'yes'):
            print('Aborted')
            exit(3)
        qh_iam = Iam(profile=params['profile'])
        #print(json.dumps(qh_iam.describe(), indent=2))
        qh_iam.create()
        #qh_iam.destroy()
        #qh_iam.describe()
        #print(json.dumps(qh_iam.describe(), indent=2))
        networking_params= AWSNetworking(
            app_name=self.app_name,
            profile=params['profile']
        )
        #print(json.dumps(networking_params.describe(), indent=2))
        p = networking_params.create()
        #p = networking_params.destroy()
        #p = networking_params.get()
        #print(p)
        #print(json.dumps(networking_params.describe(), indent=2))
        return 

    def load_default_config(self):
        networking_params = AWSNetworking(
            app_name=self.app_name,
        ).get()
        self.vpc_id = networking_params['vpc_id']
        self.subnet_id = networking_params['subnet_id']

    def _old_load_default_config(self):
        """
        read values from config file, and import the relevant ones
        run before load_cli_args()
        """
        try:
            all_config = self._config_file_parser[self._all_cfg_key()]
            for k in all_config:
                if k in self.__dict__.keys():
                    self.__dict__[k] = self._config_file_parser[self._all_cfg_key()][k]
                else:
                    logger.warning(f"Ignoring bad param in config: '{k}'")
        except KeyError:
            logger.debug(f"No '_all' config ({self._all_cfg_key()}) found in config file '{self.config_file}'")
            all_config = None
        try:
            app_config = self._config_file_parser[self._app_cfg_key()]
            for k in app_config:
                if (k in self.__dict__.keys()) and (not k.startswith('_')):
                    self.__dict__[k] = self._config_file_parser[self._app_cfg_key()][k]
                else:
                    logger.warning(f"Ignoring bad param in config: '{k}'")
        except KeyError:
            logger.debug(f"No app config ({self._app_cfg_key()}) found in config file '{self.config_file}'")
            app_config = None

    def get_init_parser(self):
        init_parser = ArgumentParser("AWS init", add_help=False)
        #parser.add_argument("-y", "--dry-run", required=False, action='store_true', help="prevents any resource creation when set")
        #parser.add_argument("-a", "--aws-access-key-id", required=False, action='store_true', help="the access key id provided when creating root account credentials")
        #init_parser.add_argument("-x", "--aws-secret-access-key", required=False, action='store', help="the secret access key provided when creating root account credentials")
        init_parser.add_argument("--profile", required=False, action='store', help="profile of an admin AWS account used to create initial quickhost resources")
        init_parser.add_argument("--region", required=False, action='store', help="AWS region in which to create initial quickhost resources")
        #parser.add_argument("-f", "--user-key-csv", required=False, action='store_true', help="path to the rootkey.csv file downloaded when creating root account credentials")
        return init_parser

    def get_make_parser(self):
        """arguments for `make`"""
        make_parser = ArgumentParser("AWS make", add_help=False)
        make_parser.add_argument("--vpc-id", required=False, default=SUPPRESS, help="specify a VpcId to choose the vpc in which to launch hosts")
        make_parser.add_argument("--subnet-id", required=False, default=SUPPRESS, help="specify a SubnetId to choose the subnet in which to launch hosts")
        make_parser.add_argument("-c", "--host-count", required=False, default=1, help="number of hosts to create")
        make_parser.add_argument("--ssh-key-filepath", required=False, default=SUPPRESS, help="download newly created key to target file (default is APP_NAME.pem in cwd)")
        make_parser.add_argument("-y", "--dry-run", required=False, action='store_true', help="prevents any resource creation when set")
        make_parser.add_argument("-p", "--port", required=False, type=int, action='append', default=SUPPRESS, help="add an open tcp port to security group, applied to all ips")
        make_parser.add_argument("--ip", required=False, action='append', help="additional ipv4 to allow through security group. all ports specified with '--port' are applied to all ips specified with --ip if a cidr is not included, it is assumed to be /32")
        make_parser.add_argument("--instance-type", required=False, default="t2.micro", help="change the type of instance to launch")
        make_parser.add_argument("--ami", required=False, default=SUPPRESS, help="change the ami to launch, see source-aliases for getting lastest")
        make_parser.add_argument("-u", "--userdata", required=False, default=SUPPRESS, help="path to optional userdata file")
        return make_parser

    def get_describe_parser(self):
        parser= ArgumentParser("AWS describe", add_help=False)
        return parser

    def update_parser_arguments(self, parser: ArgumentParser):
        parser.add_argument("-y", "--dry-run", required=False, action='store_true', help="prevents any resource creation when set")
        parser.add_argument("-p", "--port", required=False, type=int, action='append', default=SUPPRESS, help="add an open tcp port to security group, applied to all ips")
        parser.add_argument("--ip", required=False, action='append', help="additional ipv4 to allow through security group. all ports specified with '--port' are applied to all ips specified with --ip if a cidr is not included, it is assumed to be /32")
        parser.add_argument("--instance-type", required=False, default="t2.micro", help="change the type of instance to launch")
        parser.add_argument("--ami", required=False, default=SUPPRESS, help="change the ami to launch, see source-aliases for getting lastest")
        parser.add_argument("-u", "--userdata", required=False, default=SUPPRESS, help="path to optional userdata file")
        return None

    def get_destroy_parser(self):
        parser= ArgumentParser("AWS destroy", add_help=False)
        return parser

    @classmethod
    def parser_arguments(subparser: ArgumentParser) -> None:
        """required cli arguments, as well as allowed overrides"""
        pass
    
    def run_init(self, args: dict):
        """must be run as an admin-like user"""
        logger.debug('run init')
        self.plugin_init(args)
        return QHExit.OK

    def run_make(self, args: dict):
        logger.debug('make')
        prompt_continue = input("proceed?")
        if not prompt_continue == 'y':
            print("aborted.")
            return QHExit.ABORTED
        params = self._parse_make(args)
        self.create(args)
        return QHExit.OK

    def run_describe(self, args: dict):
        logger.debug('describe')
        self.describe(args)
        return QHExit.OK

    def run_destroy(self, args: dict):
        logger.debug('destroy')
        prompt_continue = input("proceed?")
        if not prompt_continue == 'y':
            print("aborted.")
            return QHExit.ABORTED
        params = self._parse_destroy(args)
        self.destroy(params)
        return QHExit.OK

    def run(self, args: dict):
        """
        eats a user's input from the CLI 'form' that parser_arguments() sets up. 
        Subsequently calls an appropriate AWSApp CRUD method.
        This method overrides AWSApp instance properties that were set after load_default_config() returns.
        """
        return QHExit.KNOWN_ISSUE
        if args['__qhaction'] == 'init':
            logger.debug('init')
            self.plugin_init(args)
            return QHExit.OK
        elif args['__qhaction'] == 'make':
            if not check_running_as_user():
                return QHExit.NOT_QH_USER 
            logger.debug('make')
            params = self._parse_make(args)
            self.create(args)
            return QHExit.OK
        elif args['__qhaction'] == 'describe':
            if not check_running_as_user():
                return QHExit.NOT_QH_USER 
            logger.debug('describe')
            self.describe(args)
            return QHExit.OK
        elif args['__qhaction'] == 'update':
            if not check_running_as_user():
                return QHExit.NOT_QH_USER 
            logger.debug('update')
            logger.debug("@@@ WIP")
            return QHExit.KNOWN_ISSUE
        elif args['__qhaction'] == 'destroy':
            if not check_running_as_user():
                return QHExit.NOT_QH_USER 
            logger.debug('destroy')
            params = self._parse_destroy(args)
            self.destroy(params)
            logger.debug("@@@ WIP")
            return QHExit.KNOWN_ISSUE
        else:
            return QHExit.GENERAL_FAILURE

    def _parse_init(self, args: dict):
        init_params = args
        return init_params
    
    def _parse_make(self, args: dict):
        make_params = {}
        flags = args.keys()
        # ports ingress
        if 'port' in flags:
            # get rid of duplicates
            _ports = list(dict.fromkeys(args['port']))
            ports = []
            for p in _ports:
                # pretend they're all inst for now
                try:
                    ports.append(str(p))
                except ValueError:
                    raise RuntimeError("port numbers must be digits")
            self.ports = ports
            # @@@ todo: return make_params_params instead of using AWSApp() properties..?
            make_params['ports'] = ports
        else:
            self.ports = QHC.DEFAULT_OPEN_PORTS
            make_params['ports'] = QHC.DEFAULT_OPEN_PORTS
        # cidrs ingress
        make_params['cidrs'] = []
        if args['ip'] is None:
            self.cidrs = [quickhost.get_my_public_ip()]
            make_params['cidrs'].append(quickhost.get_my_public_ip())
        else:
            for i in args['ip']:
                if len(i.split('/')) == 1:
                    logger.warning(f"Assuming /32 cidr for ip '{i}'")
                    self.cidrs.append(i + "/32")
                    make_params['cidrs'].append(i + "/32")
                else:
                    self.cidrs.append(i)
                    make_params['cidrs'].append(i)
        # userdata
        if 'user_data' in flags:
            if not Path(args['userdata']).exists():
                raise RuntimeError(f"path to userdata '{args['userdata']}' does not exist!")
            self.userdata = flags['userdata']

        # ec2 key name
        if 'key_name' in flags:
            self.key_name = args['key_name']
            make_params['key_name'] = args['key_name']
        else:
            self.key_name = self.app_name
            make_params['key_name'] = self.app_name

        # ec2 key pem file
        if 'ssh_key_filepath' in flags:
            self.ssh_key_filepath = args['ssh_key_filepath']
            make_params['ssh_key_filepath'] = args['ssh_key_filepath']
        else:
            self.ssh_key_filepath = f"{self.app_name}.pem"
            make_params['ssh_key_filepath'] = f"{self.app_name}.pem"

        # the rest 
        if 'dry_run' in flags:
            #self.dry_run = not args['dry_run']
            self.dry_run = args['dry_run']
            make_params['dry_run'] = args['dry_run']
        if 'host_count' in flags:
            self.num_hosts = args['host_count']
            make_params['host_count'] = args['host_count']
        if 'instance_type' in flags:
            self.instance_type = args['instance_type']
            make_params['instance_type'] = args['instance_type']
        if 'ami' in flags:
            self.ami= args['ami']
            make_params['ami'] = args['ami']
        if 'vpc_id' in flags:
            self.vpc_id= args['vpc_id']
            make_params['vpc_id'] = args['vpc_id']
        if 'subnet_id' in flags:
            self.subnet_id= args['subnet_id']
            make_params['subnet_id'] = args['subnet_id']

        return make_params


    def _parse_describe(self):
        #flags = args.keys()
        self.dry_run = False
        return {}
        
    def _parse_destroy(self, args: dict):
        destroy_params = {}
        flags = args.keys()
        return {
            'app_name': self.app_name,
            'config_file': self.config_file
        }

    def _print_loaded_args(self, d: dict, heading=None) -> None:
        """print the currently loaded app parameters"""
        underline_char = '*'
        fill_char = '.'
        if heading:
            print(heading)
            print(underline_char*len(heading))

        # qualm pytest when running without -s
        if os.isatty(1):
            if os.get_terminal_size()[0] > 80:
                termwidth = 40
            else:
                termwidth = os.get_terminal_size()[0] 
            for k,v in d.items():
                if not k.startswith("_"):
                    if heading:
                        k = underline_char + k
                    print("{0:{fc}{align}{width}}{1}".format(
                        k, v, fc=fill_char, align='<', width=termwidth
                    ))
            
        else:
            logger.warning("There's nowhere to show your results!")
        return None

    def describe(self, args: dict) -> None:
        self._parse_describe()
        self.load_default_config()

        sts = self.get_client( 'sts',)
        caller_id = sts.get_caller_identity()
        iam = self.get_client('iam')
        all_users = iam.list_users()
        running_as_user_id = caller_id['UserId']
        running_as_user = ''
        for u in all_users['Users']:
            if u['UserId'] == running_as_user_id:
                running_as_user = u['UserName']
                break
        iam_vals = {
            "invoking_user_name": running_as_user,
            "invoking_user_id": running_as_user_id,
        }
        sg = SG(
            app_name=self.app_name,
            vpc_id=self.vpc_id,
        )
        sg_vals = sg.describe()
        kp = KP( app_name=self.app_name,)
        kp_vals = kp.describe()
        host = AWSHost( app_name=self.app_name,)
        host_vals = host.describe()
        init = AWSNetworking( app_name=self.app_name,)
        # idk man
        self._print_loaded_args(init.describe(),heading=f"global params")
        self._print_loaded_args(iam_vals)
        self._print_loaded_args(sg_vals)
        self._print_loaded_args(kp_vals)
        for i,host in enumerate(host_vals):
            self._print_loaded_args(host, heading=f"host {i}")
            #get_ssh(kp_vals['key_filepath'], h['public_ip'])
        #self._print_loaded_args(heading=f"Params for app '{self.app_name}'")

    def create(self, args: dict):
        self.load_default_config()
        p = self._parse_make(args)
        kp = KP(
            app_name=self.app_name,
        )
        kp.create()
        sg = SG(
            app_name=self.app_name,
            vpc_id=self.vpc_id,
        )
        sgid = sg.create(
            ports=self.ports,
            cidrs=self.cidrs
        )
        host = AWSHost(
            app_name=self.app_name,
        )
        if self.ami is None:
            print("No ami specified, getting latest al2...", end='')
            self.ami = AWSHost.get_latest_image(self._client)
            print(f"done ({self.ami})")
        host.create(
            num_hosts=self.num_hosts,
            image_id=self.ami,
            instance_type=self.instance_type,
            subnet_id=self.subnet_id,
            sgid=sgid,
            key_name=self.key_name,
            userdata=self.userdata,
            dry_run=self.dry_run
        )
        #_host.get_ssh()
        print('Done')
        return QHExit.OK 

    def update(self):
        pass

    def destroy(self, args: dict):
        self.load_default_config()
        kp = KP(
            app_name=self.app_name,
            # @@@ ...
            #ssh_key_filepath=params['ssh_key_filepath'],
        ).destroy()
        hosts = AWSHost( app_name=self.app_name,)
        hc = hosts.get_host_count()
        print(f"{hc=}")
        hosts.destroy()
        sg = SG(
            app_name=self.app_name,
            vpc_id=self.vpc_id,
        ).destroy()
        return QHExit.OK 
