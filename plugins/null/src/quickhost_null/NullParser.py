import argparse
import logging

from quickhost import ParserBase

logger = logging.getLogger(__name__)

class NullParser(ParserBase):
    def __init__(self) -> argparse.ArgumentParser:
        pass

    def add_parser_arguments(self, action: str, parser: argparse.ArgumentParser) -> None:
        logger.debug(f"action is '{action}'")
        if action == 'init':
            parser.add_argument("--null-init-arg", action='store_true', help='set an init property of the null app')
        elif action == 'make':
            parser.add_argument("--null-make-arg", action='store_true', help='set a make property of the null app')
            parser.add_argument("-n", "--app-name", required=True, help="name of the app")
        elif action == 'describe':
            parser.add_argument("--null-describe-arg", action='store_true', help='set a describe property of the null app')
            parser.add_argument("-n", "--app-name", required=True, help="name of the app")
        elif action == 'update':
            parser.add_argument("--null-update-arg", action='store_true', help='set an update property of the null app')
            parser.add_argument("-n", "--app-name", required=True, help="name of the app")
        elif action == 'destroy':
            parser.add_argument("--null-destroy-arg", action='store_true', help='set a destroy property of the null app')
            parser.add_argument("-n", "--app-name", required=True, help="name of the app")
        else:
            logger.error(f"why did main.py not handle invalid actions?")
            raise ValueError(f"(This is a bug with quickhost, not the plugin) No such action '{action}'.")
