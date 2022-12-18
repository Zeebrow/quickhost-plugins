from pathlib import Path
from argparse import Namespace, SUPPRESS, ArgumentParser
import logging

from quickhost import APP_CONST as C, ParserBase
from .constants import AWSConstants

logger = logging.getLogger(__name__)

class AWSParser(ParserBase):
    def __init__(self, config_file=C.DEFAULT_CONFIG_FILEPATH):
        self.config_file = Path(config_file).absolute()
        if not self.config_file.exists():
            raise RuntimeError(f"no such file: {self.config_file}")

    def add_parser_arguments(self, action: str, parser: ArgumentParser, help: bool) -> None:
        if help:
            p = ArgumentParser(f"aws {action}")
        else:
            p = parser

        match action:
            case 'init':
                self.get_init_parser(parser=p)
            case 'make':
                self.get_make_parser(parser=p)
            case 'describe':
                self.get_describe_parser(parser=p)
            case 'update':
                self.get_update_parser(parser=p)
            case 'destroy':
                self.get_destroy_parser(parser=p)
        if help:
            p.print_help()
            exit(0)

        logger.debug(f"action is '{action}'")
    
    def get_init_parser(self, parser: ArgumentParser):
        parser.add_argument("--profile", required=False, action='store', default=AWSConstants.DEFAULT_IAM_USER, help="profile of an admin AWS account used to create initial quickhost resources")
        parser.add_argument(
            "--region",
            required=False,
            action='store',
            choices=AWSConstants.AVAILABLE_REGIONS,
            default=AWSConstants.DEFAULT_REGION,
            help="AWS region in which to create initial quickhost resources"
        )
        return None

    def get_make_parser(self, parser: ArgumentParser) -> None:
        """arguments for `make`"""
        parser.add_argument("-n", "--app-name", required=True, default=SUPPRESS, help="name of the app")
        parser.add_argument("--vpc-id", required=False, default=SUPPRESS, help="specify a VpcId to choose the vpc in which to launch hosts")
        parser.add_argument("--subnet-id", required=False, default=SUPPRESS, help="specify a SubnetId to choose the subnet in which to launch hosts")
        parser.add_argument("-c", "--host-count", required=False, default=1, help="number of hosts to create")
        parser.add_argument("--ssh-key-filepath", required=False, default=SUPPRESS, help="download newly created key to target file (default is APP_NAME.pem in cwd)")
        parser.add_argument("-y", "--dry-run", required=False, action='store_true', help="prevents any resource creation when set")
        parser.add_argument("-p", "--port", required=False, type=int, action='append', default=SUPPRESS, help="add an open tcp port to security group, applied to all ips")
        parser.add_argument("--ip", required=False, action='append', help="additional ipv4 to allow through security group. all ports specified with '--port' are applied to all ips specified with --ip if a cidr is not included, it is assumed to be /32")
        parser.add_argument("--instance-type", required=False, default="t2.micro", help="change the type of instance to launch")
        parser.add_argument("--ami", required=False, default=None, help="change the ami to launch, see source-aliases for getting lastest")
        parser.add_argument("-u", "--userdata", required=False, default=None, help="path to optional userdata file")
        parser.add_argument("--region", required=False, choices=AWSConstants.AVAILABLE_REGIONS, default=AWSConstants.DEFAULT_REGION, help="region to launch the host into.")

    def get_describe_parser(self, parser: ArgumentParser):
        parser.add_argument("-n", "--app-name", required=True, default=SUPPRESS, help="name of the app")
        parser.add_argument("--region", required=False, choices=AWSConstants.AVAILABLE_REGIONS, default=AWSConstants.DEFAULT_REGION, help="region to launch the host into.")
        return None

    def get_update_parser(self, parser: ArgumentParser):
        parser.add_argument("-n", "--app-name", required=True, default=SUPPRESS, help="name of the app")
        parser.add_argument("-y", "--dry-run", required=False, action='store_true', help="prevents any resource creation when set")
        parser.add_argument("-p", "--port", required=False, type=int, action='append', default=SUPPRESS, help="add an open tcp port to security group, applied to all ips")
        parser.add_argument("--ip", required=False, action='append', help="additional ipv4 to allow through security group. all ports specified with '--port' are applied to all ips specified with --ip if a cidr is not included, it is assumed to be /32")
        parser.add_argument("--instance-type", required=False, default="t2.micro", help="change the type of instance to launch")
        parser.add_argument("--ami", required=False, default=None, help="change the ami to launch, see source-aliases for getting lastest")
        parser.add_argument("-u", "--userdata", required=False, default=SUPPRESS, help="path to optional userdata file")
        return None

    def get_destroy_parser(self, parser: ArgumentParser):
        parser.add_argument("-n", "--app-name", required=True, default=SUPPRESS, help="name of the app")
        parser.add_argument("-r", "--region", required=False, default=AWSConstants.DEFAULT_REGION, help="region to launch the host into.")
        return None


    # from AWSApp.py
    # def get_init_parser(self):
    #     init_parser = ArgumentParser("AWS init", add_help=False)
    #     #parser.add_argument("-y", "--answer-yes", required=False, action='store_true', help="bypass prompt to confirm you want to init.")
    #     init_parser.add_argument("--profile", required=False, action='store', default=AWSConstants.DEFAULT_IAM_USER, help="profile of an admin AWS account used to create initial quickhost resources")
    #     init_parser.add_argument(
    #         "--region",
    #         required=False,
    #         action='store',
    #         choices=AWSConstants.AVAILABLE_REGIONS,
    #         default=AWSConstants.DEFAULT_REGION,
    #         help="AWS region in which to create initial quickhost resources"
    #     )
    #     return init_parser

    # def get_make_parser(self) -> ArgumentParser:
    #     """arguments for `make`"""
    #     make_parser = ArgumentParser("AWS make", add_help=False)
    #     #make_parser = ArgumentParser("AWS make", add_help=True)
    #     make_parser.add_argument("--vpc-id", required=False, default=SUPPRESS, help="specify a VpcId to choose the vpc in which to launch hosts")
    #     make_parser.add_argument("--subnet-id", required=False, default=SUPPRESS, help="specify a SubnetId to choose the subnet in which to launch hosts")
    #     make_parser.add_argument("-c", "--host-count", required=False, default=1, help="number of hosts to create")
    #     make_parser.add_argument("--ssh-key-filepath", required=False, default=SUPPRESS, help="download newly created key to target file (default is APP_NAME.pem in cwd)")
    #     make_parser.add_argument("-y", "--dry-run", required=False, action='store_true', help="prevents any resource creation when set")
    #     make_parser.add_argument("-p", "--port", required=False, type=int, action='append', default=SUPPRESS, help="add an open tcp port to security group, applied to all ips")
    #     make_parser.add_argument("--ip", required=False, action='append', help="additional ipv4 to allow through security group. all ports specified with '--port' are applied to all ips specified with --ip if a cidr is not included, it is assumed to be /32")
    #     make_parser.add_argument("--instance-type", required=False, default="t2.micro", help="change the type of instance to launch")
    #     make_parser.add_argument("--ami", required=False, default=None, help="change the ami to launch, see source-aliases for getting lastest")
    #     make_parser.add_argument("-u", "--userdata", required=False, default=None, help="path to optional userdata file")
    #     make_parser.add_argument("--region", required=False, choices=AWSConstants.AVAILABLE_REGIONS, default=AWSConstants.DEFAULT_REGION, help="region to launch the host into.")
    #     return make_parser

    # def get_describe_parser(self):
    #     parser= ArgumentParser("AWS describe", add_help=False)
    #     parser.add_argument("--region", required=False, choices=AWSConstants.AVAILABLE_REGIONS, default=AWSConstants.DEFAULT_REGION, help="region to launch the host into.")
    #     return parser

    # def update_parser_arguments(self, parser: ArgumentParser):
    #     parser.add_argument("-y", "--dry-run", required=False, action='store_true', help="prevents any resource creation when set")
    #     parser.add_argument("-p", "--port", required=False, type=int, action='append', default=SUPPRESS, help="add an open tcp port to security group, applied to all ips")
    #     parser.add_argument("--ip", required=False, action='append', help="additional ipv4 to allow through security group. all ports specified with '--port' are applied to all ips specified with --ip if a cidr is not included, it is assumed to be /32")
    #     parser.add_argument("--instance-type", required=False, default="t2.micro", help="change the type of instance to launch")
    #     parser.add_argument("--ami", required=False, default=None, help="change the ami to launch, see source-aliases for getting lastest")
    #     parser.add_argument("-u", "--userdata", required=False, default=SUPPRESS, help="path to optional userdata file")
    #     return None

    # def get_destroy_parser(self):
    #     parser= ArgumentParser("AWS destroy", add_help=False)
    #     parser.add_argument("-r", "--region", required=False, default=AWSConstants.DEFAULT_REGION, help="region to launch the host into.")
    #     return parser