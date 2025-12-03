#! /usr/bin/env python3

# This sample code supports Appium Python client >=2.3.0
# pip install Appium-Python-Client
# Then you can paste this into a file and simply run with Python

from typing import *
import os
import sys

import appium.webdriver.webdriver
from appium import webdriver
from appium.options.common.base import AppiumOptions
from appium.webdriver.common.appiumby import AppiumBy

# For W3C actions
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.actions import interaction
from selenium.webdriver.common.actions.action_builder import ActionBuilder
from selenium.webdriver.common.actions.pointer_input import PointerInput
from setuptools.sandbox import save_path

from tests.appium_driver_macOS import AppiumDriverFactoryMacOS

#------------------
dir_containing_this_script = os.path.dirname(__file__)
source_paths = [
	os.path.realpath(os.path.join(dir_containing_this_script, '..', 'pymacros')),
	os.path.realpath(os.path.join(dir_containing_this_script, '..', '..', 'klayout-plugin-utils', 'python')),
]
for path in source_paths:
	if os.path.exists(path):
		sys.path.append(path)
#------------------

from new_hierarchical_layout_config import NewHierarchicalLayoutConfig, LibraryMapCreationMode
from klayout_plugin_utils.layer_list_string import LayerList

#--------------------------------------------------------------------------------

driver_factory = AppiumDriverFactoryMacOS()
options = driver_factory.prepare_options(
	app_path="/Users/martin/Source/klayout/qt5MP.build.macos-Sequoia-release-Rhb34Phbauto.macQAT/klayout.app"
)
driver = driver_factory.connect(options)

def create_new_hierarchical_layout(config: NewHierarchicalLayoutConfig):
	menu_item = driver.find_menu_item( 'File', 'New Hierarchical Layout…')
	menu_item.click()

	dialog_title = 'New Hierarchical Layout'
	dialog = driver.find_dialog(dialog_title)

	layout_path_text_field = driver.find_text_field(dialog, 'File name')
	layout_path_text_field.clear()
	layout_path_text_field.send_keys(config.save_path)

	match config.library_map_creation_mode:
		case LibraryMapCreationMode.CREATE_EMPTY:
			rb = driver.find_radio_button(dialog, 'Create empty library map file')
			rb.click()

		case LibraryMapCreationMode.LINK_TEMPLATE | LibraryMapCreationMode.COPY_TEMPLATE:
			rb = driver.find_radio_button(dialog, 'Use existing library map file,')
			rb.click()

			template_text_field = driver.find_text_field(dialog, 'Library Map')
			template_text_field.clear()
			template_text_field.send_keys(config.library_map_template_path)

	match config.library_map_creation_mode:
		case LibraryMapCreationMode.CREATE_EMPTY | LibraryMapCreationMode.LINK_TEMPLATE:
			pass

		case LibraryMapCreationMode.COPY_TEMPLATE:
			rb = driver.find_combo_box(dialog, 'include')
			rb.click()
			rbi = driver.find_combo_box_item(rb, 'copy')
			rbi.click()

	ok = driver.find_push_button(dialog, 'OK')
	ok.click()



status = driver.get_status()
print(status)

save_path = os.path.expandvars("$HOME/tmp/foobar.klay.gds")
lib_map_path = os.path.expandvars("$HOME/tmp/common.klib")

create_new_hierarchical_layout(
	NewHierarchicalLayoutConfig(
		save_path=save_path,
		library_map_creation_mode=LibraryMapCreationMode.COPY_TEMPLATE, #CREATE_EMPTY,
		library_map_template_path=lib_map_path, #None,
		tech_name=None,
		top_cell='TOP',
		dbu_um=None,
		initial_window_um=2.0,
		initial_layers=LayerList()
	)
)


driver.quit()

