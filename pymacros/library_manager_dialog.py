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

import os
from pathlib import Path
from typing import *
import traceback

import pya

from klayout_plugin_utils.debugging import debug, Debugging
from klayout_plugin_utils.event_loop import EventLoop
from klayout_plugin_utils.file_selector_widget import FileSelectorWidget
from klayout_plugin_utils.path_helpers import strip_all_suffixes

from constants import (
    LIBRARY_MAP_FILE_FILTER,
    HIERARCHICAL_LAYOUT_FILE_SUFFIXES,
)    

from library_map_config import (
    LibraryMapConfig, 
    LibraryMapStatement,
    LibraryMapComment, 
    LibraryDefinition, 
    LibraryMapInclude,
)

#--------------------------------------------------------------------------------

path_containing_this_script = os.path.realpath(os.path.dirname(__file__))

#--------------------------------------------------------------------------------

class LibraryManagerDialog(pya.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.layout_path: Optional[Path] = None
        self.lib_path: Optional[Path] = None
        self.config: Optional[LibraryMapConfig] = None

        self.init_ui()
        
    def init_ui(self):        
        self.setWindowTitle('Cell Library Manager')

        loader = pya.QUiLoader()
        ui_path = os.path.join(path_containing_this_script, "LibraryManagerDialog.ui")
        ui_file = pya.QFile(ui_path)
        try:
            ui_file.open(pya.QFile.ReadOnly)
            self.page = loader.load(ui_file, self)
        finally:
            ui_file.close()

        self.bottom = pya.QHBoxLayout()
        self.resetButton = pya.QPushButton('Reset')
        self.okButton = pya.QPushButton('OK')
        self.applyButton = pya.QPushButton('Apply')
        self.cancelButton = pya.QPushButton('Cancel')
        
        self.bottom.addWidget(self.resetButton)
        self.bottom.addStretch(1)
        self.bottom.addWidget(self.okButton)
        self.bottom.addWidget(self.applyButton)
        self.bottom.addWidget(self.cancelButton)
        
        self.hline = pya.QFrame()
        self.hline.setFrameShape(pya.QFrame.HLine)
        self.hline.setFrameShadow(pya.QFrame.Sunken)
        
        layout = pya.QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(15)
        layout.addWidget(self.page)
        layout.addWidget(self.hline)
        layout.addLayout(self.bottom)
        
        self.resetButton.clicked.connect(self.on_reset)
        self.okButton.clicked.connect(self.on_ok)
        self.applyButton.clicked.connect(self.on_apply)
        self.cancelButton.clicked.connect(self.on_cancel)
        
        self.okButton.setDefault(True)
        self.okButton.setAutoDefault(True)
        self.cancelButton.setAutoDefault(False)
        
        for pb in (self.page.library_add_pb, self.page.include_add_pb):
            pb.icon = pya.QIcon(':add_16px')
            
        for pb in (self.page.library_remove_pb, self.page.include_remove_pb):
            pb.icon = pya.QIcon(':del_16px')

        for pb in (self.page.library_add_pb, self.page.include_add_pb,
                   self.page.library_remove_pb, self.page.include_remove_pb):
            pb.text = ''
            pb.setFixedSize(40, 32)
        
        self.page.library_add_pb.clicked.connect(self.on_add_library)
        self.page.library_remove_pb.clicked.connect(self.on_remove_library)
        self.page.include_add_pb.clicked.connect(self.on_add_include)
        self.page.include_remove_pb.clicked.connect(self.on_remove_include)
        
        self.page.library_mappings_tw.header.setSectionResizeMode(0, pya.QHeaderView.ResizeToContents)
        self.page.library_mappings_tw.header.setSectionResizeMode(1, pya.QHeaderView.Stretch)
        self.page.library_mappings_tw.header.setSectionResizeMode(2, pya.QHeaderView.Fixed)
        self.page.library_mappings_tw.setColumnWidth(2, 80)
        self.page.library_mappings_tw.header.setStretchLastSection(False)      
          
        self.page.includes_tw.header.setSectionResizeMode(0, pya.QHeaderView.Stretch)
        self.page.includes_tw.setColumnWidth(1, 80)
        self.page.includes_tw.header.setStretchLastSection(False)        
        
        self.page.library_mappings_tw.itemSelectionChanged.connect(self.on_library_selection_changed)
        self.page.includes_tw.itemSelectionChanged.connect(self.on_include_selection_changed)
        
        self.shortcuts = [
            pya.QShortcut(pya.QKeySequence("Delete"), 
                          self.page.library_mappings_tw, self.on_remove_library),
            pya.QShortcut(pya.QKeySequence("Backspace"), 
                          self.page.includes_tw, self.on_remove_include)
        ]
    
    def add_includes_tree_row(self, include_path: str):
        tree: pya.QTreeWidget = self.page.includes_tw
        
        status = ''
        item = pya.QTreeWidgetItem()
        item.setFlags(item.flags | pya.Qt.ItemIsEditable)
        tree.addTopLevelItem(item)
        file_widget = FileSelectorWidget(
            tree,
            file_dialog_title='Select Library Map File',
            file_types=[
                LIBRARY_MAP_FILE_FILTER
            ]
        )
        if include_path:
            file_widget.path = include_path
        
        tree.setItemWidget(item, 0, file_widget)
        item.setText(1, status)
        tree.setCurrentItem(item)

    def add_library_tree_row(self, lib_name: str, lib_path: str):
        tree: pya.QTreeWidget = self.page.library_mappings_tw
        
        status = ''
        item = pya.QTreeWidgetItem()
        item.setFlags(item.flags | pya.Qt.ItemIsEditable)
        tree.addTopLevelItem(item)
        file_widget = FileSelectorWidget(
            tree,
            file_dialog_title='Select Cell Library File',
            file_types=[
               'GDS II Binary file (*.gds *.gds.gz)',
               'GDS II Text file (*.txt)',
               'OASIS file (*.oas)',
               'All Files (*)',
            ]
        )
        if lib_path:
            file_widget.path = lib_path
        item.setText(0, lib_name)
        tree.setItemWidget(item, 1, file_widget)
        item.setText(2, status)
        tree.setCurrentItem(item)
        
        def on_path_changed(file_selector_widget):
            if item.text(0) == '':
                stem = strip_all_suffixes(Path(file_selector_widget.path), HIERARCHICAL_LAYOUT_FILE_SUFFIXES)
                item.setText(0, stem)
        
        file_widget.on_path_changed += [on_path_changed]

    def update_ui_from_config(self, layout_path: Path, lib_path: Path, config: LibraryMapConfig):
        self.layout_path = layout_path
        self.lib_path = lib_path
        self.config = config
    
        self.page.layout_path_le.text = str(layout_path)
        self.page.lib_path_le.text = str(lib_path)
        
        self.page.library_mappings_tw.clear()
        self.page.includes_tw.clear()

        for ld in config.library_definitions:
            self.add_library_tree_row(lib_name=ld.lib_name, lib_path=str(ld.lib_path))
        
        for inc in config.library_map_includes:
            self.add_includes_tree_row(include_path=str(inc.include_path))

        # Nothing is selected yet, disable remove
        self.page.library_remove_pb.setEnabled(False)
        self.page.include_remove_pb.setEnabled(False)
        
    def set_cell_valid(self, item: pya.QTreeWidgetItem, column: int, valid: bool):
        color = pya.QColor(255, 255, 255) if valid \
                else pya.QColor(255, 0, 0, 50)     # light red
        item.setBackgroundColor(column, color)
    
    def validate_ui_inputs(self) -> bool:
        valid = True
        
        problem_items: Tuple[pya.QTreeWidget, pya.QTreeWidgetItem, int] = []
        
        for i in range(0, self.page.library_mappings_tw.topLevelItemCount):
            item = self.page.library_mappings_tw.topLevelItem(i)
            lib_name = item.text(0)
            lib_path = self.page.library_mappings_tw.itemWidget(item, 1).path  # FileSelectorWidget
            self.set_cell_valid(item, 0, bool(lib_name.strip() != ''))
            path = Path(lib_path)
            if path.exists():
                item.setText(2, 'OK')
            else:
                valid = False
                item.setText(2, 'Not found!')  # update status
            self.set_cell_valid(item, 1, path.exists())
            problem_items.append((self.page.library_mappings_tw, item, 1))
            
        for i in range(0, self.page.includes_tw.topLevelItemCount):
            item = self.page.includes_tw.topLevelItem(i)
            include_path = self.page.includes_tw.itemWidget(item, 0).path  # FileSelectorWidget
            path = Path(include_path)
            if path.exists():
                item.setText(1, 'OK')
            else:
                valid = False
                item.setText(1, 'Not found!')  # update status
            self.set_cell_valid(item, 0, path.exists())
            problem_items.append((self.page.includes_tw,item, 0))
        
        # clear selection, otherwise the red indication could be hidden
        self.page.library_mappings_tw.clearSelection()
        self.page.includes_tw.clearSelection()
        
        return valid
    
    def config_from_ui(self) -> LibraryMapConfig:
        statements = []
        
        for i in range(0, self.page.library_mappings_tw.topLevelItemCount):
            item = self.page.library_mappings_tw.topLevelItem(i)
            lib_name = item.text(0)
            lib_path = self.page.library_mappings_tw.itemWidget(item, 1).path  # FileSelectorWidget
            statements.append(LibraryDefinition(lib_name, lib_path))
        
        for i in range(0, self.page.includes_tw.topLevelItemCount):
            item = self.page.includes_tw.topLevelItem(i)
            include_path = self.page.includes_tw.itemWidget(item, 0).path  # FileSelectorWidget
            statements.append(LibraryMapInclude(include_path))
        
        return LibraryMapConfig(technology='',  # TODO
                                statements=statements)
    
    def remove_selected_items(self, tree: pya.QTreeView):
        for item in tree.selectedItems():
            parent = item.parent()
            if parent is None:
                # Item is top-level
                idx = tree.indexOfTopLevelItem(item)
                tree.takeTopLevelItem(idx)
            else:
                # Item has a parent
                idx = parent.indexOfChild(item)
                parent.takeChild(idx)
    
    def on_add_library(self):
        if Debugging.DEBUG:
            debug("LibraryManagerDialog.on_add_library")
        self.add_library_tree_row(lib_name='', lib_path='')
    
    def on_remove_library(self):
        if Debugging.DEBUG:
            debug("LibraryManagerDialog.on_remove_library")
        self.remove_selected_items(self.page.library_mappings_tw)

    def on_add_include(self):
        if Debugging.DEBUG:
            debug("LibraryManagerDialog.on_add_include")
        self.add_includes_tree_row(include_path='')
    
    def on_remove_include(self):
        if Debugging.DEBUG:
            debug("LibraryManagerDialog.on_remove_include")
        self.remove_selected_items(self.page.includes_tw)
    
    def on_library_selection_changed(self):
        if Debugging.DEBUG:
            debug("LibraryManagerDialog.on_library_selection_changed")
        selected = self.page.library_mappings_tw.selectedItems()
        self.page.library_remove_pb.setEnabled(bool(selected))

    def on_include_selection_changed(self):
        if Debugging.DEBUG:
            debug("LibraryManagerDialog.on_include_selection_changed")
        selected = self.page.includes_tw.selectedItems()
        self.page.include_remove_pb.setEnabled(bool(selected))

    def on_reset(self):
        if Debugging.DEBUG:
            debug("LibraryManagerDialog.on_reset")
        
        try:
            self.update_ui_from_config(self.layout_path, self.lib_path, self.config)    
        except Exception as e:
            print("LibraryManagerDialog.on_reset caught an exception", e)
            traceback.print_exc()
        
    def on_ok(self):
        if Debugging.DEBUG:
            debug("LibraryManagerDialog.on_ok")
        
        try:
            if not self.validate_ui_inputs():
                return
            
            self.config = self.config_from_ui()
            self.config.write_json(self.lib_path)
        except Exception as e:
            print("LibraryManagerDialog.on_ok caught an exception", e)
            traceback.print_exc()
        
        self.accept()

    def on_apply(self):
        if Debugging.DEBUG:
            debug("AutoBackupConfigPage.on_apply")

        try:
            if not self.validate_ui_inputs():
                return
                
            self.config = self.config_from_ui()
            self.config.write_json(self.lib_path)
        except Exception as e:
            print("LibraryManagerDialog.on_apply caught an exception", e)
            traceback.print_exc()
        
    def on_cancel(self):
        if Debugging.DEBUG:
            debug("LibraryManagerDialog.on_cancel")
        self.reject()

#--------------------------------------------------------------------------------

