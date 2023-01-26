from .NullApp import NullApp
from .NullParser import NullParser


def load_plugin():
    return NullApp


def get_parser():
    return NullParser
