from .AWSApp import AWSApp
from argparse import ArgumentParser

def load_plugin(parser:ArgumentParser):
    parser.add_argument("--aws", action='store_true', dest='plugin_aws')
    return AWSApp
