from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path
from typing import *

import appium.webdriver.webdriver
from appium.options.common.base import AppiumOptions


class AppiumDriverBase(ABC):
	@abstractmethod
	def get_status(self) -> Dict:
		raise NotImplementedError()

	@abstractmethod
	def quit(self):
		raise NotImplementedError()

	@abstractmethod
	def find_menu(self, title: str) -> appium.webdriver.webelement.WebElement:
		raise NotImplementedError()

	@abstractmethod
	def find_menu_item(self,
					   menu_bar_title: str,
					   path: List[str] | str) -> appium.webdriver.webelement.WebElement:
		raise NotImplementedError()

	@abstractmethod
	def find_dialog(self, title: str) -> appium.webdriver.webelement.WebElement:
		raise NotImplementedError()

	@abstractmethod
	def find_text_field(self,
						ancestor: appium.webdriver.webelement.WebElement,
						text_field_title: str) -> appium.webdriver.webelement.WebElement:
		raise NotImplementedError()

	@abstractmethod
	def find_push_button(self,
						 ancestor: appium.webdriver.webelement.WebElement,
						 button_title: str) -> appium.webdriver.webelement.WebElement:
		raise NotImplementedError()

	@abstractmethod
	def find_radio_button(self,
						  ancestor: appium.webdriver.webelement.WebElement,
						  radio_button_title: str) -> appium.webdriver.webelement.WebElement:
		raise NotImplementedError()

	@abstractmethod
	def find_combo_box(self,
					   ancestor: appium.webdriver.webelement.WebElement,
					   combo_box_title: str) -> appium.webdriver.webelement.WebElement:
		raise NotImplementedError()

	@abstractmethod
	def find_combo_box_item(self,
				            combo_box: appium.webdriver.webelement.WebElement,
					        item_title: str) -> appium.webdriver.webelement.WebElement:
		raise NotImplementedError()


class AppiumDriverFactoryBase(ABC):
	@abstractmethod
	def prepare_options(self, app_path: str | Path) -> AppiumOptions:
		raise NotImplementedError()

	@abstractmethod
	def connect(self, options: AppiumOptions) -> AppiumDriverBase:
		raise NotImplementedError()
