# Copyright (C) 2022 zeebrow
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from pathlib import Path

from quickhost import AppBase, APP_CONST as C

"""
The null plugin is used to test the main app.
"""


class NullApp(AppBase):
    def __init__(self, app_name, config_file=C.DEFAULT_CONFIG_FILEPATH):
        self.app_name = app_name
        self.config_file = Path(config_file).absolute()
        if not self.config_file.exists():
            raise RuntimeError(f"no such file: {self.config_file}")

    @classmethod
    def about(self):
        return """
<program>  Copyright (C) <year>  <name of author>
This program comes with ABSOLUTELY NO WARRANTY; for details type `show w'.
This is free software, and you are welcome to redistribute it
under certain conditions; type `show c' for details.
        """
        # return ("null plugin", 0, 0, 1)

    def load_default_config(self):
        """get possible config from file"""
        pass

    def plugin_init(self, args):
        [print(f"{k}: {v}") for k, v in args.items()]
        """Account setup, networking, etc. required to use plugin"""
        return ("null", "null", "null")

    def create(self, args):
        [print(f"{k}: {v}") for k, v in args.items()]
        """ Start hosts """
        return ("null", "null", "null")

    def describe(self, args) -> dict:
        [print(f"{k}: {v}") for k, v in args.items()]
        """return information about hosts in the target app"""
        return ("null", "null", "null")

    def update(self, args):
        [print(f"{k}: {v}") for k, v in args.items()]
        """change the hosts in some way"""
        return ("null", "null", "null")

    def destroy(self, args):
        [print(f"{k}: {v}") for k, v in args.items()]
        """ delete all hosts associated with your app """
        return ("null", "null", "null")

    @classmethod
    def list_all(self):
        return ("null", "null", 0)

    @classmethod
    def destroy_all(self):
        return ("stdout null", "stderr null", 0)
