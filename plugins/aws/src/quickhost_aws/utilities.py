import datetime
import json
import urllib.request

def convert_datetime_to_string(thing):
    """
    Remove all datetime objects from a dict, and convert them to a string
    """
    if isinstance(thing, dict):
        for k,v in thing.items():
            thing[k] = convert_datetime_to_string(v)
    elif isinstance(thing, list):
        for i,a in enumerate(thing):
            thing[i] = convert_datetime_to_string(a)
    elif isinstance(thing, datetime.datetime):
        thing = str(thing)
    else:
        return thing
    return thing

def get_my_public_ip() -> str:
    # what could possibly be better?!
    try:
        with urllib.request.urlopen("https://ipv4.icanhazip.com") as r:
            html = r.read()
            return html.decode('utf-8').strip() + "/32"
    except Exception:
        return input('Could not determine your public ip address (are you connected to the internet?). Enter it here (Ctrl^C to cancel): ')
