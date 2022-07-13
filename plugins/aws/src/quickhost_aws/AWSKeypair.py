import logging
import json
import shutil
from pathlib import Path
from tempfile import mkstemp
import os, sys

from botocore.exceptions import ClientError

import quickhost
from quickhost import APP_CONST as C
from quickhost import store_test_data, scrub_datetime

from .utilities import get_single_result_id, handle_client_error, UNDEFINED
from .AWSResource import AWSResourceBase
from .constants import AWSConstants

logger = logging.getLogger(__name__)

class KP(AWSResourceBase):
    #def __init__(self, client: any, ec2_resource: any, app_name: str, ssh_key_filepath=None, key_name=None, dry_run=True):
    def __init__(self, app_name: str, profile=AWSConstants.DEFAULT_IAM_USER, region=AWSConstants.DEFAULT_REGION):
        self._client_caller_info, self.client = self.get_client('ec2', profile=profile, region=region)
        self._resource_caller_info, self.ec2 = self.get_resource('ec2', profile=profile, region=region)
        if self._client_caller_info == self._resource_caller_info:
            self.caller_info = self._client_caller_info
        self.app_name = app_name
        self.key_name = app_name 
        self.key_filepath = C.DEFAULT_SSH_KEY_FILE_DIR / f"{self.key_name}.pem"

    def get_key_id(self) -> str:
        try:
            existing_key = self.client.describe_key_pairs(
                KeyNames=[
                    self.app_name
                ],
                DryRun=False,
                IncludePublicKey=True
            )
        except ClientError as e: 
            return None
        return get_single_result_id(resource=existing_key, resource_type='KeyPair', plural=True)

    def _create_ssh_key_file(key_material: str, ssh_key_filepath=None):
        rtn = True
        if ssh_key_filepath is None:
            # not overriden from config, set default
            # @@@ just use ~/.ssh...
            # @@@ actually dont
            tgt_file = Path(f"./{self.app_name}.pem")
        else:
            if not ssh_key_filepath.endswith('.pem'):
                tgt_file = Path(f"{ssh_key_filepath}.pem")
            else:
                tgt_file = Path(ssh_key_filepath)
        if tgt_file.exists():
            logger.warning(f"overwriting pem file '{tgt_file.absolute()}'")
            rtn = False

        try:
            with tgt_file.open('w') as pemf:
                pemf.writelines(key_material)
                os.chmod(tgt_file.absolute(), 0o600)
            logger.debug(f"saved private key to file '{tgt_file.absolute()}'")
        except Exception as e:
            logger.error(f"Exception creating ssh keyfile: {e}")
            rtn = False

        return rtn
        
    def create(self, ssh_key_filepath=None) -> bool:
        """Make a new ec2 keypair named for app"""
        existing_key_pair = self.describe()
        self.key_id = existing_key_pair['key_id']
        self.key_fingerprint = existing_key_pair['key_id']

        if self.key_id is not None:
            #NOTE: You can't retreive key material unless you are creating the key
            logger.warning(f"Ssh key already exists with id '{self.key_id}'")
        else:
            rtn = True
            new_key = self.client.create_key_pair(
                KeyName=self.key_name,
                DryRun=False,
                KeyType='rsa',
                TagSpecifications=[
                    {
                        'ResourceType': 'key-pair',
                        'Tags': [
                            { 'Key': C.DEFAULT_APP_NAME, 'Value': self.app_name},
                        ]
                    },
                ],
            )
            safe_response = new_key
            safe_response['KeyMaterial'] = "XXXXXXXXXX"
            store_test_data(resource='AWSKeyPair', action='create_key_pair', response_data=new_key)

            rtn = self._create_ssh_key_file(new_key['KeyMaterial'], ssh_key_filepath=ssh_key_filepath)
            self.key_id = new_key['KeyPairId']
            self.fingerprint = new_key['KeyFingerprint']
            del new_key
            return rtn

    def describe(self):
        rtn = {
            'key_id': None,
            'key_fingerprint': None,
        }
        try:
            existing_key = self.client.describe_key_pairs(
                KeyNames=[ self.app_name ],
                DryRun=False,
                IncludePublicKey=True
            )
            rtn['key_id']           = existing_key['KeyPairs'][0]['KeyPairId']
            rtn['key_fingerprint']  = existing_key['KeyPairs'][0]['KeyFingerprint']
            store_test_data(resource='AWSKeypair', action='describe_key_pairs', response_data=scrub_datetime(existing_key))
            return rtn
        except ClientError as e:
            code = e.__dict__['response']['Error']['Code']
            if code == 'InvalidKeyPair.NotFound':
                logger.debug(f"({code}): {e.operation_name}")
                rtn['key_id'] = None
                rtn['key_fingerprint'] = None
                return rtn
            else:
                logger.error(f"(Key Pair) Unhandled botocore client exception: ({code}): {e}")
                return rtn

    def destroy(self, ssh_key_file=None) -> bool:
        if not ssh_key_file:
            ssh_key_file=Path(self.app_name + '.pem')
        key_id = self.get_key_id()
        if not key_id:
            logger.warning(f"No key for app '{self.app_name}'")
            return False
        try:
            del_key = self.client.delete_key_pair(
                KeyPairId=key_id,
                DryRun=False
            )
            print(f"{del_key=}")
            store_test_data(resource='AWSKeyPair', action='delete_key_pair', response_data=del_key)
            if ssh_key_file.exists():
                os.remove(ssh_key_file)
                logger.debug(f"removed keyfile '{ssh_key_file.name}'")
                return True
            else:
                logger.warning(f"Couldn't find key file '{ssh_key_file.name}' to remove!")
                return False
        except ClientError as e:
            handle_client_error(e)
            logger.warning(f"failed to delete keypair for app '{self.app_name}' (id: '{key_id}'):\n {e}")
            return False

    def update(self):
        """Not implemented"""
        pass


if __name__ == '__main__':
    import boto3
    import json
    c = boto3.client('ec2')
    kp = KP(client=c, app_name='asdf', ssh_key_filepath='.', dry_run=False )
    #print(json.dumps(kp.get_key_pair(),indent=2))
    #print(kp.destroy())
    #print(json.dumps(kp.create(),indent=2))
    print()
    print(json.dumps(kp.describe(), indent=2))

