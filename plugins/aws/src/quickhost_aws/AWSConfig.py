from dataclasses import dataclass
from typing import NewType, List
from collections import namedtuple

"""
These are utility functions, types, etc.
This module should only import from the standard library.
"""

Region = NewType('Region', str)
Port = NewType('Port', int)
Cidr = NewType('Cidr', str)
#HostState = NewType('HostState', str)

@dataclass
class AWSHostConfig:
    app_name: str
    region: Region
    host_count: int

class HostState:
    running = 'running'
    pending = 'pending' 
    shutting_down = 'shutting-down' 
    terminated = 'terminated' 
    stopping = 'stopping' 
    stopped = 'stopped' 
    @classmethod
    def allofem(self):
        return [
            "running",
            "pending",
            "shutting_down",
            "terminated",
            "stopping",
            "stopped",
        ]
    @classmethod
    def butnot(self,*states):
        rtn = list(HostState.allofem())
        [rtn.remove(i) for i in states]
        return rtn

@dataclass
class AWSSgConfig:
    app_name: str
    region: Region
    vpc_id: str
    ports: List[Port]
    cidrs: List[Cidr]





