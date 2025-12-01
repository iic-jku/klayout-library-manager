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
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import traceback
from typing import *

import pya

from klayout_plugin_utils.debugging import debug, Debugging
from klayout_plugin_utils.event_loop import EventLoop
from klayout_plugin_utils.file_system_helpers import FileSystemHelpers
from klayout_plugin_utils.str_enum_compat import StrEnum

from constants import (
    HIERARCHICAL_LAYOUT_FILE_SUFFIXES,
    HIERARCHICAL_LAYOUT_FILE_FILTER,
    GENERIC_LAYOUT_FILE_FILTER,
    LIBRARY_MAP_FILE_SUFFIX,
    LIBRARY_MAP_FILE_FILTER,
)
from library_map_changes import LibraryMapChanges
from library_map_config import (
    LibraryMapConfig, 
    LibraryMapStatement, 
    LibraryMapComment, 
    LibraryDefinition, 
    LibraryMapInclude,
    LibraryMapIssues,
)
from library_manager_dialog import LibraryManagerDialog
from new_hierarchical_layout_dialog import NewHierarchicalLayoutDialog, LibraryMapCreationMode

#--------------------------------------------------------------------------------

path_containing_this_script = os.path.realpath(os.path.dirname(__file__))

#--------------------------------------------------------------------------------

@dataclass
class LayoutFileSet:
    layout_path: Path

    @classmethod
    def active(cls) -> Optional[LayoutFileSet]:
        cv = pya.CellView.active()
        if cv.is_valid():
            return LayoutFileSet(Path(cv.filename()))
        return None
    
    @property
    def lib_path(self) -> Path:
        path = self.layout_path.with_suffix(LIBRARY_MAP_FILE_SUFFIX)
        return path

    def load_config(self, msg: str) -> Optional[LibraryMapConfig]:
        try:
            config = LibraryMapConfig.read_json(self.lib_path)
            return config
        except:
            mw = pya.MainWindow.instance()        
            mbx = pya.QMessageBox(mw)
            mbx.icon = pya.QMessageBox_Icon.Critical
            mbx.setTextFormat(pya.Qt.RichText)
            mbx.window_title = 'Error'
            mbx.text = msg
            mbx.informativeText = f"The library map file could not be read:\n"\
                                  f"<pre>{str(self.lib_path)}</pre>"
            mbx.exec_()
            return

#--------------------------------------------------------------------------------

class LibraryMapIssueConsequence(StrEnum):
    NONE = 'none'
    LOAD_NOTHING = "load_nothing"
    LOAD_LOADABLES = "load_loadables"
    EDIT_MAP = "edit_map"
    CLOSE_LAYOUT = "close_layout"

#--------------------------------------------------------------------------------


class LibraryManagerPluginFactory(pya.PluginFactory):
    def __init__(self):
        super().__init__()
                
        self.has_tool_entry = False
        self.register(-1000, "library_manager", "Library Manager")
        
        try:
            self.setup()
        except Exception as e:
            print("LibraryManagerPluginFactory.ctor caught an exception", e)
            traceback.print_exc()
    
    def setup(self):
        self.add_menu_actions()
        
    def add_menu_actions(self):
        mw = pya.MainWindow.instance()
        menu = mw.menu()
        
        action_new_hierarchical_layout = pya.Action()
        action_new_hierarchical_layout.title = 'New Hierarchical Layout…'
        action_new_hierarchical_layout.default_shortcut = 'Ctrl+Shift+N'
        action_new_hierarchical_layout.on_triggered += self.on_new_hierarchical_layout

        action_open_hierarchical_layout = pya.Action()
        action_open_hierarchical_layout.title = 'Open Hierarchical Layout…'
        action_open_hierarchical_layout.default_shortcut = 'Ctrl+Shift+O'
        action_open_hierarchical_layout.on_triggered += self.on_load_hierarchical_layout
        
        action_save_hierarchical_layout = pya.Action()
        action_save_hierarchical_layout.title = 'Save Hierarchical Layout'
        action_save_hierarchical_layout.default_shortcut = 'Ctrl+Shift+S'
        action_save_hierarchical_layout.on_triggered += self.on_save_hierarchical_layout

        action_save_as_hierarchical_layout = pya.Action()
        action_save_as_hierarchical_layout.title = 'Save Hierarchical Layout As…'
        action_save_as_hierarchical_layout.default_shortcut = ''
        action_save_as_hierarchical_layout.on_triggered += self.on_save_as_hierarchical_layout

        action_export_hierarchical_layout_for_tapeout = pya.Action()
        action_export_hierarchical_layout_for_tapeout.title = 'Export Layout For Tapeout…'
        action_export_hierarchical_layout_for_tapeout.default_shortcut = ''
        action_export_hierarchical_layout_for_tapeout.on_triggered += self.on_export_hierarchical_layout_for_tapeout

        action_manage_cell_library_map = pya.Action()
        action_manage_cell_library_map.title = 'Manage Cell Library Map…'
        action_manage_cell_library_map.default_shortcut = 'Ctrl+Shift+M'
        action_manage_cell_library_map.on_triggered += self.on_manage_cell_library_map

        action_reload_cell_libraries = pya.Action()
        action_reload_cell_libraries.title = 'Reload Cell Libraries'
        action_reload_cell_libraries.default_shortcut = ''
        action_reload_cell_libraries.on_triggered += self.on_reload_cell_libraries

        self.actions_by_name: Dict[str, pya.Action] = {
            'new_hierarchical_layout': action_new_hierarchical_layout,
            'open_hierarchical_layout': action_open_hierarchical_layout,
            'save_hierarchical_layout': action_save_hierarchical_layout,
            'save_as_hierarchical_layout': action_save_as_hierarchical_layout,
            'export_hierarchical_layout_for_tapeout': action_export_hierarchical_layout_for_tapeout,
            'manage_cell_library_map': action_manage_cell_library_map,
            'reload_cell_libraries': action_reload_cell_libraries,
        }
        
        # Remove existing commands
        for name, action in self.actions_by_name.items():
            path = f"file_menu.{name}"
            menu.delete_item(path)
        menu.delete_item('file_menu.hierarchical_layout_separator')
        
        # Locate the separator after the 'New …' commands
        file_menu_items = menu.items('file_menu')
        idx = file_menu_items.index('file_menu.open')

        menu.insert_separator(f"file_menu.#{idx}", "hierarchical_layout_separator")

        for i, (name, action) in enumerate(self.actions_by_name.items()):
            menu.insert_item(f"file_menu.#{idx+i}", name, action)
    
    def on_new_hierarchical_layout(self):
        if Debugging.DEBUG:
            debug("LibraryManagerPluginFactory.on_new_hierarchical_layout")

        mw = pya.MainWindow.instance()        
        self.new_hierarchical_layout_dialog = NewHierarchicalLayoutDialog(mw)
        self.new_hierarchical_layout_dialog.exec_()
        
        config = self.new_hierarchical_layout_dialog.get_config()
        if not config:
            return
        
        def validate_library_map_template() -> bool:
            try:
                map_cfg = LibraryMapConfig.read_json(config.library_map_template_path)
                return True
            except:
                mbx = pya.QMessageBox.critical(mw, 'Error', 'New layout creation failed')
                mbx.icon = pya.QMessageBox_Icon.Critical
                mbx.setTextFormat(pya.Qt.RichText)
                mbx.informativeText = f"The template library file could not be read:\n"\
                                      f"<pre>{str(config.library_map_template_path)}</pre>"
                mbx.exec_()
                return False
        
        #
        # prepare library config map sidecar file
        #
        
        map_path = config.save_path.with_suffix(LIBRARY_MAP_FILE_SUFFIX)
        
        map_cfg = LibraryMapConfig(
            technology=config.technology.name,
            statements=[
                LibraryMapComment(f"Automatically generated by 'KLayout Library Manager Plugin ") # TODO: add version   
            ]
        )
        
        match config.library_map_creation_mode:
            case LibraryMapCreationMode.CREATE_EMPTY:
                map_cfg.write_json(map_path)
                    
            case LibraryMapCreationMode.LINK_TEMPLATE:
                if not validate_library_map_template():
                    return
                abbrev_path = LibraryMapConfig.abbreviate_path(path=config.library_map_template_path,
                                                               base_folder=map_path.parent)
                map_cfg.statements.append(LibraryMapInclude(abbrev_path))
                map_cfg.write_json(map_path)
                
            case LibraryMapCreationMode.COPY_TEMPLATE:
                if not validate_library_map_template():
                    return
                map_cfg = LibraryMapConfig.load_as_copy(original_path=config.library_map_template_path, 
                                                        new_path=map_path)
        
        #
        # create new layout
        #
        
        self.reload_cell_libraries(map_path, map_cfg)
        
        cv = mw.create_layout(config.technology.name, 1)  # mode 1 == new view
        layout = cv.layout()
        cv.name = config.top_cell

        cell = layout.create_cell(config.top_cell)
        cv.cell = cell
        
        if config.initial_layers.layers:
            for li in config.initial_layers.layers:
                layout.layer(li)
            cv.view().add_missing_layers()
        
        if config.dbu_um is not None:
            layout.dbu = config.dbu_um
        
        meta_info = pya.LayoutMetaInfo('Hierarchical Layout', True)
        meta_info.persisted = True
        layout.add_meta_info(meta_info)
        
        self.save_hierarchical_layout(layout_path=config.save_path, write_context_info=True)
        cv.view().zoom_box(pya.DBox(0.001, config.initial_window_um or 2.0))

    def save_hierarchical_layout(self, layout_path: Path, write_context_info: bool):
        cv = pya.CellView.active()
        if cv is None:
            return
        
        layout = cv.layout()
        if not self.validate_layout_is_hierarchical(layout, 'Opening Library Manager failed'):
            return
    
        o = pya.SaveLayoutOptions()
        o.oasis_recompress = True
        o.oasis_permissive = True
        o.select_all_cells()
        o.select_all_layers()
        o.set_format_from_filename(str(layout_path))

        # NOTE: 
        #   - for regular "save as…", we want the context info
        #   - for final tapeout export, we don't want the context info
        #       - as some online DRC checker will fail when they see the context info
        o.write_context_info = write_context_info   
        
        lv = cv.view()
        lv.save_as(lv.active_cellview_index, str(layout_path), o)
        
    def save_layout_and_library(self, 
                                layout_path: Path, 
                                lib_path: Path, 
                                config: LayoutMapConfig,
                                write_context_info: bool):
        if Debugging.DEBUG:
            debug("LibraryManagerPluginFactory.save_layout_and_library")
            
        self.save_hierarchical_layout(layout_path, write_context_info)
        config.write_json(lib_path)
        
    def validate_layout_is_hierarchical(self, layout: pya.Layout, topic: str) -> bool:
        if Debugging.DEBUG:
            debug("LibraryManagerPluginFactory.validate_layout_is_hierarchical")

        mw = pya.MainWindow.instance()        
        cv = pya.CellView.active()

        # check if this is a hierarchical layout
        if layout.meta_info_value('Hierarchical Layout') is None:
            mbx = pya.QMessageBox(mw)
            mbx.icon = pya.QMessageBox_Icon.Critical
            mbx.setTextFormat(pya.Qt.RichText)
            mbx.window_title = 'Error'
            mbx.text = topic
            mbx.informativeText = f"The current layout is not hierarchical: "\
                                  f"<pre>{cv.filename()}</pre>"
            mbx.exec_()
            return False
        return True
        
    def report_library_map_issues(self, issues: LibraryMapIssues) -> LibraryMapIssueConsequence:
        if not issues.failed_libraries and not issues.failed_includes:
            return LibraryMapIssueConsequence.NONE
    
        mbox = pya.QMessageBox()
        mbox.setIcon(pya.QMessageBox.Critical)
        mbox.setWindowTitle('Library Map Error')
        mbox.setTextFormat(pya.Qt.RichText)
        mbox.setText(issues.rich_text())
        
        cancel_button = mbox.addButton("Cancel", pya.QMessageBox.RejectRole)
        close_button = mbox.addButton("Close Layout", pya.QMessageBox.DestructiveRole)
        edit_button = mbox.addButton("Edit Map", pya.QMessageBox.ActionRole)
        ignore_button = mbox.addButton("Ignore", pya.QMessageBox.AcceptRole)
        
        result = mbox.exec_()
        match result:
            case 0: return LibraryMapIssueConsequence.LOAD_NOTHING
            case 1: return LibraryMapIssueConsequence.CLOSE_LAYOUT
            case 2: return LibraryMapIssueConsequence.EDIT_MAP
            case 3: return LibraryMapIssueConsequence.LOAD_LOADABLES
    
    def on_load_hierarchical_layout(self):
        if Debugging.DEBUG:
            debug("LibraryManagerPluginFactory.on_load_hierarchical_layout")
        
        mw = pya.MainWindow.instance()        
        
        try:
            lru_path = FileSystemHelpers.least_recent_directory()
        
            layout_path_str = pya.QFileDialog.getOpenFileName(
                mw,
                "Select Hierarchical Layout File",
                lru_path,
                f"{HIERARCHICAL_LAYOUT_FILE_FILTER};;All Files (*)"
            )
        
            if layout_path_str:
                layout_path = Path(layout_path_str)
                lib_path = layout_path.with_suffix(LIBRARY_MAP_FILE_SUFFIX)
                if not lib_path.exists():
                    mbx = pya.QMessageBox(mw)
                    mbx.icon = pya.QMessageBox_Icon.Critical
                    mbx.setTextFormat(pya.Qt.RichText)
                    mbx.window_title = 'Error'
                    mbx.text = 'Opening Hierarchical Layout failed'
                    mbx.informativeText = f"The library map file does not exist:\n"\
                                          f"<pre>{str(lib_path)}</pre>"
                    mbx.exec_()
                    return
                
                try:
                    config = LibraryMapConfig.read_json(lib_path)
                except:
                    mbx = pya.QMessageBox(mw)
                    mbx.icon = pya.QMessageBox_Icon.Critical
                    mbx.setTextFormat(pya.Qt.RichText)
                    mbx.window_title = 'Error'
                    mbx.text = 'Opening Hierarchical Layout failed'
                    mbx.informativeText = f"The library map file could not be read:\n"\
                                          f"<pre>{str(lib_path)}</pre>"
                    mbx.exec_()
                    return
                
                mw = pya.MainWindow.instance()
                
                # NOTE: reloading the cell libraries will set the layout dirty, 
                #       therefore we start with an empty view, load the libs there,
                #       then open the layout
                mw.create_view()

                self.reload_cell_libraries(lib_path, config)
                mw.load_layout(str(layout_path), 0)
                
        except Exception as e:
            print("NewHierarchicalLayoutDialog.on_browse_save_path caught an exception", e)
            traceback.print_exc()
        
    def report_no_active_cell_view(self, msg: str):
        mw = pya.MainWindow.instance()
        pya.QMessageBox.critical(mw, 'Save Failed', msg)
        
    def on_save_hierarchical_layout(self):
        if Debugging.DEBUG:
            debug("LibraryManagerPluginFactory.on_save_hierarchical_layout")
            
        try:
            layout_file_set = LayoutFileSet.active()
            if layout_file_set is None:
                self.report_no_active_cell_view('No view open to save')
                return
    
            map_cfg = layout_file_set.load_config('Save Hierarchical Layout failed')
            if map_cfg is None:
                return
            
            self.save_layout_and_library(layout_path=layout_file_set.layout_path,
                                         lib_path=layout_file_set.lib_path, 
                                         config=map_cfg,
                                         write_context_info=True)
        except Exception as e:
            print("LibraryManagerPluginFactory.on_save_hierarchical_layout caught an exception", e)
            traceback.print_exc()

    def on_save_as_hierarchical_layout(self):
        if Debugging.DEBUG:
            debug("LibraryManagerPluginFactory.on_save_as_hierarchical_layout")
            
        try:
            layout_file_set = LayoutFileSet.active()
            if layout_file_set is None:
                self.report_no_active_cell_view('No view open to save')
                return
                
            cv = pya.CellView.active()
            layout = cv.layout()
            if not self.validate_layout_is_hierarchical(layout, 'Save Hierarchical Layout failed'):
                return
            
            map_cfg = layout_file_set.load_config('Save Hierarchical Layout failed')
            if map_cfg is None:
                return
            
            lru_path = FileSystemHelpers.least_recent_directory()
            
            mw = pya.MainWindow.instance()
            
            layout_path_str = pya.QFileDialog.getSaveFileName(
                mw,               
                "Select Layout File Path",
                lru_path,                 # starting dir ("" = default to last used / home)
                f"{HIERARCHICAL_LAYOUT_FILE_FILTER};;All Files (*)"
            )
        
            if layout_path_str:
                layout_path = Path(layout_path_str)
                if ''.join(layout_path.suffixes).lower() not in HIERARCHICAL_LAYOUT_FILE_SUFFIXES:
                    layout_path = layout_path.with_suffix(HIERARCHICAL_LAYOUT_FILE_SUFFIXES[0])
                
                FileSystemHelpers.set_least_recent_directory(layout_path.parent)

                lib_path = layout_path.with_suffix(LIBRARY_MAP_FILE_SUFFIX)
                self.save_layout_and_library(layout_path=layout_path,
                                             lib_path=lib_path, 
                                             config=map_cfg,
                                             write_context_info=True)
        except Exception as e:
            print("LibraryManagerPluginFactory.on_save_as_hierarchical_layout caught an exception", e)
            traceback.print_exc()
    
    def on_export_hierarchical_layout_for_tapeout(self):
        if Debugging.DEBUG:
            debug("LibraryManagerPluginFactory.on_export_hierarchical_layout_for_tapeout")
            
        succeeded = False
        layout_path = None
        caught_exception = None
            
        try:
            layout_file_set = LayoutFileSet.active()
            if layout_file_set is None:
                self.report_no_active_cell_view('No view open to save')
                return
                
            cv = pya.CellView.active()
            layout = cv.layout()
            if not self.validate_layout_is_hierarchical(layout, 'Export Hierarchical Layout failed'):
                return
            
            map_cfg = layout_file_set.load_config('Export Hierarchical Layout failed')
            if map_cfg is None:
                return
            
            lru_path = FileSystemHelpers.least_recent_directory()
            
            mw = pya.MainWindow.instance()
            
            layout_path_str = pya.QFileDialog.getSaveFileName(
                mw,               
                "Select Layout File Path",
                lru_path,                 # starting dir ("" = default to last used / home)
                f"{GENERIC_LAYOUT_FILE_FILTER};;All Files (*)"
            )
            
            if not layout_path_str:
                return  # User clicked cancel
                
            layout_path = Path(layout_path_str)
            
            FileSystemHelpers.set_least_recent_directory(layout_path.parent)
        
            o = pya.SaveLayoutOptions()
            o.oasis_recompress = True
            o.oasis_permissive = True
            o.select_all_cells()
            o.select_all_layers()
            o.set_format_from_filename(str(layout_path))
    
            # NOTE: 
            #   - for regular "save as…", we want the context info
            #   - for final tapeout export, we don't want the context info
            #       - as some online DRC checker will fail when they see the context info
            o.write_context_info = False
            
            layout.write(str(layout_path), o)
            
            succeeded = True
            # raise Exception(f"Test exception")
        except Exception as e:
            print("LibraryManagerPluginFactory.on_export_hierarchical_layout_for_tapeout caught an exception", e)
            traceback.print_exc()
            caught_exception = e            
        finally:
            if not succeeded and caught_exception is None:  # cancellation
                return
            
            mbox = pya.QMessageBox()
            mbox.setTextFormat(pya.Qt.RichText)
            if succeeded:
                mbox.setIcon(pya.QMessageBox.Information)
                mbox.setWindowTitle('Export For Tapeout Success')
                mbox.text = "Export for tapeout succeeded."
                mbox.informativeText = f"The current layout was successfully exported for tapeout to: "\
                                       f"<pre>{str(layout_path)}</pre>"
                reveal_button = mbox.addButton("Reveal in File Manager", pya.QMessageBox.ActionRole)
                ok_button = mbox.addButton("OK", pya.QMessageBox.AcceptRole)
                    
                result = mbox.exec_()
                if result == 0:
                    FileSystemHelpers.reveal_in_file_manager(layout_path)
            else:
                mbox.setIcon(pya.QMessageBox.Critical)
                mbox.setWindowTitle('Export For Tapeout Error')
                mbox.text = "Export for tapeout failed."
                mbox.informativeText = f"Caught Exception: "\
                                       f"<pre>{str(caught_exception)}</pre>"                
                ok_button = mbox.addButton("OK", pya.QMessageBox.AcceptRole)                
                result = mbox.exec_()
            
    
    def on_manage_cell_library_map(self):
        if Debugging.DEBUG:
            debug("LibraryManagerPluginFactory.on_manage_cell_library_map")
        
        try:
            layout_file_set = LayoutFileSet.active()
            if layout_file_set is None:
                self.report_no_active_cell_view('No view open to manage')
                return
                
            cv = pya.CellView.active()
            layout = cv.layout()
            
            if not self.validate_layout_is_hierarchical(layout, 'Opening Library Manager failed'):
                return
            
            old_map_cfg = layout_file_set.load_config('Manage cell library map failed')
            if old_map_cfg is None:
                return
            
            mw = pya.MainWindow.instance()
            self.library_manager_dialog = LibraryManagerDialog(mw)
            self.library_manager_dialog.update_ui_from_config(layout_file_set.layout_path, layout_file_set.lib_path, old_map_cfg)
            result = self.library_manager_dialog.exec_()
            if result != 0:
                new_map_cfg = layout_file_set.load_config('Manage cell library map failed')
                if new_map_cfg is None:
                    return
                
                base_folder = layout_file_set.layout_path.parent
                        
                changes = LibraryMapChanges.compare(base_folder, old_map_cfg, new_map_cfg)
                
                if Debugging.DEBUG:
                    debug(f"LibraryManagerPluginFactory.on_manage_cell_library_map\n"
                          f"\tadded: {changes.added_libs}\n"
                          f"\tremoved: {changes.removed_libs}\n"
                          f"\trenamed: {changes.renamed_libs}\n"
                          f"\trepathed: {changes.repathed_libs}\n")
                
                self.apply_library_map_changes(changes)
        except Exception as e:
            print("LibraryManagerPluginFactory.on_manage_cell_library_map caught an exception", e)
            traceback.print_exc()
    
    def apply_library_map_changes(self, changes: LibraryMapChanges):
        if Debugging.DEBUG:
            debug("LibraryManagerPluginFactory.on_reload_cell_libraries")

        mw = pya.MainWindow.instance()
        
        def report_issues(issues: LibraryMapIssues) -> bool:
            consequence = self.report_library_map_issues(issues)
            match consequence:
                case LibraryMapIssueConsequence.LOAD_NOTHING:
                    return False
                case LibraryMapIssueConsequence.EDIT_MAP:
                    EventLoop.defer(self.on_manage_cell_library_map)
                    return False
                case LibraryMapIssueConsequence.CLOSE_LAYOUT:
                    mw = pya.MainWindow.instance()
                    EventLoop.defer(mw.close_current_view)
                    return False
                case LibraryMapIssueConsequence.NONE |\
                     LibraryMapIssueConsequence.LOAD_LOADABLES:
                    return True

        if not report_issues(changes.issues):
            return
        
        loading_issues = LibraryMapIssues()
        
        for new_lib_def in changes.added_libs:
            try:
                lib = pya.Library()
                lib.layout().read(new_lib_def.lib_path)
                lib.register(new_lib_def.lib_name)
            except Exception as e:
                loading_issues.failed_libraries.append((new_lib_def, issue))
        
        if not report_issues(loading_issues):
            return        
        
        for old_lib_def, new_lib_def in changes.renamed_libs:
            lib = pya.Library.library_by_name(old_lib_def.lib_name)
            if 'rename' in dir(lib):  # added in KLayout 0.30.5 API
                lib.rename(new_lib_def.lib_name)
            
        for old_lib_def, new_lib_def in changes.repathed_libs:
            lib = pya.Library.library_by_name(new_lib_def.lib_name)
            # NOTE: due to loading errors, it could be that the library does not yet exist
            if lib is None:
                lib = pya.Library()
                lib.layout().read(new_lib_def.lib_path)
                lib.register(new_lib_def.lib_name)
            else:
                lib.layout().clear()
                lib.layout().read(new_lib_def.lib_path)
                lib.refresh()
        
        for old_lib_def in changes.removed_libs:
            lib = pya.Library.library_by_name(old_lib_def.lib_name)
            if lib:  # NOTE: due to loading errors, it could be that the library does not yet exist
                if 'unregister' in dir(pya.Library):  # added in KLayout 0.30.5 API
                    pya.Library.unregister(lib)
    
    def on_reload_cell_libraries(self):
        if Debugging.DEBUG:
            debug("LibraryManagerPluginFactory.on_reload_cell_libraries")
        
        try:        
            mw = pya.MainWindow.instance()
            cv = pya.CellView.active()
            
            layout_file_set = LayoutFileSet.active()
            if layout_file_set is None:
                self.report_no_active_cell_view('No view open to reload')
                return

            map_cfg = layout_file_set.load_config('Reload cell libraries failed')
            if map_cfg is None:
                return

            self.reload_cell_libraries(layout_file_set.lib_path, map_cfg)
            
        except Exception as e:
            print("LibraryManagerPluginFactory.on_reload_cell_libraries caught an exception", e)
            traceback.print_exc()

    def reload_cell_libraries(self, lib_path: Path, config: LibraryMapConfig):
        if Debugging.DEBUG:
            debug("LibraryManagerPluginFactory.reload_cell_libraries")
        
        parent_dir = lib_path.parent
        issues = LibraryMapIssues()
        new_lib_defs = config.effective_library_definitions(base_folder=parent_dir, issues=issues)
        
        loading_issues = LibraryMapIssues()
        
        def handle_issues(issues: LibraryMapIssues):
            consequence = self.report_library_map_issues(issues)
            match consequence:
                case LibraryMapIssueConsequence.LOAD_NOTHING:
                    return
                case LibraryMapIssueConsequence.EDIT_MAP:
                    EventLoop.defer(self.on_manage_cell_library_map)
                case LibraryMapIssueConsequence.NONE |\
                     LibraryMapIssueConsequence.LOAD_LOADABLES:
                    for lib_def in new_lib_defs:
                        if Debugging.DEBUG:
                            debug(f"Reload library {lib_def.lib_name} from path {lib_def.lib_path}")
                        lib = pya.Library.library_by_name(lib_def.lib_name)
                        if lib is None:
                            lib = pya.Library()
                            try:
                                lib.layout().read(lib_def.lib_path)
                                lib.register(lib_def.lib_name)
                            except Exception as e:
                                loading_issues.failed_libraries.append((lib_def, str(e)))
                        else:              
                            try:
                                lib.layout().clear()
                                lib.layout().read(lib_def.lib_path)
                                lib.refresh()
                            except Exception as e:
                                loading_issues.failed_libraries.append((lib_def, str(e)))
                case LibraryMapIssueConsequence.CLOSE_LAYOUT:
                    mw = pya.MainWindow.instance()
                    EventLoop.defer(mw.close_current_view)
                    
        handle_issues(issues)
        handle_issues(loading_issues)
