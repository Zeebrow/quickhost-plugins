import argparse
import logging

import click

from quickhost import ParserBase

logger = logging.getLogger(__name__)

class NullParser(ParserBase):
    def __init__(self):
        pass

    def add_parser_arguments(self, action: str, parser: argparse.ArgumentParser, help: bool) -> None:
        if help:
            p = argparse.ArgumentParser(f"null {action}")
        else:
            p = parser
        match action:
            case 'init':
                self.init_parser_args(parser=p)
            case 'make':
                self.make_parser_args(parser=p)
            case 'describe':
                self.describe_parser_args(parser=p)
            case 'update':
                self.update_parser_args(parser=p)
            case 'destroy':
                self.destroy_parser_args(parser=p)
        if help:
            p.print_help()
            exit(0)
        logger.debug(f"action is '{action}'")
        
    def init_parser_args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--null-init-arg", action='store_true', help='set an init property of the null app')

    def make_parser_args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--null-make-arg", action='store_true', help='set a make property of the null app')
        parser.add_argument("-n", "--app-name", required=True, help="name of the app")

    def describe_parser_args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--null-describe-arg", action='store_true', help='set a describe property of the null app')
        parser.add_argument("-n", "--app-name", required=True, help="name of the app")

    def update_parser_args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--null-update-arg", action='store_true', help='set an update property of the null app')
        parser.add_argument("-n", "--app-name", required=True, help="name of the app")

    def destroy_parser_args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--null-destroy-arg", action='store_true', help='set a destroy property of the null app')
        parser.add_argument("-n", "--app-name", required=True, help="name of the app")
