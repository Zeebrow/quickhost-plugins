import argparse
import logging

from quickhost import ParserBase

logger = logging.getLogger(__name__)


class NullParser(ParserBase):
    def __init__(self):
        pass

    def add_subparsers(self, parser: argparse.ArgumentParser) -> None:
        subp = parser.add_subparsers(dest='null')
        init_parser = subp.add_parser("init")
        make_parser = subp.add_parser("make")
        describe_parser = subp.add_parser("describe")
        update_parser = subp.add_parser("update")
        destroy_parser = subp.add_parser("destroy")
        subp.add_parser("list-all")
        destroy_all_parser = subp.add_parser("destroy-all", help="null app destroy-all help @@@")
        self.add_init_parser_arguments(init_parser)
        self.add_make_parser_arguments(make_parser)
        self.add_describe_parser_arguments(describe_parser)
        self.add_update_parser_arguments(update_parser)
        self.add_destroy_parser_arguments(destroy_parser)
        self.add_destroy_all_parser_arguments(destroy_all_parser)

    def add_destroy_all_parser_arguments(self, parser: argparse.ArgumentParser):
        parser.add_argument("-y", "--yes", action='store_true', help="force deletion without prompting for confirmation")

    def add_init_parser_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--null-init-arg", action='store_true', help='set an init property of the null app')

    def add_make_parser_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--null-make-arg", action='store_true', help='set a make property of the null app')
        parser.add_argument("-n", "--app-name", required=True, help="name of the app")

    def add_describe_parser_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--null-describe-arg", action='store_true', help='set a describe property of the null app')
        parser.add_argument("-n", "--app-name", required=True, help="name of the app")

    def add_update_parser_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--null-update-arg", action='store_true', help='set an update property of the null app')
        parser.add_argument("-n", "--app-name", required=True, help="name of the app")

    def add_destroy_parser_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--null-destroy-arg", action='store_true', help='set a destroy property of the null app')
        parser.add_argument("-n", "--app-name", required=True, help="name of the app")
