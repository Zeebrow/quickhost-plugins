import logging
import shutil
from pathlib import Path
from tempfile import mkstemp
import os, sys

from botocore.exceptions import ClientError

import quickhost
from quickhost import APP_CONST as C
#try:
#    from .constants import *
#except:
#    from constants import *
#try:
#    from .temp_data_collector import store_test_data
#except:
#    from temp_data_collector import store_test_data

logger = logging.getLogger(__name__)

class KP:
    def __init__(self, client: any, app_name: str, ssh_key_filepath: str, key_name=None, dry_run=True):
        self.client = client
        self.app_name = app_name
        self.ssh_key_filepath = ssh_key_filepath
        self.dry_run = dry_run
        self.key_name = key_name
        if not self.key_name:
            self.key_name = app_name
        self._key_id = None
        self._fingerprint = None

    def get_key_id(self) -> dict:
        """
        call aws to get existing ec2 key
        returns None if the ex2 key does not exist
        """
        try: 
            _existing_key = self.client.describe_key_pairs(
                KeyNames=[
                    self.app_name
                ],
                DryRun=False,
                # @@@No idea why the docs differ so much from what I'm able to code
                # It just means less copy-pasting, I suppose.
                #IncludePublicKey=True
            )
        except ClientError as e:
            if 'InvalidKeyPair.NotFound' in str(e):
                # SG does not exist
                return None
            else:
                # bug
                print('something went wrong!')
                print(e.with_traceback)
                return None

        if len(_existing_key['KeyPairs']) > 1:
            logger.warning(f"WARN: Found more than 1 key pair named '{self.app_name}' in result set")
            logger.debug(_existing_key)
            return None
        self.key_id = _existing_key['KeyPairs'][0]['KeyPairId']
        self._fingerprint = _existing_key['KeyPairs'][0]['KeyFingerprint']
        #quickhost.store_test_data(resource='KP', action='get_key_id', response_data=_existing_key)
        return self.key_id

    def create(self) -> dict:
        """Make a new ec2 keypair named for app"""
        print('creating ec2 key pair...', end='')
        if self.ssh_key_filepath is None:
            # not overriden from config, set default
            tgt_file = Path(f"./{self.app_name}.pem")
        else:
            if not self.ssh_key_filepath.endswith('.pem'):
                tgt_file = Path(f"{self.ssh_key_filepath}.pem")
            else:
                tgt_file = Path(self.ssh_key_filepath)
        if tgt_file.exists():
            logger.error(f"pem file '{tgt_file.absolute()}' already exists")
            exit(1)

        _new_key = self.client.create_key_pair(
            KeyName=self.key_name,
            DryRun=self.dry_run,
            KeyType='rsa',
            TagSpecifications=[
                {
                    'ResourceType': 'key-pair',
                    'Tags': [
                        { 'Key': C.DEFAULT_APP_NAME, 'Value': self.app_name},
                    ]
                },
            ],
            # @@@Why is this param throwing errors, can't be shitty docs...
            #KeyFormat='pem'
        )

        # save pem
        with tgt_file.open('w') as pemf:
            pemf.writelines(_new_key['KeyMaterial'])
        if sys.platform == 'linux':
            # shoutout for the 'o'
            # https://stackoverflow.com/questions/16249440/changing-file-permission-in-python
            os.chmod(tgt_file.absolute(), 0o600)
        else:
            logger.warning(f"unsupported platform '{sys.platform}'")
            logger.warning(f"you may have to manage ssh key permissions yourself to login successfully.")
        logger.info(f"saved private key to file '{tgt_file.absolute()}'")
        self.key_id = _new_key['KeyPairId']
        self._fingerprint = _new_key['KeyFingerprint']
        _testdata = _new_key
        if 'KeyMaterial' in _testdata.keys():
            _testdata['KeyMaterial'] = """ -----BEGIN RSA PRIVATE KEY-----
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
-----END RSA PRIVATE KEY-----
"""
        #quickhost.store_test_data(resource='KP', action='get_key_id', response_data=_testdata)
        del _new_key
        print(f"done ({self.key_id})")
        return self.key_id

    def destroy(self) -> bool:
        if self._id is None:
            self._id = self.get_key_pair()['KeyPairId']
        try:
            _del_key = self.client.delete_key_pair(
                KeyName=self.app_name,
                KeyPairId=self._id,
                DryRun=self.dry_run
            )
            #quickhost.store_test_data(resource='KP', action='destroy', response_data=_del_key)
            return True
        except ClientError as e:
            logger.warning(f"failed to delete keypair for app '{self.app_name}' (id: '{self._id}'):\n {e}")
            return False

    def update(self):
        """Not implemented"""
        pass

    def describe(self):
        _existing_key = self.client.describe_key_pairs(
            KeyNames=[
                self.app_name
            ],
            DryRun=False,
            # @@@The docs clearly show this param: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_key_pairs
            # but it throws an error
            IncludePublicKey=True
        )
        self.key_id = _existing_key['KeyPairs'][0]['KeyPairId']
        self._fingerprint = _existing_key['KeyPairs'][0]['KeyFingerprint']
        return _existing_key


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

