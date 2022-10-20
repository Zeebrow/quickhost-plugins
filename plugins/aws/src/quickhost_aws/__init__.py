from .AWSApp import AWSApp
from .PluginArgs import AWSParser

def get_parser():
    return AWSParser

def load_plugin():
    return AWSApp

#@@@ for tests
from .AWSSG import SG