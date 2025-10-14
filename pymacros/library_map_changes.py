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
from pathlib import Path
import traceback
from typing import *
import unittest

import pya

from klayout_plugin_utils.dataclass_dict_helpers import dataclass_from_dict
from klayout_plugin_utils.debugging import debug, Debugging

from library_map_config import (
    LibraryMapConfig,
    LibraryDefinition
)

#--------------------------------------------------------------------------------

@dataclass
class LibraryMapChanges:
    added_libs: List[LibraryDefinition] = field(default_factory=list)
    removed_libs: List[LibraryDefinition] = field(default_factory=list)
    renamed_libs: List[Tuple[LibraryDefinition, LibraryDefinition]] = field(default_factory=list)
    repathed_libs: List[Tuple[LibraryDefinition, LibraryDefinition]] = field(default_factory=list)

    @classmethod
    def compare(self, 
                base_folder: Path, 
                old_config: LibraryMapConfig,
                new_config: LibraryMapConfig) -> LibraryMapChanges:
        # if we have a layout containing cells, referencing to a renamed library
        # we want to change the references to the new name

        new_lib_defs = new_config.effective_library_definitions(base_folder)
        old_lib_defs = old_config.effective_library_definitions(base_folder)
        
        old_lib_defs_by_path = {ld.lib_path: ld for ld in old_lib_defs}
        new_lib_defs_by_path = {ld.lib_path: ld for ld in new_lib_defs}
        new_lib_defs_by_name = {ld.lib_name: ld for ld in new_lib_defs}
        
        added_libs: List[LibraryDefinition] = []
        removed_libs: List[LibraryDefinition] = []
        renamed_libs: List[Tuple[LibraryDefinition, LibraryDefinition]] = []
        repathed_libs: List[Tuple[LibraryDefinition, LibraryDefinition]] = []
        
        handled_new_lib_defs: Set[LibraryDefinition] = set()
        
        for path, old_def in old_lib_defs_by_path.items():
            new_def = new_lib_defs_by_path.get(path, None)
            if new_def is None:  # lib was removed (or got other path?)
                new_def_for_name = new_lib_defs_by_name.get(old_def.lib_name, None)
                if new_def_for_name is not None:
                    repathed_libs.append((old_def, new_def_for_name))
                    handled_new_lib_defs.add(new_def_for_name)
                else:
                    removed_libs.append(old_def)
            else:
                if old_def != new_def:
                    renamed_libs.append((old_def, new_def))
                handled_new_lib_defs.add(new_def)
        
        for new_def in new_lib_defs:
            if new_def not in handled_new_lib_defs:
                handled_new_lib_defs.add(new_def)
                added_libs.append(new_def)
        
        return LibraryMapChanges(added_libs=added_libs,
                                 removed_libs=removed_libs,
                                 renamed_libs=renamed_libs,
                                 repathed_libs=repathed_libs)
        
#--------------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main()
