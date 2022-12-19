import argparse
import logging

import click

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
        self.add_init_parser_arguments(init_parser)
        self.add_make_parser_arguments(make_parser)
        self.add_describe_parser_arguments(describe_parser)
        self.add_update_parser_arguments(update_parser)
        self.add_destroy_parser_arguments(destroy_parser)

    def add_parser_arguments(self, action: str, parser: argparse.ArgumentParser, help: bool) -> None:
        if help:
            p = argparse.ArgumentParser(f"null {action}")
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
