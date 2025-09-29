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
import traceback

import pya

from klayout_plugin_utils.debugging import debug, Debugging
from klayout_plugin_utils.file_system_helpers import FileSystemHelpers
from klayout_plugin_utils.layer_list_string import LayerList
from klayout_plugin_utils.str_enum_compat import StrEnum

from constants import FILE_SUFFIX_HIERARCHICAL_LAYOUT, FILE_SUFFIX_LIBRARY_MAP


#--------------------------------------------------------------------------------

path_containing_this_script = os.path.realpath(os.path.dirname(__file__))

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
    
    technology: Optional[pya.Technology] = None  # None means default
    top_cell: Optional[str] = 'TOP'
    dbu_um: Optional[float] = None   # None means default
    initial_window_um: float = 2.0
    initial_layers: LayerList = field(default_factory=LayerList)


class NewHierarchicalLayoutDialog(pya.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('New Hierarchical Layout')
        self.setWindowModality(pya.Qt.ApplicationModal)
        
        loader = pya.QUiLoader()
        ui_path = os.path.join(path_containing_this_script, "NewHierarchicalLayoutDialog.ui")
        ui_file = pya.QFile(ui_path)
        try:
            ui_file.open(pya.QFile.ReadOnly)
            self.page = loader.load(ui_file, self)
        finally:
            ui_file.close()

        self.bottom = pya.QHBoxLayout()
        self.okButton = pya.QPushButton('OK')
        self.cancelButton = pya.QPushButton('Cancel')
        
        self.bottom.addStretch(1)
        
        self.bottom.addWidget(self.okButton)
        self.bottom.addWidget(self.cancelButton)
        
        layout = pya.QVBoxLayout(self)
        layout.addWidget(self.page)
        layout.addLayout(self.bottom)
        
        self.okButton.clicked.connect(self.on_ok)
        self.cancelButton.clicked.connect(self.on_cancel)
        
        self.okButton.setDefault(True)
        self.okButton.setAutoDefault(True)
        self.cancelButton.setAutoDefault(False)

        self.page.browse_save_path_pb.clicked.connect(self.on_browse_save_path)
        self.page.browse_template_map_pb.clicked.connect(self.on_browse_template_map_path)
        self.page.create_empty_map_rb.toggled.connect(self.on_radio_buttons_changed)
        self.page.use_existing_map_rb.toggled.connect(self.on_radio_buttons_changed)
        
        self.page.tech_cbx.clear()
        tech_names = [n if n != '' else '(Default)' \
                      for n in pya.Technology.technology_names()]
        self.page.tech_cbx.addItems(tech_names)
        
        preconfigured_tech: Optional[pya.Technology] = None
        cv = pya.CellView.active()
        if cv.is_valid():
            preconfigured_tech = cv.layout().technology()
        if preconfigured_tech is not None:
            tech_name = preconfigured_tech.name or '(Default)'
            self.page.tech_cbx.setCurrentText(tech_name)
            self.page.dbu_le.placeholderText = preconfigured_tech.dbu
        
        config = NewHierarchicalLayoutConfig()
        config.save_path = Path(FileSystemHelpers.least_recent_directory() or os.getcwd()) / \
                           f"{config.top_cell.lower() or 'top'}{FILE_SUFFIX_HIERARCHICAL_LAYOUT}"
        self.update_ui_from_config(config)
        
        self._config = None
        
    def get_config(self) -> NewHierarchicalLayoutConfig:
        """
        Get the resulting config after OK was pressed
        """
        return self._config
        
    def set_field_valid(self, widget: pya.QLineEdit, valid: bool):
        if valid:
            widget.setStyleSheet('')  # reset to default
        else:
            widget.setStyleSheet('background-color: rgba(255, 0, 0, 50);')  # light red
        
    def validate_ui_inputs(self):
        valid = True
    
        save_path_str = self.page.save_path_le.text.strip()
        save_path = Path(save_path_str) if save_path_str else None
        if not save_path_str:
            self.set_field_valid(self.page.save_path_le, False)
            valid = False
        else:
            save_path = Path(save_path_str)
            parent_dir = save_path.parent
            if not parent_dir.exists() or not parent_dir.is_dir():
                self.set_field_valid(self.page.save_path_le, False)
                valid = False
            elif save_path.suffix.lower() != FILE_SUFFIX_HIERARCHICAL_LAYOUT:
                self.set_field_valid(self.page.save_path_le, False)
                valid = False
            else:
                self.set_field_valid(self.page.save_path_le, True)
    
        if self.page.use_existing_map_rb.checked:
            template_path_str = self.page.template_path_le.text.strip()
            template_path = Path(template_path_str) if template_path_str else None
            if not template_path or not template_path.exists() or not template_path.is_file():
                self.set_field_valid(self.page.template_path_le, False)
                valid = False
            else:
                self.set_field_valid(self.page.template_path_le, True)
        else:
            self.set_field_valid(self.page.template_path_le, True)
    
        dbu_str = self.page.dbu_le.text.strip()
        try:
            dbu = float(dbu_str) if dbu_str else None
            if dbu is not None and dbu <= 0:
                raise ValueError
            self.set_field_valid(self.page.dbu_le, True)
        except ValueError:
            self.set_field_valid(self.page.dbu_le, False)
            valid = False
    
        try:
            window = float(self.page.window_le.text.strip())
            if window <= 0:
                raise ValueError
            self.set_field_valid(self.page.window_le, True)
        except ValueError:
            self.set_field_valid(self.page.window_le, False)
            valid = False
    
        top_cell = self.page.topcell_le.text.strip()
        if top_cell and not top_cell.replace("_", "").isalnum():
            self.set_field_valid(self.page.topcell_le, False)
            valid = False
        else:
            self.set_field_valid(self.page.topcell_le, True)
    
        layers_str = self.page.layers_le.text
        if LayerList.is_valid_layer_list_string(layers_str):
            self.set_field_valid(self.page.layers_le, True)
        else:
            valid = False
            self.set_field_valid(self.page.layers_le, False)
                        
        return valid
        
    def config_from_ui(self) -> NewHierarchicalLayoutConfig:
        save_path_str = self.page.save_path_le.text.strip()
        save_path = Path(save_path_str) if save_path_str else None

        mode: LibraryMapCreationMode
        template_path: Optional[Path]
        
        if self.page.create_empty_map_rb.checked:
            mode = LibraryMapCreationMode.CREATE_EMPTY
            template_path = None
        else:
            mode_index = self.page.include_or_copy_template_map_cb.currentIndex()
            mode = LibraryMapCreationMode.LINK_TEMPLATE if mode_index == 0 else LibraryMapCreationMode.COPY_TEMPLATE
            template_path_str = self.page.template_path_le.text.strip()
            template_path = Path(template_path_str) if template_path_str else None
        
        dbu_str = self.page.dbu_le.text.strip()
        dbu_um = float(dbu_str) if dbu_str else None
        
        window_str = self.page.window_le.text.strip()
        initial_window_um = float(window_str) if window_str else 2.0
        
        tech_name = self.page.tech_cbx.currentText
        if tech_name == 'Default': tech_name = None
        technology = pya.Technology.technology_by_name(tech_name)
        
        layers_str = self.page.layers_le.text
        layer_list_parse_result = LayerList.parse_layer_list_string(layers_str)
        initial_layers = layer_list_parse_result.result if len(layer_list_parse_result.errors) == 0 else LayerList()
        
        return NewHierarchicalLayoutConfig(
            save_path=save_path,
            library_map_creation_mode=mode,
            library_map_template_path=template_path,
            technology=technology,
            top_cell=self.page.topcell_le.text.strip() or 'TOP',
            dbu_um=dbu_um,
            initial_window_um=initial_window_um,
            initial_layers=initial_layers
        )
    
    def update_ui_from_config(self, config: NewHierarchicalLayoutConfig):
        if Debugging.DEBUG:
            debug("LibraryManagerDialog.update_ui_from_config")
        
        self.page.save_path_le.setText('' if config.save_path is None else str(config.save_path))
        
        match config.library_map_creation_mode:
            case LibraryMapCreationMode.CREATE_EMPTY:
                self.page.create_empty_map_rb.setChecked(True)
                self.page.use_existing_map_rb.setChecked(False)
                self.page.include_or_copy_template_map_cb.setEnabled(False)
                self.page.template_path_le.setEnabled(False)
                self.page.browse_template_map_pb.setEnabled(False)
            case LibraryMapCreationMode.LINK_TEMPLATE:
                self.page.create_empty_map_rb.setChecked(False)
                self.page.use_existing_map_rb.setChecked(True)
                self.page.include_or_copy_template_map_cb.setEnabled(True)
                self.page.include_or_copy_template_map_cb.setCurrentIndex(0)
                self.page.template_path_le.setEnabled(True)
                self.page.browse_template_map_pb.setEnabled(True)
            case LibraryMapCreationMode.COPY_TEMPLATE:
                self.page.create_empty_map_rb.setChecked(False)
                self.page.use_existing_map_rb.setChecked(True)
                self.page.include_or_copy_template_map_cb.setEnabled(True)
                self.page.include_or_copy_template_map_cb.setCurrentIndex(1)
                self.page.template_path_le.setEnabled(True)
                self.page.browse_template_map_pb.setEnabled(True)
                
        self.page.template_path_le.setText(
            '' if config.library_map_template_path is None else str(config.library_map_template_path)
        )
        
        # NOTE: self.page.tech_cbx is handled in ctor
        
        self.page.topcell_le.setText('' if config.top_cell is None else str(config.top_cell))
        self.page.dbu_le.setText('' if config.dbu_um is None else str(config.dbu_um))
        self.page.window_le.setText('' if config.initial_window_um is None else str(config.initial_window_um))
        self.page.layers_le.setText(str(config.initial_layers))
        
        self.on_radio_buttons_changed()
        
    def on_ok(self):
        if Debugging.DEBUG:
            debug("NewHierarchicalLayoutDialog.on_ok")
        
        try:
            if self.validate_ui_inputs():
                self._config = self.config_from_ui()
                self.accept()
        except Exception as e:
            print("NewHierarchicalLayoutDialog.on_ok caught an exception", e)
            traceback.print_exc()

    def on_cancel(self):
        if Debugging.DEBUG:
            debug("NewHierarchicalLayoutDialog.on_cancel")
        self.reject()
    
    def on_radio_buttons_changed(self):
        if Debugging.DEBUG:
            debug("NewHierarchicalLayoutDialog.on_radio_buttons_changed")
            
        try:
            if self.page.create_empty_map_rb.checked:
                self.page.include_or_copy_template_map_cb.setEnabled(False)
                self.page.template_path_le.setEnabled(False)
                self.page.browse_template_map_pb.setEnabled(False)
            elif self.page.use_existing_map_rb.checked:
                self.page.include_or_copy_template_map_cb.setEnabled(True)
                self.page.template_path_le.setEnabled(True)
                self.page.browse_template_map_pb.setEnabled(True)
        except Exception as e:
            print("NewHierarchicalLayoutDialog.on_radio_buttons_changed caught an exception", e)
            traceback.print_exc()
    
    def on_browse_save_path(self):
        if Debugging.DEBUG:
            debug("NewHierarchicalLayoutDialog.on_browse_save_path")

        try:
            lru_path = FileSystemHelpers.least_recent_directory()
            
            file_path = pya.QFileDialog.getSaveFileName(
                self,               
                "Select Layout File Path",
                lru_path,                 # starting dir ("" = default to last used / home)
                f"Hierarchical Layout (*{FILE_SUFFIX_HIERARCHICAL_LAYOUT})"
            )
        
            if file_path:
                if not file_path.lower().endswith(FILE_SUFFIX_HIERARCHICAL_LAYOUT):
                    file_path += FILE_SUFFIX_HIERARCHICAL_LAYOUT
                self.page.save_path_le.setText(file_path)
                
                FileSystemHelpers.set_least_recent_directory(os.path.dir(file_path))
        except Exception as e:
            print("NewHierarchicalLayoutDialog.on_browse_save_path caught an exception", e)
            traceback.print_exc()

    def on_browse_template_map_path(self):
        if Debugging.DEBUG:
            debug("NewHierarchicalLayoutDialog.on_browse_template_map_path")
            
        try:
            lru_path = FileSystemHelpers.least_recent_directory()
        
            file_path = pya.QFileDialog.getOpenFileName(
                self,
                "Select Library Map Template",
                lru_path,
                f"Library Map (*{FILE_SUFFIX_LIBRARY_MAP})"
            )
        
            if file_path:
                self.page.template_path_le.setText(file_path)
        except Exception as e:
            print("NewHierarchicalLayoutDialog.on_browse_save_path caught an exception", e)
            traceback.print_exc()
            
