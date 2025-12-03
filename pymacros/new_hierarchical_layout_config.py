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
from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import *

from klayout_plugin_utils.layer_list_string import LayerList
from klayout_plugin_utils.str_enum_compat import StrEnum

#--------------------------------------------------------------------------------

class LibraryMapCreationMode(StrEnum):
    CREATE_EMPTY = 'create_empty'
    LINK_TEMPLATE = 'link'
    COPY_TEMPLATE = 'copy'


@dataclass
class NewHierarchicalLayoutConfig:
    save_path: Optional[Path] = None
    library_map_creation_mode: LibraryMapCreationMode = LibraryMapCreationMode.CREATE_EMPTY
    library_map_template_path: Optional[Path] = None  # create empty map if None
    
    tech_name: Optional[str] = None  # None means default
    top_cell: Optional[str] = 'TOP'
    dbu_um: Optional[float] = None   # None means default
    initial_window_um: float = 2.0
    initial_layers: LayerList = field(default_factory=LayerList)
