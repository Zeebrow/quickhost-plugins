# Copyright (C) 2022 zeebrow

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import logging
import os
from pathlib import Path
import json

import boto3

import quickhost
from quickhost import QHExit, CliResponse

from .AWSResource import AWSResourceBase
from .AWSIam import Iam
from .AWSSG import SG
from .AWSHost import AWSHost
from .AWSKeypair import KP
from .AWSNetworking import AWSNetworking
from .constants import AWSConstants
from .utilities import QuickhostUnauthorized, Arn

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
    * 'ssh_key_filepath' is arguably not even a plugin argument
    """
    plugin_name = 'aws'

    def __init__(self, app_name):
        self.app_name = app_name
        self._client = boto3.client('ec2')
        self._ec2_resource = boto3.resource('ec2')
        # super().__init__('aws', app_name)
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

    def load_default_config(self, cache_ok=True, region=AWSConstants.DEFAULT_REGION, profile=AWSConstants.DEFAULT_IAM_USER):
        networking_params = AWSNetworking(
            app_name=self.app_name,
            region=region,
            profile=profile
        ).describe(use_cache=cache_ok)
        sts = self.get_client(
            'sts',
            region=region,
            profile=profile
        )[1]
        caller_info = sts.get_caller_identity()
        _ = caller_info.pop('ResponseMetadata')
        self.vpc_id = networking_params['vpc_id']
        self.subnet_id = networking_params['subnet_id']
        calling_user_arn = Arn(caller_info['Arn'])
        self.user = calling_user_arn.resource
        self.account = calling_user_arn.account
        return networking_params
    def _print_loaded_args(self, d: dict, heading=None) -> None:
        """ Wow this is bad.  """
        if d is None:
            logger.warning("No items to print!")
            return
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
                    print("{0:{fc}{align}{width}} {1}".format(
                        k, v, fc=fill_char, align='<', width=termwidth
                    ))
        else:
            logger.warning("There's nowhere to show your results!")
        return None

    def plugin_destroy(self, init_args: dict) -> CliResponse:
        """
        Needs a list-all-apps or something similar (which I want, anyways)
        """
        raise Exception("TODO")

    # @@@ CliResponse
    def plugin_init(self, init_args: dict) -> CliResponse:
        """
        Setup the following:
        - IAM user/group/policies/credentials
        - .aws/config and .aws/credentials files
        - VPC/Subnet/Routing/networking per-region
        must be run as an admin-like user
        """
        logger.debug('run init')
        finished_with_errors = False
        params = {
            "region": init_args['region'],
            "profile": init_args['profile'],
        }
        whoami, _ = self.get_client(resource='iam', **params)
        user_name = whoami['Arn'].split(":")[5].split("/")[-1]
        user_id = whoami['UserId']
        account = whoami['Account']
        inp = input(f"About to initialize quickhost using:\nuser:\t\t{user_name} ({user_id})\naccount:\t{account}\n\nContinue? (y/n) ")
        if not inp.lower() == ('y' or 'yes'):
            return CliResponse(None, 'aborted', QHExit.ABORTED)
        qh_iam = Iam(**params)
        try:
            qh_iam.create()
        except QuickhostUnauthorized as e:
            finished_with_errors = True
            logger.error(f"Failed to create initial IAM resources: {e}")

        networking_params= AWSNetworking(
            app_name=self.app_name,
            profile=init_args['profile'],
            region=init_args['region'],
        )
        try: 
            networking_params.create()
        except Exception:
            finished_with_errors = True
            logger.error("huh. I didn't know networking threw exceptions.")

        if finished_with_errors: #@@@
            return CliResponse('finished init with errors', "<placeholder>", QHExit.GENERAL_FAILURE)
        else:
            return CliResponse('Done', None, QHExit.OK)

    # @@@ CliResponse
    def describe(self, args: dict) -> CliResponse:
        logger.debug('run describe')
        params = args
        networking_params = self.load_default_config(
            region=params['region']
        )
        iam_vals = Iam(
            region=params['region'],
        ).describe(verbiage=1)
        sg = SG(
            region=params['region'],
            app_name=self.app_name,
            vpc_id=self.vpc_id,
        )
        sg_describe = sg.describe()
        kp = KP(
            app_name=self.app_name,
            region=params['region']
        )
        kp_describe = kp.describe()
        hosts = AWSHost(
            app_name=self.app_name,
            region=params['region']
        )
        hosts_describe = hosts.describe()
        logger.debug(hosts_describe)
        caller_info = {
            'account': self.account,
            'invoking user': '/'.join(self.user.split('/')[1:])
        }
        # idk man
        self._print_loaded_args(networking_params,heading=f"global params")
        self._print_loaded_args(caller_info)
        self._print_loaded_args(iam_vals)
        self._print_loaded_args(sg_describe)
        self._print_loaded_args(kp_describe)
        if hosts_describe is None:
            logger.warning("No hosts found for app " + self.app_name)
        else:
            for i,host in enumerate(hosts_describe):
                self._print_loaded_args(host, heading=f"host {i}")
        if kp_describe and hosts_describe and sg_describe:
            return CliResponse('Done', None, QHExit.OK)
        else:
            return CliResponse('finished creating hosts with errors', "<placeholder>", 1)

    #@@@
    @classmethod
    def list_all(self):
        print(json.dumps({
            "hosts": AWSHost.get_all_running_apps(),
            #...
        }, indent=3))
        return CliResponse('Done', None, QHExit.OK)

    # @@@ CliResponse
    def create(self, args: dict) -> CliResponse:
        # @@@ run_make
        logger.debug('make')
        stdout = ""
        stderr = ""
        rc = QHExit.GENERAL_FAILURE
        prompt_continue = input("proceed? (y/n)")
        if not prompt_continue == 'y':
            stderr = "aborted"
            return CliResponse(stdout, stderr, QHExit.ABORTED)
        params = self._parse_make(args)

        self.load_default_config(region=params['region'])
        profile = AWSConstants.DEFAULT_IAM_USER
        kp = KP(app_name=self.app_name, region=params['region'], profile=profile)
        sg = SG(app_name=self.app_name, region=params['region'], profile=profile, vpc_id=self.vpc_id)
        host = AWSHost(app_name=self.app_name, region=params['region'], profile=profile)
        if host.describe() is not None:
            logger.error(f"app named '{self.app_name}' already exists")
            return CliResponse(None, f"app named '{self.app_name}' already exists", QHExit.ABORTED)
            
        kp_created = kp.create()
        sg_created = sg.create(
            ports=params['ports'],
            cidrs=params['cidrs'],
        )
        hosts_created = host.create(
            subnet_id=self.subnet_id,
            num_hosts=params['host_count'],
            _os=params['os'],
            instance_type=params['instance_type'],
            sgid=sg.sgid,
            key_name=params['key_name'],
            userdata=params['userdata'],
            dry_run=params['dry_run']
        )
        if kp_created and hosts_created and sg_created:
            return CliResponse( 'Done', None, QHExit.OK)
        else:
            return CliResponse('finished creating hosts with warnings', f"{kp_created=}, {hosts_created=}, {sg_created=}", QHExit.GENERAL_FAILURE)

    def update(self, args: dict) -> CliResponse:
        raise Exception("TODO")

    def destroy(self, args: dict) -> CliResponse:
        prompt_continue = input("proceed? (y/n)")
        if not prompt_continue == 'y':
            print("aborted.")
            rc = QHExit.ABORTED
            return CliResponse(rc, "", "")
        self.load_default_config()
        kp_destroyed = KP(
            app_name=self.app_name,
            region=args['region'],
        ).destroy()
        hosts = AWSHost(
            region=args['region'],
            app_name=self.app_name,
        )
        hosts_destroyed = hosts.destroy()
        sg_destroyed = SG(
            region=args['region'],
            app_name=self.app_name,
            vpc_id=self.vpc_id,
        ).destroy()
        if kp_destroyed and hosts_destroyed and sg_destroyed:
            return CliResponse('Done', '', QHExit.OK)
        else:
            return CliResponse('finished destroying hosts with errors', f"{kp_destroyed=}, {hosts_destroyed=}, {sg_destroyed=}", QHExit.GENERAL_FAILURE)

    def _parse_make(self, args: dict):
        make_params = {}
        flags = args.keys()
        # ports ingress
        if 'port' in flags:
            # get rid of duplicates
            _ports = list(dict.fromkeys(args['port']))
            ports = []
            for p in _ports:
                try:
                    ports.append(str(p))
                except ValueError:
                    raise RuntimeError("port numbers must be digits")
            make_params['ports'] = ports
        # set defaults based on os
        # NOTE: specifying a port on the command line will override defaults
        # this is not documented, but is desired behavior
        else:
            if args['os'] in AWSConstants.WindowsOSTypes:
                make_params['ports'] = [3389]
            else:
                make_params['ports'] = [22]
        # cidrs ingress
        make_params['cidrs'] = []
        if args['ip'] is None:
            make_params['cidrs'].append(quickhost.get_my_public_ip())
        else:
            for i in args['ip']:
                if len(i.split('/')) == 1:
                    logger.warning(f"Assuming /32 cidr for ip '{i}'")
                    make_params['cidrs'].append(i + "/32")
                else:
                    make_params['cidrs'].append(i)
        # userdata
        if args['userdata'] is not None:
            if not Path(args['userdata']).exists():
                raise RuntimeError(f"path to userdata '{args['userdata']}' does not exist!")
        make_params['userdata'] = args['userdata']
        # ec2 key name
        if 'key_name' in flags:
            make_params['key_name'] = args['key_name']
        else:
            make_params['key_name'] = self.app_name
        # ec2 key pem file
        if 'ssh_key_filepath' in flags:
            make_params['ssh_key_filepath'] = args['ssh_key_filepath']
        else:
            make_params['ssh_key_filepath'] = f"{self.app_name}.pem"
        # the rest 
        if 'dry_run' in flags:
            make_params['dry_run'] = args['dry_run']
        if 'host_count' in flags:
            make_params['host_count'] = int(args['host_count'])
        if 'instance_type' in flags:
            make_params['instance_type'] = args['instance_type']
        if 'vpc_id' in flags:
            make_params['vpc_id'] = args['vpc_id']
        if 'subnet_id' in flags:
            make_params['subnet_id'] = args['subnet_id']
        if 'region' in flags:
            make_params['region'] = args['region']
        if 'os' in flags:
            make_params['os'] = args['os']
        return make_params
