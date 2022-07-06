import boto3

from .constants import AWSConstants

class AWSResourceBase:
    def get_resource(self, resource, profile=None):
        if profile is None:
            # use ye olde trodden foodchain
            session = boto3.session.Session(profile_name=AWSConstants.DEFAULT_IAM_USER)
        else:
            session = boto3.session.Session(profile_name=profile)
        return session.resource(resource)
    def get_client(self, resource, profile=None):
        if profile is None:
            # use ye olde trodden foodchain
            session = boto3.session.Session(profile_name=AWSConstants.DEFAULT_IAM_USER)
        else:
            session = boto3.session.Session(profile_name=profile)
        return session.client(resource)
