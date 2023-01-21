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

    def add_subparsers(self, parser: ArgumentParser) -> None:
        """
        Create a subparser for each action, and attach argparse arguments.
        Setup each action's parser with argparse arguments.
        """
        subp = parser.add_subparsers(dest='aws')
        init_parser = subp.add_parser("init")
        make_parser = subp.add_parser("make")
        describe_parser = subp.add_parser("describe")
        update_parser = subp.add_parser("update")
        destroy_parser = subp.add_parser("destroy")
        list_all_parser = subp.add_parser("list-all")
        destroy_all_parser = subp.add_parser("destroy-all")
        self.add_init_parser_arguments(init_parser)
        self.add_make_parser_arguments(make_parser)
        self.add_describe_parser_arguments(describe_parser)
        self.add_update_parser_arguments(update_parser)
        self.add_destroy_parser_arguments(destroy_parser)
        self.add_destroy_all_parser_arguments(destroy_all_parser)

    def add_parser_arguments(self, action: str, parser: ArgumentParser, help: bool) -> None:
        """
        (old) Add arguments to a single parser 
        leave this here in case you don't like something about self.add_subparsers() again
        """
        if help:
            p = ArgumentParser(f"aws {action}")
        else:
            p = parser

        match action:
            case 'init':
                self.add_init_parser_arguments(parser=p)
            case 'make':
                self.add_make_parser_arguments(parser=p)
            case 'describe':
                self.add_describe_parser_arguments(parser=p)
            case 'update':
                self.add_update_parser_arguments(parser=p)
            case 'destroy':
                self.add_destroy_parser_arguments(parser=p)
        if help:
            p.print_help()
            exit(0)

        logger.debug(f"action is '{action}'")

    def add_destroy_all_parser_arguments(self, parser: ArgumentParser):
        parser.add_argument("-y", "--yes", action='store_true', help="force deletion without prompting for confirmation")
    
    def add_init_parser_arguments(self, parser: ArgumentParser):
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

    def add_make_parser_arguments(self, parser: ArgumentParser) -> None:
        """arguments for `make`"""
        parser.add_argument("-n", "--app-name", required=True, default=SUPPRESS, help="name of the app")
        parser.add_argument("--vpc-id", required=False, default=SUPPRESS, help="specify a VpcId to choose the vpc in which to launch hosts")
        parser.add_argument("--subnet-id", required=False, default=SUPPRESS, help="specify a SubnetId to choose the subnet in which to launch hosts")
        parser.add_argument("-c", "--host-count", required=False, default=1, help="number of hosts to create")
        parser.add_argument("--ssh-key-filepath", required=False, default=SUPPRESS, help="download newly created key to target file (default is APP_NAME.pem in cwd)")
        parser.add_argument("-y", "--dry-run", required=False, action='store_true', help="prevents any resource creation when set")
        parser.add_argument("-p", "--port", required=False, type=int, action='append', default=SUPPRESS, help="add an open tcp port to security group, applied to all ips (*nix default is 22, Windows 3389)")
        parser.add_argument("--ip", required=False, action='append', help="additional ipv4 to allow through security group. all ports specified with '--port' are applied to all ips specified with --ip if a cidr is not included, it is assumed to be /32")
        parser.add_argument("--instance-type", required=False, default="t2.micro", help="change the type of instance to launch")
        parser.add_argument("-u", "--userdata", required=False, default=None, help="path to optional userdata file")
        parser.add_argument("--region", required=False, choices=AWSConstants.AVAILABLE_REGIONS, default=AWSConstants.DEFAULT_REGION, help="region to launch the host into.")
        parser.add_argument("--os", required=False, default='amazon-linux-2', help="the OS to run on the host ('-core' means no GUI)",
            choices=[
            "amazon-linux-2",
            "ubuntu",
            "windows",
            "windows-core",
            ])

    def add_describe_parser_arguments(self, parser: ArgumentParser):
        parser.add_argument("-n", "--app-name", required=True, default=SUPPRESS, help="name of the app")
        parser.add_argument("--region", required=False, choices=AWSConstants.AVAILABLE_REGIONS, default=AWSConstants.DEFAULT_REGION, help="region to launch the host into.")
        return None

    def add_update_parser_arguments(self, parser: ArgumentParser):
        parser.add_argument("-n", "--app-name", required=True, default=SUPPRESS, help="name of the app")
        parser.add_argument("-y", "--dry-run", required=False, action='store_true', help="prevents any resource creation when set")
        parser.add_argument("-p", "--port", required=False, type=int, action='append', default=SUPPRESS, help="add an open tcp port to security group, applied to all ips")
        parser.add_argument("--ip", required=False, action='append', help="additional ipv4 to allow through security group. all ports specified with '--port' are applied to all ips specified with --ip if a cidr is not included, it is assumed to be /32")
        parser.add_argument("--instance-type", required=False, default="t2.micro", help="change the type of instance to launch")
        parser.add_argument("--ami", required=False, default=None, help="change the ami to launch, see source-aliases for getting lastest")
        parser.add_argument("-u", "--userdata", required=False, default=SUPPRESS, help="path to optional userdata file")
        return None

    def add_destroy_parser_arguments(self, parser: ArgumentParser):
        parser.add_argument("-n", "--app-name", required=True, default=SUPPRESS, help="name of the app")
        parser.add_argument("-r", "--region", required=False, default=AWSConstants.DEFAULT_REGION, help="region to launch the host into.")
        return None
