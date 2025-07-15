#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Main orchestrator for crawling vehicle (자동차) listings from the Korean Court Auction system.
It uses modular components for driver interaction, HTML parsing, and data exporting.
"""
import os
# Moved dotenv loading to the top to ensure environment variables are set before other local modules import config
from dotenv import load_dotenv

# --- Load .env file FIRST (now located in the same directory as this script) ---
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path=dotenv_path)
    # print(f"Attempted to load .env from: {dotenv_path}") # For early debug if needed
else:
    # Fallback if .env is somehow not found in the script's directory
    load_dotenv()
    # print(f".env not found at {dotenv_path}. Attempting default .env load.") # For early debug

# Now that .env is loaded, other modules (like car_auction_config) can safely access os.getenv()
from . import car_auction_config as config
import logging # logging can now correctly use config.DEBUG
from selenium.webdriver.support.ui import WebDriverWait
# from .car_driver import CarWebDriver # <- 이 줄을 주석 처리

# Import newly created modules
from . import car_driver
from . import car_parser
from . import car_exporter

# --- Logging Setup ---
logger = logging.getLogger(__name__)
# Configure based on DEBUG from config, which should now be correctly loaded
log_level = logging.DEBUG if config.DEBUG else logging.INFO
logging.basicConfig(level=log_level,
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')

# Log .env load status after logger is configured
if os.path.exists(dotenv_path):
    logger.info(f"Loaded .env file from: {dotenv_path}")
else:
    logger.info(f".env not found at {dotenv_path}. Attempting default .env load (this might not be intended).")


# --- Check for API key (must be done after .env load and config import) ---
# At this point, config.NESTJS_API_KEY should reflect the value from .env
if not config.NESTJS_API_KEY:
    logger.warning("경고: NESTJS_API_KEY가 .env 파일이나 환경변수에 설정되어 있지 않습니다. API 호출이 실패할 수 있습니다.")
else:
    # 추가적인 디버깅을 위해 로드된 키의 일부를 로깅 (실제 키 전체를 로깅하지 않도록 주의)
    logger.info(f"NESTJS_API_KEY loaded, starting with: {config.NESTJS_API_KEY[:5]}...")


def main():
    driver = None
    try:
        driver = car_driver.initialize_driver()
        # Pass config.DEFAULT_WAIT_TIME to WebDriverWait
        wait = WebDriverWait(driver, config.DEFAULT_WAIT_TIME)

        for current_middle_category in config.MIDDLE_CATEGORIES_TO_CRAWL:
            logger.info(f"\n{'='*20} Starting crawl for Middle Category: {current_middle_category} {'='*20}")
            
            if not car_driver.initialize_search(driver, wait, current_middle_category):
                logger.error(f"Failed to initialize search for '{current_middle_category}'. Skipping to next category.")
                continue

            logger.info(f"Initial check for items in '{current_middle_category}'...")
            initial_total_pages_check = car_driver.get_total_pages(driver, wait, 10) # Default 10 for initial check
            if initial_total_pages_check == 0:
                logger.info(f"No auction results found for category '{current_middle_category}'. Skipping category.")
                continue
            logger.info(f"Items found for '{current_middle_category}'. Proceeding.")

            page_size_set_success, actual_items_per_page = car_driver.set_page_size(driver, wait, config.ITEMS_PER_PAGE)
            if not page_size_set_success:
                logger.error(f"Grid lost or page size set failed for '{current_middle_category}'. Actual items/page: {actual_items_per_page}. Skipping category.")
                continue
            
            if not actual_items_per_page or actual_items_per_page == 0:
                logger.warning(f"Actual items_per_page is invalid ({actual_items_per_page}) for {current_middle_category}. Defaulting to 10.")
                actual_items_per_page = 10

            total_pages_to_crawl = car_driver.get_total_pages(driver, wait, actual_items_per_page)
            logger.info(f"For '{current_middle_category}', will crawl {total_pages_to_crawl} pages ({actual_items_per_page} items/page).")

            if total_pages_to_crawl == 0:
                logger.info(f"No results for '{current_middle_category}' after page size set. Skipping.")
                continue

            for page_num in range(1, total_pages_to_crawl + 1):
                logger.info(f"--- Processing Page {page_num} for {current_middle_category} ---")
                if page_num > 1:
                    if not car_driver.go_to_page(driver, wait, page_num):
                        logger.error(f"Failed to navigate to page {page_num} for '{current_middle_category}'. Stopping category.")
                        break 
                
                html_content = car_driver.get_current_page_html(driver, page_num)
                if not html_content:
                    logger.error(f"Failed to get HTML for page {page_num} of '{current_middle_category}'. Skipping page.")
                    continue

                parsed_records = car_parser.parse_list(html_content)
                if not parsed_records:
                    logger.warning(f"No records parsed from page {page_num} of '{current_middle_category}'.")
                
                page_had_api_errors = False
                for record_idx, record in enumerate(parsed_records):
                    logger.debug(f"Sending record {record_idx + 1}/{len(parsed_records)} for page {page_num} (AuctionNo: {record.get('auction_no')})")
                    try:
                        response = car_exporter.insert_auction_result(record)
                        # response 객체가 None인 경우는 auction_no 누락 등으로 exporter 내부에서 예외 발생 전 반환했을 경우 (현재 로직에서는 예외 발생)
                        # 또는 tenacity에서 모든 재시도 실패 후 반환값이 None일 경우 (reraise=True이므로 예외 발생)
                        # 따라서, 정상적인 흐름에서는 response가 requests.Response 객체일 것을 기대.
                        if response is None: # 방어 코드, 실제로는 tenacity 예외로 처리될 가능성 높음
                            logger.error(f"API call for {record.get('auction_no', 'N/A')} returned None. This should not happen if tenacity reraises.")
                            page_had_api_errors = True
                        elif not response.ok: # HTTP 상태 코드가 2xx가 아닌 경우
                            logger.warning(f"API call for {record.get('auction_no', 'N/A')} failed with status {response.status_code}. Response: {response.text}")
                            page_had_api_errors = True
                        # 성공적인 경우 (response.ok is True)는 이미 car_exporter 내부에서 로깅됨

                    except Exception as api_e: # Tenacity에서 모든 재시도 실패 후 발생한 예외 포함
                        logger.error(f"Exception during API call for {record.get('auction_no', 'N/A')}: {api_e}", exc_info=True)
                        page_had_api_errors = True
                
                if page_had_api_errors:
                    logger.warning(f"API errors on page {page_num} of '{current_middle_category}'. Check logs.")
                else:
                    logger.info(f"Successfully processed page {page_num} of '{current_middle_category}'.")
            
            logger.info(f"--- Finished Middle Category: {current_middle_category} ---")

    except Exception as e:
        logger.critical(f"CRITICAL ERROR in main: {e}", exc_info=True)
        if config.DEBUG and driver:
             try:
                  os.makedirs(config.DEBUG_DIR, exist_ok=True)
                  error_screenshot_path = os.path.join(config.DEBUG_DIR, 'main_critical_error_screenshot.png')
                  driver.save_screenshot(error_screenshot_path)
                  logger.info(f"Saved error screenshot to {error_screenshot_path}")
             except Exception as ss_e:
                  logger.error(f"Could not save error screenshot: {ss_e}")
    finally:
        if driver:
            logger.info("Closing browser.")
            driver.quit()
        logger.info("Crawling process execution finished.")

if __name__ == '__main__':
    main()

"""
Change Log (Summary of recent refactoring):
- Refactored into a modular structure:
  - car_auction_config.py: Shared constants and configurations.
  - car_driver.py: Handles Selenium WebDriver interactions.
  - car_parser.py: HTML parsing logic for car auctions.
  - car_exporter.py: Manages data export to NestJS API.
  - court_auction_car_crawler.py: Main orchestrator.
- Logging initialized in main, modules use their own loggers.
- .env loading and API key checks in main.
- Removed direct DB connection from main orchestrator.
"""
