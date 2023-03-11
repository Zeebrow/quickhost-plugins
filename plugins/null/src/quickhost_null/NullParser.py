# Copyright (C) 2022 zeebrow
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import argparse
import logging

from quickhost import ParserBase

logger = logging.getLogger(__name__)


class NullParser(ParserBase):
    def __init__(self):
        pass

    def add_subparsers(self, parser: argparse.ArgumentParser) -> None:
        subp = parser.add_subparsers(dest='null')
        init_parser = subp.add_parser("init", help="plugin initialization help")
        make_parser = subp.add_parser("make", help="make an app help")
        describe_parser = subp.add_parser("describe", help="show details about an app help")
        update_parser = subp.add_parser("update", help="change an app help")
        destroy_parser = subp.add_parser("destroy", help="destroy an app help")
        subp.add_parser("list-all", help="list all running apps")
        destroy_all_parser = subp.add_parser("destroy-all", help="remove the plugin help")
        self.add_init_parser_arguments(init_parser)
        self.add_make_parser_arguments(make_parser)
        self.add_describe_parser_arguments(describe_parser)
        self.add_update_parser_arguments(update_parser)
        self.add_destroy_parser_arguments(destroy_parser)
        self.add_destroy_all_parser_arguments(destroy_all_parser)

    def add_destroy_all_parser_arguments(self, parser: argparse.ArgumentParser):
        parser.add_argument("-y", "--yes", action='store_true', help="answer yes to prompt for confirmation")

    def add_init_parser_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--null-init-arg", action='store_true', help='set an init property of the null app')

    def add_make_parser_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--null-make-arg", action='store_true', help='set a make property of the null app')
        parser.add_argument("-n", "--app-name", required=True, help="name of the app")
        parser.add_argument("-y", "--yes", action='store_true', help="answer yes to prompt for confirmation")

    def add_describe_parser_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--null-describe-arg", action='store_true', help='set a describe property of the null app')
        parser.add_argument("-n", "--app-name", required=True, help="name of the app")

    def add_update_parser_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--null-update-arg", action='store_true', help='set an update property of the null app')
        parser.add_argument("-y", "--yes", action='store_true', help="answer yes to prompt for confirmation")
        parser.add_argument("-n", "--app-name", required=True, help="name of the app")

    def add_destroy_parser_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--null-destroy-arg", action='store_true', help='set a destroy property of the null app')
        parser.add_argument("-y", "--yes", action='store_true', help="answer yes to prompt for confirmation")
        parser.add_argument("-n", "--app-name", required=True, help="name of the app")
