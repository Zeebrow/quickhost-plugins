import logging

import boto3
from botocore.config import Config

from .constants import AWSConstants

logger = logging.getLogger(__name__)

class AWSResourceBase:

    def _get_session(self, profile, region):
        session = boto3.session.Session(profile_name=profile, region_name=region)
        return session

    def get_resource(self, resource, profile=AWSConstants.DEFAULT_IAM_USER, region=AWSConstants.DEFAULT_REGION):
        session = self._get_session(profile=profile, region=region)
        sts = session.client('sts')
        whoami = sts.get_caller_identity()
        whoami['username'] = self._get_user_name_from_arn(whoami['Arn'])
        whoami['region'] =  session.region_name
        whoami['profile'] =  session.profile_name
        _ = whoami.pop('ResponseMetadata')

        if self._get_user_name_from_arn(whoami['Arn']) != AWSConstants.DEFAULT_IAM_USER:
            logger.warning(f"You're about to do stuff with the non-quickhost user {whoami['Arn']}")
        return (whoami, session.resource(resource))

    def get_client(self, resource, profile=AWSConstants.DEFAULT_IAM_USER, region=AWSConstants.DEFAULT_REGION):
        session = self._get_session(profile=profile, region=region)
        sts = session.client('sts')
        whoami = sts.get_caller_identity()
        whoami['username'] = self._get_user_name_from_arn(whoami['Arn'])
        whoami['region'] =  session.region_name
        whoami['profile'] =  session.profile_name
        _ = whoami.pop('ResponseMetadata')

        if self._get_user_name_from_arn(whoami['Arn']) != AWSConstants.DEFAULT_IAM_USER:
            logger.warning(f"You're about to do stuff with the non-quickhost user {whoami['Arn']}")
        return (whoami, session.client(resource))

    def _get_user_name_from_arn(self, arn: str):
        return arn.split(":")[5].split("/")[-1]
