from .AWSApp import AWSApp
from .PluginArgs import AWSParser
from .AWSSG import SG  # @@@ for tests ... ???


def get_parser():
    return AWSParser


def load_plugin():
    return AWSApp
