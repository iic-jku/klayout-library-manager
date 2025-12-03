from abc import ABC, abstractmethod
from pathlib import Path
from typing import *

import appium.webdriver.webdriver
from appium.webdriver.common.appiumby import AppiumBy
from appium.options.common.base import AppiumOptions

from tests.appium_driver import AppiumDriverBase, AppiumDriverFactoryBase


class AppiumDriverMacOS(AppiumDriverBase):
	def __init__(self, driver: appium.webdriver.webdriver.WebDriver):
		self.driver = driver

	def get_status(self) -> Dict:
		return self.driver.get_status()

	def quit(self):
		return self.driver.quit()

	def find_menu(self, title: str) -> appium.webdriver.webelement.WebElement:
		xpath = f"**/XCUIElementTypeMenuBar/XCUIElementTypeMenuBarItem[`title == \"{title}\"`]"
		e = self.driver.find_element(by=AppiumBy.IOS_CLASS_CHAIN, value=xpath)
		return e

	def find_menu_item(self,
					   menu_bar_title: str,
					   path: List[str] | str) -> appium.webdriver.webelement.WebElement:
		if isinstance(path, str):
			path = [path]
		xpath = f"**/XCUIElementTypeMenuBar/XCUIElementTypeMenuBarItem[`title == \"{menu_bar_title}\"`]"
		for pi in path:
			xpath += f"/XCUIElementTypeMenu/XCUIElementTypeMenuItem[`title == \"{pi}\"`]"
		e = self.driver.find_element(by=AppiumBy.IOS_CLASS_CHAIN, value=xpath)
		return e

	def find_dialog(self, title: str) -> appium.webdriver.webelement.WebElement:
		xpath = f"**/XCUIElementTypeDialog[`title == \"{title}\"`]"
		e = self.driver.find_element(by=AppiumBy.IOS_CLASS_CHAIN, value=xpath)
		return e

	def find_text_field(self,
						ancestor: appium.webdriver.webelement.WebElement,
						text_field_title: str) -> appium.webdriver.webelement.WebElement:
		xpath = f"**/XCUIElementTypeTextField[`title == \"{text_field_title}\"`]"
		e = ancestor.find_element(by=AppiumBy.IOS_CLASS_CHAIN, value=xpath)
		return e

	def find_push_button(self,
						 ancestor: appium.webdriver.webelement.WebElement,
						 button_title: str) -> appium.webdriver.webelement.WebElement:
		xpath = f"**/XCUIElementTypeButton[`title == \"{button_title}\"`]"
		e = ancestor.find_element(by=AppiumBy.IOS_CLASS_CHAIN, value=xpath)
		return e

	def find_radio_button(self,
						  ancestor: appium.webdriver.webelement.WebElement,
						  radio_button_title: str) -> appium.webdriver.webelement.WebElement:
		xpath = f"**/XCUIElementTypeRadioButton[`title == \"{radio_button_title}\"`]"
		e = ancestor.find_element(by=AppiumBy.IOS_CLASS_CHAIN, value=xpath)
		return e

	def find_combo_box(self,
				       ancestor: appium.webdriver.webelement.WebElement,
					   combo_box_title: str) -> appium.webdriver.webelement.WebElement:
		xpath = f"**/XCUIElementTypeComboBox[`title == \"{combo_box_title}\"`]"
		e = ancestor.find_element(by=AppiumBy.IOS_CLASS_CHAIN, value=xpath)
		return e

	def find_combo_box_item(self,
				            combo_box: appium.webdriver.webelement.WebElement,
					        item_title: str) -> appium.webdriver.webelement.WebElement:
		xpath = f"**/XCUIElementTypeOther/"\
		        f"XCUIElementTypeStaticText[`title == \"{item_title}\"`]"
		e = combo_box.find_element(by=AppiumBy.IOS_CLASS_CHAIN, value=xpath)
		return e


class AppiumDriverFactoryMacOS(AppiumDriverFactoryBase):
	def prepare_options(self, app_path: str | Path) -> AppiumOptions:
		app_path = Path(app_path)
		options = AppiumOptions()
		options.load_capabilities({
			"platformName": "mac",
			"appium:automationName": "mac2",
			"appium:appPath": str(app_path),
			"appium:environment": {
				"DYLD_LIBRARY_PATH": str(app_path.parent)
			},
			"appium:newCommandTimeout": 3600,
			"appium:connectHardwareKeyboard": True,
			"appium:noReset": True
		})
		return options

	def connect(self, options: AppiumOptions) -> AppiumDriverBase:
		driver = appium.webdriver.Remote("http://127.0.0.1:4723", options=options)
		return AppiumDriverMacOS(driver)
