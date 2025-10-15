# --------------------------------------------------------------------------------
# SPDX-FileCopyrightText: 2025 Martin Jan Köhler
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
# along with this program. If not, see <http://www.gnu.org/licenses/>.
# SPDX-License-Identifier: GPL-3.0-or-later
#--------------------------------------------------------------------------------

from __future__ import annotations
from dataclasses import dataclass, asdict, field
from functools import cached_property
import json
from pathlib import Path
import traceback
from typing import *
import unittest

import pya

from klayout_plugin_utils.dataclass_dict_helpers import dataclass_from_dict
from klayout_plugin_utils.debugging import debug, Debugging
from klayout_plugin_utils.event_loop import EventLoop
from klayout_plugin_utils.json_helpers import JSONEncoderSupportingPaths
from klayout_plugin_utils.path_helpers import expand_path

#--------------------------------------------------------------------------------

@dataclass
class LibraryMapComment:
    comment: str


@dataclass(frozen=True)
class LibraryDefinition:
    lib_name: str
    lib_path: Path
    

@dataclass
class LibraryMapInclude:
    include_path: Path


LibraryMapStatement = Union[
    LibraryMapComment,
    LibraryDefinition,
    LibraryMapInclude,
]

#--------------------------------------------------------------------------------

@dataclass
class LibraryMapConfig:
    technology: str = ''
    statements: List[LibraryMapStatement] = field(default_factory=list)

    @classmethod
    def read_json(cls, path: Path) -> LibraryMapConfig:
        with open(path) as f:
            data = json.load(f)
            return dataclass_from_dict(cls, data)
        
    @classmethod
    def from_json_string(cls, json_string: str) -> LibraryMapConfig:
        data = json.loads(json_string)
        return dataclass_from_dict(cls, data)
        
    def write_json(self, path: Path):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(asdict(self), f, indent=4, cls=JSONEncoderSupportingPaths)

    def json_string(self) -> str:
        return json.dumps(asdict(self), indent=4, cls=JSONEncoderSupportingPaths)

    @cached_property
    def library_map_includes(self) -> List[LibraryMapInclude]:
        return [s for s in self.statements if isinstance(s, LibraryMapInclude)]

    @cached_property
    def library_definitions(self) -> List[LibraryDefinition]:
        return [s for s in self.statements if isinstance(s, LibraryDefinition)]

    @staticmethod
    def resolve_path(path: Path, base_folder: Path) -> Path:
        path = expand_path(path)
        if not path.is_absolute():
            path = Path(base_folder) / path
        path = path.resolve()
        return path
    
    def effective_library_definitions(self, base_folder: Path) -> List[LibraryDefinition]:
        """
        Resolve all includes to get the effective list of definitions
        """
        libs = []
        for s in self.statements:
            if isinstance(s, LibraryMapComment):
                continue
            elif isinstance(s, LibraryDefinition):
                libs += [LibraryDefinition(s.lib_name, self.resolve_path(s.lib_path, base_folder))]
            elif isinstance(s, LibraryMapInclude):
                if not s.include_path.is_file():
                    print(f"ERROR: library map file contains non-file include entry: {s.include_path}, ignoring…")
                    continue
                path = self.resolve_path(s.include_path, base_folder)
                config = LibraryMapConfig.read_json(path)
                libs += config.effective_library_definitions(base_folder=path.parent)
        return libs

#--------------------------------------------------------------------------------

class LibraryMapConfigTests(unittest.TestCase):
    def setUp(self):
        self.config = LibraryMapConfig(technology='sg13g2', statements=[
            LibraryMapComment('KLayout Library Manager Plugin: Cell library map file example'),
            LibraryMapComment('--------------------------------------------------------------'),
            LibraryMapComment('------------------- library definitions ----------------------'),
            LibraryDefinition('my_stdcells', Path('my_stdcells.gds.gz')),
            LibraryMapComment('--------------------------------------------------------------'),
            LibraryMapComment('------------------- other map file includes ------------------'),
            LibraryMapInclude(Path('default_lib.klib')),
        ])
        
    def test_read_write_example_library_map(self):
        lm = self.config
        lm_obtained = LibraryMapConfig.from_json_string(self.config.json_string())
        self.assertEqual('sg13g2', lm_obtained.technology)
        self.assertEqual(lm.statements[0].comment, lm_obtained.statements[0].comment)
        self.assertEqual(lm.statements[1].comment, lm_obtained.statements[1].comment)
        self.assertEqual(lm.statements[2].comment, lm_obtained.statements[2].comment)
        self.assertEqual(lm.statements[3].lib_name, lm_obtained.statements[3].lib_name)
        self.assertEqual(lm.statements[3].lib_path, lm_obtained.statements[3].lib_path)
        self.assertEqual(lm.statements[4].comment, lm_obtained.statements[4].comment)
        self.assertEqual(lm.statements[5].comment, lm_obtained.statements[5].comment)
        self.assertEqual(lm.statements[6].include_path, lm_obtained.statements[6].include_path)
        
    def test_resolution(self):
        cfg = LibraryMapConfig(technology='sg13g2', statements=[
            LibraryMapComment('KLayout Library Manager Plugin: Cell library map file example'),
            LibraryMapComment('--------------------------------------------------------------'),
            LibraryMapComment('------------------- library definitions ----------------------'),
            LibraryDefinition('my_stdcells', Path('my_stdcells.gds.gz'))
        ])
        
        obtained_libs = cfg.effective_library_definitions(base_folder='/home/foo')
        self.assertEqual(Path('/home/foo/my_stdcells.gds.gz').resolve(), obtained_libs[0].lib_path)

        
#--------------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main()
