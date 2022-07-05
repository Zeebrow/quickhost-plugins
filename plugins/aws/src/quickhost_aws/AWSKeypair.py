import logging
import json
import shutil
from pathlib import Path
from tempfile import mkstemp
import os, sys

from botocore.exceptions import ClientError

import quickhost
from quickhost import APP_CONST as C
from quickhost.temp_data_collector import store_test_data

from .utilities import get_single_result_id, handle_client_error

logger = logging.getLogger(__name__)

class KP:
    #def __init__(self, client: any, ec2_resource: any, app_name: str, ssh_key_filepath=None, key_name=None, dry_run=True):
    def __init__(self, client: any, ec2_resource: any, app_name: str):
        self.client = client
        self.app_name = app_name
        self.ec2 = ec2_resource
        self.key_name = app_name 
        self.key_filepath = C.DEFAULT_SSH_KEY_FILE_DIR / f"{self.key_name}.pem"

    def get_key_id(self) -> str:
        try:
            existing_key = self.client.describe_key_pairs(
                KeyNames=[
                    self.app_name
                ],
                DryRun=False,
                # @@@No idea why the docs differ so much from what I'm able to code
                # It just means less copy-pasting, I suppose.
                #IncludePublicKey=True
            )
        except ClientError as e: 
            logger.debug(f"No key for app '{self.app_name}'?\n{e}")
            return None
        return get_single_result_id(resource=existing_key, resource_type='KeyPair', plural=True)
        
    def create(self, ssh_key_filepath=None):
        """Make a new ec2 keypair named for app"""
        print('creating ec2 key pair...', end='')
        if ssh_key_filepath is None:
            # not overriden from config, set default
            # @@@ just use ~/.ssh...
            tgt_file = Path(f"./{self.app_name}.pem")
        else:
            if not ssh_key_filepath.endswith('.pem'):
                tgt_file = Path(f"{ssh_key_filepath}.pem")
            else:
                tgt_file = Path(ssh_key_filepath)
        if tgt_file.exists():
            logger.error(f"pem file '{tgt_file.absolute()}' already exists")
            return False

        new_key = self.client.create_key_pair(
            KeyName=self.key_name,
            DryRun=False,
            KeyType='rsa',
            TagSpecifications=[
                {
                    'ResourceType': 'key-pair',
                    'Tags': [
                        { 'Key': QHC.DEFAULT_APP_NAME, 'Value': self.app_name},
                    ]
                },
            ],
        )

        with tgt_file.open('w') as pemf:
            pemf.writelines(new_key['KeyMaterial'])
        if sys.platform == 'linux':
            os.chmod(tgt_file.absolute(), 0o600)
        logger.debug(f"saved private key to file '{tgt_file.absolute()}'")
        self.key_id = new_key['KeyPairId']
        self.fingerprint = new_key['KeyFingerprint']
        del new_key
        print(f"done ({self.key_id})")
        return

    def describe(self):
        try:
            existing_key = self.client.describe_key_pairs(
                KeyNames=[ self.app_name ],
                DryRun=False,
                # @@@The docs clearly show this param: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_key_pairs
                # but it throws an error
                IncludePublicKey=True
            )
            key_id = existing_key['KeyPairs'][0]['KeyPairId']
            fingerprint = existing_key['KeyPairs'][0]['KeyFingerprint']
        except ClientError as e:
            code = e['Error']['Code']
            if code == 'UnauthorizedOperation':
                logger.error(f"({code}): {e.operation_name}")
                return {
                    'key_id': '?',
                    'key_fingerprint': '?'
                }
            else:
                logger.error(f"(Key Pair) Unhandled botocore client exception: ({e.response['Error']['Code']}): {e.response['Error']['Message']}")
                return {
                    'key_id': None,
                    'fingerprint': None
                }
        return {
                'key_id': key_id,
                'key_fingerprint': fingerprint
        }

    def destroy(self, ssh_key_file=None) -> bool:
        if not ssh_key_file:
            ssh_key_file=Path(self.app_name + '.pem')
        key_id = self.get_key_id()
        if not key_id:
            logger.debug(f"No key for app '{self.app_name}'")
            return False
        try:
            del_key = self.client.delete_key_pair(
                KeyName=self.app_name,
                KeyPairId=key_id,
                DryRun=False
            )
            print(f"{del_key=}")
            #quickhost.store_test_data(resource='KP', action='destroy', response_data=_del_key)
            if ssh_key_file.exists():
                os.remove(ssh_key_file)
                logger.debug(f"removed keyfile '{ssh_key_file.name}'")
            else:
                logger.warning(f"Couldn't find key file '{ssh_key_file.name}' to remove!")
            return True
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

