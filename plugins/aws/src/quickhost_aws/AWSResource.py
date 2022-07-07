import boto3

from .constants import AWSConstants

class AWSResourceBase:
    def get_resource(self, resource, profile=None):
        if profile is None:
            # use ye olde trodden foodchain
            session = boto3.session.Session(profile_name=AWSConstants.DEFAULT_IAM_USER)
            sts = session.client('sts')
            whoami = sts.get_caller_identity()['Arn']
        else:
            session = boto3.session.Session(profile_name=profile)
            sts = session.client('sts')
            whoami = sts.get_caller_identity()['Arn']
        #return (whoami, session.resource(resource))
        return session.resource(resource)
    def get_client(self, resource, profile=None):
        if profile is None:
            # use ye olde trodden foodchain
            session = boto3.session.Session(profile_name=AWSConstants.DEFAULT_IAM_USER)
            sts = session.client('sts')
            whoami = sts.get_caller_identity()['Arn']
        else:
            session = boto3.session.Session(profile_name=profile)
            sts = session.client('sts')
            whoami = sts.get_caller_identity()['Arn']
        #return (whoami, session.client(resource))
        return session.client(resource)
