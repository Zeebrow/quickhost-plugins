from typing import List
from dataclasses import dataclass
from argparse import Namespace, SUPPRESS
from abc import ABCMeta, abstractmethod
import configparser
import logging
from os import get_terminal_size

from .utilities import get_my_public_ip
from .constants import *

logger = logging.getLogger(__name__)


class AppConfigFileParser(configparser.ConfigParser):
    def __init__(self):
        super().__init__(allow_no_value=True)

class AppBase(metaclass=ABCMeta):
    def __init__(self, _cli_parser_id: str, app_name: str, config_file=DEFAULT_CONFIG_FILEPATH):
        """should there actually be logic here? in the same vain, more than just primitive data types?"""
        self._cli_parser_id = _cli_parser_id
        self.app_name = app_name
        self.config_file = Path(config_file).absolute()
        if not self.config_file.exists():
            raise RuntimeError(f"no such file: {self.config_file}")
        if self._cli_parser_id is None:
            raise Exception("need a cli_parser_id")

    @abstractmethod
    def load_default_config(self):
        """get possible config from file"""
        pass

    @abstractmethod
    def run(self):
        """get remaining config from argparse namespace"""
        pass

    @classmethod
    @abstractmethod
    def parser_arguments(self, subparsers: any) -> None:
        """modify main ArgumentParser to accept arguments required by plugin"""
        pass

# maybe all crud's should exit instead of return
    @abstractmethod
    def create(self):
        """
        do the needful to get app up
        should promptly exit after returning
        """
        pass

    @abstractmethod
    def describe(self) -> dict:
        """return information about resources in the target app"""
        pass

    @abstractmethod
    def update(self):
        """change the app in some way"""
        pass
        
    @abstractmethod
    def destroy(self):
        """
        delete all resources associated with your app
        should promptly exit after returning
        """
        pass
        
class QuickhostApp(metaclass=ABCMeta):
    def __init__(self):
        pass

    @abstractmethod
    def parser_arguments(self, subparser: any) -> None:
        """Add required arguments to a parser"""
        pass

    @abstractmethod
    def _print_loaded_args(self) -> None:
        pass
