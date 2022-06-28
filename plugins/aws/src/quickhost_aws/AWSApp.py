from typing import List
from dataclasses import dataclass
from argparse import Namespace, SUPPRESS, ArgumentParser, _ArgumentGroup
from abc import ABCMeta, abstractmethod
import configparser
import logging
import os
import json

import boto3

import quickhost
from quickhost import APP_CONST as C

#from .utilities import get_my_public_ip
#from .constants import *
#from .cli_params import AppBase, AppConfigFileParser
from .AWSSG import SG
from .AWSHost import AWSHost
from .AWSKeypair import KP
from .AWSVpc import AWSVpc

logger = logging.getLogger(__name__)


class AWSApp(quickhost.AppBase):
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
    def __init__(self, app_name, config_file=None):
        self._client = boto3.client('ec2')
        self.config_file = config_file
        if config_file is None:
            config_file = C.DEFAULT_CONFIG_FILEPATH
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
        self.load_default_config()

    def plugin_init(self, args: dict):
        """
        Setup the following:
        - IAM
        """
        self._parse_init(args)
        iam = boto3.client(
            'iam',
        )
        sts = boto3.client(
            'sts',
        )
        caller_id = sts.get_caller_identity()
        caller_id.pop('ResponseMetadata')
        inp = input(f"About to initialize quickhost for this user/account: \n{json.dumps(caller_id, indent=2)}\n\nContinue? (y/n)")
        if not inp.lower() == ('y' or 'yes'):
            print('Aborted')
            exit(3)
        networking_params= AWSVpc(
            app_name=self.app_name,
            client=self._client,
        )
        p = networking_params.create()
        #p = networking_params.destroy()
        #p = networking_params.get()
        print(p)
        return 
        

    def _all_cfg_key(self):
        return f'{self._cli_parser_id}:all'
    def _app_cfg_key(self):
        return f'{self.app_name}:{self._cli_parser_id}'
    def load_default_config(self):
        networking_params = AWSVpc(
            app_name=self.app_name,
            client=self._client,
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

    def init_parser_arguments(self, parser: ArgumentParser):
        #parser.add_argument("-y", "--dry-run", required=False, action='store_true', help="prevents any resource creation when set")
        #parser.add_argument("-a", "--aws-access-key-id", required=False, action='store_true', help="the access key id provided when creating root account credentials")
        #parser.add_argument("-x", "--aws-secret-access-key", required=False, action='store_true', help="the secret access key provided when creating root account credentials")
        #parser.add_argument("-f", "--root-key-csv", required=False, action='store_true', help="path to the rootkey.csv file downloaded when creating root account credentials")
        return None

    def describe_parser_arguments(self, parser: ArgumentParser):
        pass

    def update_parser_arguments(self, parser: ArgumentParser):
        parser.add_argument("-y", "--dry-run", required=False, action='store_true', help="prevents any resource creation when set")
        parser.add_argument("-p", "--port", required=False, type=int, action='append', default=SUPPRESS, help="add an open tcp port to security group, applied to all ips")
        parser.add_argument("--ip", required=False, action='append', help="additional ipv4 to allow through security group. all ports specified with '--port' are applied to all ips specified with --ip if a cidr is not included, it is assumed to be /32")
        parser.add_argument("--instance-type", required=False, default="t2.micro", help="change the type of instance to launch")
        parser.add_argument("--ami", required=False, default=SUPPRESS, help="change the ami to launch, see source-aliases for getting lastest")
        parser.add_argument("-u", "--userdata", required=False, default=SUPPRESS, help="path to optional userdata file")
        return None

    def make_parser_arguments(self, parser: ArgumentParser):
        """arguments for `aws make`"""
        parser.add_argument("--vpc-id", required=False, default=SUPPRESS, help="specify a VpcId to choose the vpc in which to launch hosts")
        parser.add_argument("--subnet-id", required=False, default=SUPPRESS, help="specify a SubnetId to choose the subnet in which to launch hosts")
        parser.add_argument("-c", "--host-count", required=False, default=1, help="number of hosts to create")
        parser.add_argument("--ssh-key-filepath", required=False, default=SUPPRESS, help="download newly created key to target file (default is APP_NAME.pem in cwd)")
        parser.add_argument("-y", "--dry-run", required=False, action='store_true', help="prevents any resource creation when set")
        parser.add_argument("-p", "--port", required=False, type=int, action='append', default=SUPPRESS, help="add an open tcp port to security group, applied to all ips")
        parser.add_argument("--ip", required=False, action='append', help="additional ipv4 to allow through security group. all ports specified with '--port' are applied to all ips specified with --ip if a cidr is not included, it is assumed to be /32")
        parser.add_argument("--instance-type", required=False, default="t2.micro", help="change the type of instance to launch")
        parser.add_argument("--ami", required=False, default=SUPPRESS, help="change the ami to launch, see source-aliases for getting lastest")
        parser.add_argument("-u", "--userdata", required=False, default=SUPPRESS, help="path to optional userdata file")
        return None

    @classmethod
    def parser_arguments(subparser: ArgumentParser) -> None:
        """required cli arguments, as well as allowed overrides"""
        pass
    
    def run(self, args: dict):
        """
        eats a user's input from the CLI 'form' that parser_arguments() sets up. 
        Subsequently calls an appropriate AWSApp CRUD method.
        This method overrides AWSApp instance properties that were set after load_default_config() returns.
        """
        if args['__qhaction'] == 'init':
            print('init')
            print(args)
            exit()
            self.plugin_init(args)
            return 0
        elif args['__qhaction'] == 'make':
            print('make')
            self.create(args)
            return 0
        elif args['__qhaction'] == 'describe':
            print('describe')
            self.describe(args)
            return 0
        elif args['__qhaction'] == 'update':
            print('update')
            print("@@@ WIP")
            return 1
        elif args['__qhaction'] == 'destroy':
            print('destroy')
            print("@@@ WIP")
            return 1
        else:
            raise Exception("should have printed help in main.py! Bug!")

    def _parse_init(self, args: dict):
        flags = args.keys()
    
    def _parse_make(self, args: dict):
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
        else:
            self.ports = C.DEFAULT_OPEN_PORTS
        # cidrs ingress
        if args['ip'] is None:
            self.cidrs = [quickhost.get_my_public_ip()]
        else:
            for i in args['ip']:
                if len(i.split('/')) == 1:
                    logger.warning(f"Assuming /32 cidr for ip '{i}'")
                    self.cidrs.append(i + "/32")
                else:
                    self.cidrs.append(i)
        # userdata
        if 'user_data' in flags:
            if not Path(args['userdata']).exists():
                raise RuntimeError(f"path to userdata '{args['userdata']}' does not exist!")
            self.userdata = flags['userdata']

        # ec2 key name
        if 'key_name' in flags:
            self.key_name = args['key_name']
        else:
            self.key_name = args['app_name']
        # ec2 key pem file
        if 'ssh_key_filepath' in flags:
            self.ssh_key_filepath = args['ssh_key_filepath']
        else:
            self.ssh_key_filepath = f"{self.app_name}.pem"

        # the rest 
        if 'dry_run' in flags:
            #self.dry_run = not args['dry_run']
            self.dry_run = args['dry_run']
        if 'host_count' in flags:
            self.num_hosts = args['host_count']
        if 'instance_type' in flags:
            self.instance_type = args['instance_type']
        if 'ami' in flags:
            self.ami= args['ami']
        if 'vpc_id' in flags:
            self.vpc_id= args['vpc_id']
        if 'subnet_id' in flags:
            self.subnet_id= args['subnet_id']

        return
    ### end of _parse_make()


    def _parse_describe(self):
        #flags = args.keys()
        self.dry_run = False
        return
        
    def _parse_destroy(self, args: dict):
        flags = args.keys()
        if 'dry_run' in flags:
            self.dry_run = not ns.dry_run #NOT
        self._client = boto3.client("ec2")

    def _print_loaded_args(self, heading=None) -> None:
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
            for k,v in self.__dict__.items():
                if not k.startswith("_"):
                    print("{0:{fc}{align}{width}}{1}".format(
                        k, v, fc=fill_char, align='<', width=termwidth
                    ))
        else:
            logger.warning("There's nowhere to show your results!")
        return None

    def describe(self, args: dict) -> None:
        print(self.vpc_id)
        print(self.vpc_id)
        self._parse_describe()
        _sg = SG(
            client=self._client,
            app_name=self.app_name,
            vpc_id=self.vpc_id,
            dry_run=False
        )
        _kp = KP(
            client=self._client,
            app_name=self.app_name,
            ssh_key_filepath=None,
            dry_run=False
        )
        _host = AWSHost(
            client=self._client,
            app_name=self.app_name,
            num_hosts=self.num_hosts,
            image_id=self.ami,
            instance_type=self.instance_type,
            subnet_id=self.subnet_id,
            sgid=self.sgid,
            userdata=self.userdata,
            dry_run=False
        )
        _sg.describe()
        self.sgid = _sg.sgid
        self.kpid = _kp.get_key_id()
        self.ec2ids =  []
        for inst in _host.describe():
            self.ec2ids.append(inst['instance_id'])
        self._print_loaded_args(heading=f"Params for app '{self.app_name}'")

    def create(self, args: dict):
        self._parse_make(args)
        _kp = KP(
            client=self._client,
            app_name=self.app_name,
            ssh_key_filepath=self.ssh_key_filepath,
            dry_run=self.dry_run
        )
        _kp.create()
        _sg = SG(
            client=self._client,
            app_name=self.app_name,
            vpc_id=self.vpc_id,
            ports=args['port'],
            cidrs=args['cidr'],
            dry_run=self.dry_run,
        )
        self.sgid = _sg.create()
        if self.ami is None:
            print("No ami specified, getting latest al2...", end='')
            self.ami = AWSHost.get_latest_image(client=self._client)
            print(f"done ({self.ami})")
        _host = AWSHost(
            client=self._client,
            app_name=self.app_name,
            num_hosts=self.num_hosts,
            image_id=self.ami,
            instance_type=self.instance_type,
            subnet_id=self.subnet_id,
            sgid=self.sgid,
            key_name=self.key_name,
            userdata=self.userdata,
            dry_run=self.dry_run
        )
        _host.create()
        app_instances = _host.wait_for_hosts()
        #_host.get_ssh()
        print('Done')
        print(app_instances)

    def update(self):
        pass

    def destroy(self):
        pass
if __name__ == '__main__':
    pass
