#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Utility functions for Selenium WebDriver.
"""
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from contextlib import contextmanager

@contextmanager
def initialize_driver() -> webdriver.Chrome:
    """Initializes and returns the Chrome WebDriver, ensuring it's closed afterwards."""
    chrome_options = Options()
    chrome_options.headless = True
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
    
    # webdriver-manager를 사용하여 자동으로 적절한 ChromeDriver 버전을 다운로드하고 관리
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    try:
        yield driver
    finally:
        driver.quit() 