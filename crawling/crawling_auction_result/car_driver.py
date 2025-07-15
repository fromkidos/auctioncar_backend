import os
import time
import re
import datetime
import logging

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
from webdriver_manager.chrome import ChromeDriverManager

from . import car_auction_config as config

logger = logging.getLogger(__name__)

def debug_page_source(driver: webdriver.Chrome, filename: str):
    if not config.DEBUG:
        return
    os.makedirs(config.DEBUG_DIR, exist_ok=True)
    full_path = os.path.join(config.DEBUG_DIR, filename)
    try:
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
        logger.debug(f"Saved debug HTML to {full_path}")
    except Exception as e:
        logger.error(f"Error saving debug HTML to {full_path}: {e}")

def initialize_driver() -> webdriver.Chrome:
    logger.info("Initializing WebDriver...")
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
    logger.info("WebDriver initialized.")
    return driver

def _select_option_and_wait(driver: webdriver.Chrome, wait: WebDriverWait, select_element_id: str, option_text: str, description: str) -> bool:
    try:
        sel_element_present = wait.until(EC.presence_of_element_located((By.ID, select_element_id)))
        sel_element_clickable = wait.until(EC.element_to_be_clickable((By.ID, select_element_id)))
        select_obj = Select(sel_element_clickable)
        
        current_selected_text = select_obj.first_selected_option.text
        if current_selected_text == option_text:
            logger.info(f"{description} '{option_text}' is already selected.")
            return True

        select_obj.select_by_visible_text(option_text)
        logger.info(f"Selected {description}: {option_text}")

        if select_element_id == config.LARGE_CAT_SELECT_ID:
            logger.debug(f"Short pause after selecting large category for middle category options to load...")
            try:
                WebDriverWait(driver, config.SHORT_WAIT_TIME).until(
                    lambda d: len(Select(d.find_element(By.ID, config.MIDDLE_CAT_SELECT_ID)).options) > 1
                )
                logger.debug("Middle category options seem to have loaded.")
            except TimeoutException:
                logger.warning("Middle category options did not show significant change after large cat selection within short wait.")
        return True
    except (NoSuchElementException, TimeoutException) as e:
        logger.error(f"Error selecting {description} '{option_text}' from ID '{select_element_id}': {e}")
        if config.DEBUG: debug_page_source(driver, f"select_error_{description.replace(' ', '_')}.html")
        return False
    except Exception as e_general:
        logger.error(f"Unexpected error during selection of {description} '{option_text}': {e_general}", exc_info=True)
        if config.DEBUG: debug_page_source(driver, f"select_unexpected_error_{description.replace(' ', '_')}.html")
        return False

def initialize_search(driver: webdriver.Chrome, wait: WebDriverWait, middle_category: str) -> bool:
    logger.info(f"Navigating to filter page: {config.URL_FILTER}")
    driver.get(config.URL_FILTER)
    if config.DEBUG:
        debug_page_source(driver, "initial_page_before_wait.html")

    try:
        logger.info(f"Waiting for search form container table (ID: {config.SEARCH_FORM_TABLE_ID})...")
        wait.until(EC.presence_of_element_located((By.ID, config.SEARCH_FORM_TABLE_ID)))
        logger.info(f"Search form container table ({config.SEARCH_FORM_TABLE_ID}) found.")
    except TimeoutException:
        logger.error(f"Timeout waiting for the search form container table ({config.SEARCH_FORM_TABLE_ID}).")
        if config.DEBUG: debug_page_source(driver, "page_filter_form_timeout.html")
        return False

    logger.info("Setting filters...")
    try:
        if not _select_option_and_wait(driver, wait, config.LARGE_CAT_SELECT_ID, config.FILTER_USE_LARGE, "large category"):
            return False
        if not _select_option_and_wait(driver, wait, config.MIDDLE_CAT_SELECT_ID, middle_category, "middle category"):
            return False
        if not _select_option_and_wait(driver, wait, config.COURT_SELECT_ID, "전체", "court"):
            return False

        logger.info(f"Attempting to select sale result: {config.FILTER_SALE_RESULT_SOLD}")
        sale_result_element_present = wait.until(EC.presence_of_element_located((By.ID, config.SALE_RESULT_SELECT_ID)))
        sale_result_select_obj = Select(wait.until(EC.element_to_be_clickable(sale_result_element_present)))
        available_options_sale_result = [opt.text for opt in sale_result_select_obj.options]
        if config.FILTER_SALE_RESULT_SOLD in available_options_sale_result:
            if not _select_option_and_wait(driver, wait, config.SALE_RESULT_SELECT_ID, config.FILTER_SALE_RESULT_SOLD, "sale result"):
                return False 
        else:
            logger.warning(f"Warning: Sale result option '{config.FILTER_SALE_RESULT_SOLD}' not found. Available: {available_options_sale_result}. Proceeding without.")
        
        logger.info(f"{datetime.datetime.now().strftime('%H:%M:%S')} - Waiting for search button (ID: {config.SEARCH_BUTTON_ID}) presence...")
        search_btn_present = wait.until(EC.presence_of_element_located((By.ID, config.SEARCH_BUTTON_ID)))
        logger.info(f"{datetime.datetime.now().strftime('%H:%M:%S')} - Search button present. Waiting for clickability...")
        search_btn = wait.until(EC.element_to_be_clickable(search_btn_present))
        logger.info(f"{datetime.datetime.now().strftime('%H:%M:%S')} - Search button clickable. Attempting click...")
        
        current_grid_body_element = None
        try:
            current_grid_body_element = driver.find_element(By.ID, config.RESULTS_GRID_BODY_ID)
            logger.debug("Found existing results grid body before search click.")
        except NoSuchElementException:
            logger.debug("No existing results grid body (expected on first search).")

        try:
            search_btn.click()
            logger.info(f"{datetime.datetime.now().strftime('%H:%M:%S')} - Standard click executed.")
        except ElementClickInterceptedException:
             logger.warning(f"{datetime.datetime.now().strftime('%H:%M:%S')} - Standard click intercepted. Trying JavaScript click...")
             driver.execute_script("arguments[0].click();", search_btn_present)
             logger.info(f"{datetime.datetime.now().strftime('%H:%M:%S')} - JavaScript click executed.")
        except Exception as e_click:
            logger.error(f"{datetime.datetime.now().strftime('%H:%M:%S')} - Click failed: {e_click}. Trying JS click...")
            try:
                 driver.execute_script("arguments[0].click();", search_btn_present)
                 logger.info(f"{datetime.datetime.now().strftime('%H:%M:%S')} - JavaScript click executed.")
            except Exception as js_e_last:
                logger.error(f"{datetime.datetime.now().strftime('%H:%M:%S')} - JavaScript click also failed: {js_e_last}")
                if config.DEBUG: debug_page_source(driver, "page_search_click_final_fail.html")
                raise

        if current_grid_body_element:
            try:
                logger.debug("Waiting for old results grid to become stale after search click...")
                WebDriverWait(driver, config.SHORT_WAIT_TIME).until(EC.staleness_of(current_grid_body_element))
                logger.info("Old results grid is stale.")
            except TimeoutException:
                logger.warning("Old results grid did not become stale. Page might not have reloaded as expected.")
        
        logger.info(f"{datetime.datetime.now().strftime('%H:%M:%S')} - Search initiated. Waiting for initial results grid.")
        if wait_for_results_grid(driver, wait, 1, is_initial_load=True):
            logger.info(f"{datetime.datetime.now().strftime('%H:%M:%S')} - Initial results grid loaded after search.")
            return True
        else:
            logger.error(f"{datetime.datetime.now().strftime('%H:%M:%S')} - Failed to load initial results grid after search.")
            if config.DEBUG: debug_page_source(driver, "page_search_grid_load_fail.html")
            return False
    except (NoSuchElementException, TimeoutException) as e:
        logger.error(f"Error during filter setup or search: {e}", exc_info=True)
        if config.DEBUG: debug_page_source(driver, "page_filter_error.html")
        return False
    except Exception as e_main_init:
        logger.error(f"Unexpected error in initialize_search: {e_main_init}", exc_info=True)
        if config.DEBUG: debug_page_source(driver, "initialize_search_unexpected_error.html")
        return False

def wait_for_results_grid(driver: webdriver.Chrome, wait: WebDriverWait, page: int, is_initial_load: bool = False) -> bool:
    logger.info(f"--- wait_for_results_grid (Page {page}, InitialLoad: {is_initial_load}) ---")
    logger.debug(f"Current URL: {driver.current_url}, Title: {driver.title}")
    try:
        logger.debug(f"Waiting for presence of results grid container: {config.RESULTS_GRID_SELECTOR}")
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, config.RESULTS_GRID_SELECTOR)))
        logger.debug("Results grid container found.")

        logger.debug(f"Waiting for presence of results grid body: {config.RESULTS_GRID_BODY_ID}")
        grid_body_element = wait.until(EC.presence_of_element_located((By.ID, config.RESULTS_GRID_BODY_ID)))
        logger.debug("Results grid body found.")

        pagination_controls_needed = True 

        if is_initial_load and page == 1:
            logger.debug("Initial load (page 1): Checking total items for pagination expectation.")
            total_items_is_zero = False
            try:
                total_items_span = wait.until(EC.visibility_of_element_located((By.ID, config.TOTAL_ITEMS_SPAN_ID)))
                total_items_text = total_items_span.text
                logger.debug(f"Total items text: '{total_items_text}'")
                match = re.search(r'(\d+)', total_items_text)
                if match and int(match.group(1)) == 0:
                    logger.info("Total items is 0. Pagination controls are not expected.")
                    total_items_is_zero = True
                    pagination_controls_needed = False
                else:
                    logger.debug(f"Total items non-zero or parse failed ('{total_items_text}'). Expecting pagination.")
            except TimeoutException:
                logger.warning(f"Timeout waiting for total items span ({config.TOTAL_ITEMS_SPAN_ID}). Assuming pagination is expected.")
            
            if pagination_controls_needed:
                logger.debug(f"Expecting pagination. Waiting for pagination controls: {config.PAGINATION_DIV_ID}")
                wait.until(EC.presence_of_element_located((By.ID, config.PAGINATION_DIV_ID)))
                logger.debug("Pagination controls PRESENT.")
        
        elif page > 1 : 
            logger.debug(f"Page > 1 or not initial load: Waiting for pagination controls: {config.PAGINATION_DIV_ID}")
            wait.until(EC.presence_of_element_located((By.ID, config.PAGINATION_DIV_ID)))
            logger.debug("Pagination controls PRESENT.")

        logger.debug(f"Waiting for visibility of results grid container: {config.RESULTS_GRID_SELECTOR}")
        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, config.RESULTS_GRID_SELECTOR)))
        logger.debug("Results grid container visible.")

        should_check_for_data_rows = not (is_initial_load and page == 1 and total_items_is_zero)
        
        if should_check_for_data_rows:
            logger.debug(f"Expecting data rows. Waiting for first data row in: {config.RESULTS_GRID_BODY_ID}")
            first_row_xpath = f"//tbody[@id='{config.RESULTS_GRID_BODY_ID}']/tr[@data-tr-id='row2']"
            try:
                wait.until(EC.presence_of_element_located((By.XPATH, first_row_xpath)))
                logger.debug("At least one data row found.")
            except TimeoutException:
                logger.warning(f"Expected data rows but first data row locator ('{first_row_xpath}') timed out.")
        else:
            logger.info("Total items is 0, so not checking for data rows.")

        try:
            grid_body_element_final_check = driver.find_element(By.ID, config.RESULTS_GRID_BODY_ID) 
            rows = grid_body_element_final_check.find_elements(By.XPATH, "./tr[@data-tr-id='row2']")
            logger.debug(f"Number of data rows (tr with data-tr-id='row2') found: {len(rows)}")
        except Exception as e_count_rows:
            logger.warning(f"Could not count data rows for logging: {e_count_rows}")

        logger.info(f"--- Finished wait_for_results_grid (Page {page}, InitialLoad: {is_initial_load}). Returning True. ---")
        return True
    except TimeoutException:
        logger.error(f"Timeout in wait_for_results_grid (Page {page}, InitialLoad: {is_initial_load}).")
        if config.DEBUG: debug_page_source(driver, f'page_{page}_grid_timeout_initial_{is_initial_load}.html')
        return False
    except Exception as e_gen:
        logger.error(f"Exception in wait_for_results_grid (Page {page}, InitialLoad: {is_initial_load}): {e_gen}", exc_info=True)
        if config.DEBUG: debug_page_source(driver, f'page_{page}_grid_exception_initial_{is_initial_load}.html')
        return False

def set_page_size(driver: webdriver.Chrome, wait: WebDriverWait, items_per_page: int) -> tuple[bool, int]:
    actual_items_per_page = 10 # Default
    logger.info(f"Attempting to set page size to {items_per_page}...")
    short_wait = WebDriverWait(driver, config.SHORT_WAIT_TIME)
    try:
        page_size_element_present = wait.until(EC.presence_of_element_located((By.ID, config.PAGE_SIZE_SELECT_ID)))
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", page_size_element_present)
        page_size_clickable = wait.until(EC.element_to_be_clickable(page_size_element_present))

        page_size_select = Select(page_size_clickable)
        available_options = [opt.text for opt in page_size_select.options]
        current_selection_text = page_size_select.first_selected_option.text
        
        current_selection_numeric_match = re.search(r'\d+', current_selection_text)
        if current_selection_numeric_match:
            actual_items_per_page = int(current_selection_numeric_match.group())
        else:
            logger.warning(f"Could not parse numeric from current page size '{current_selection_text}'. Defaulting to 10.")
            actual_items_per_page = 10

        logger.info(f"Page size dropdown: Current '{current_selection_text}' ({actual_items_per_page} items/page). Options: {available_options}")

        desired_option_text_full = next((opt_text for opt_text in available_options if (match := re.search(r'\d+', opt_text)) and int(match.group()) == items_per_page), None)
        
        if desired_option_text_full:
            if current_selection_text != desired_option_text_full:
                logger.info(f"Selecting page size option: '{desired_option_text_full}'")
                old_grid_body_element = None
                try:
                    old_grid_body_element = driver.find_element(By.ID, config.RESULTS_GRID_BODY_ID)
                    logger.debug("Storing old grid body reference before page size change")
                except NoSuchElementException:
                    logger.debug("No old grid body found before page size change (expected if first load).")

                try:
                    page_size_select.select_by_visible_text(desired_option_text_full)
                    logger.info(f"Selenium select_by_visible_text for '{desired_option_text_full}' executed.")
                except Exception as e_select:
                    logger.warning(f"Selenium select failed for '{desired_option_text_full}': {e_select}. JS fallback.")
                    try:
                        option_value = next((opt.get_attribute("value") for opt in page_size_select.options if opt.text == desired_option_text_full), None)
                        if option_value:
                            script = f"arguments[0].value = '{option_value}'; arguments[0].dispatchEvent(new Event('change', {{\'bubbles\': true}}));"
                            logger.debug(f"Executing JS: {script}")
                            driver.execute_script(script, page_size_clickable)
                            logger.info(f"JS fallback for page size to '{option_value}' ('{desired_option_text_full}') triggered.")
                        else:
                            logger.error(f"JS fallback FAILED: No value for '{desired_option_text_full}'.")
                            raise e_select 
                    except Exception as e_js:
                        logger.error(f"JS fallback for page size also FAILED: {e_js}", exc_info=True)
                        raise

                actual_items_per_page = items_per_page
                logger.info(f"Page size selection for {items_per_page} attempted. Waiting for grid to update.")
                
                if old_grid_body_element:
                    try:
                        logger.debug("Waiting for old grid to become stale after page size change...")
                        short_wait.until(EC.staleness_of(old_grid_body_element))
                        logger.info("Old grid body is now stale after page size change.")
                    except TimeoutException:
                        logger.warning("Old grid body did not become stale. Page might not have reloaded correctly.")

                grid_reloaded = wait_for_results_grid(driver, wait, 1, is_initial_load=False)
                if grid_reloaded:
                    logger.info("Results grid reloaded/validated after page size change.")
                else:
                    logger.error("ERROR: Results grid FAILED to reload/validate after page size change.")
                    if config.DEBUG: debug_page_source(driver, "grid_reload_fail_after_page_size_set.html")
                
                logger.info(f"Actual items/page after setting to {items_per_page}: {actual_items_per_page}")
                return grid_reloaded, actual_items_per_page
            else:
                logger.info(f"Page size already '{desired_option_text_full}'. Actual items/page: {actual_items_per_page}")
                return True, actual_items_per_page 
        else:
            logger.warning(f"Desired page size {items_per_page} not found. Using current ({actual_items_per_page}).")
            grid_still_valid = wait_for_results_grid(driver, wait, 1, is_initial_load=False)
            logger.info(f"Actual items/page (requested size not available): {actual_items_per_page}")
            return grid_still_valid, actual_items_per_page
    except (NoSuchElementException, TimeoutException) as e:
        logger.warning(f"Page size dropdown (ID: {config.PAGE_SIZE_SELECT_ID}) error: {e}. Defaulting to {actual_items_per_page}.")
        if config.DEBUG: debug_page_source(driver, "page_size_dropdown_error.html")
        grid_valid_after_error = wait_for_results_grid(driver, wait, 1, is_initial_load=False) 
        return grid_valid_after_error, actual_items_per_page
    except Exception as e_main_set_page:
        logger.error(f"Unexpected error in set_page_size: {e_main_set_page}", exc_info=True)
        if config.DEBUG: debug_page_source(driver, "page_size_unexpected_error.html")
        grid_valid_after_error = wait_for_results_grid(driver, wait, 1, is_initial_load=False)
        return grid_valid_after_error, actual_items_per_page

import math

def get_total_pages(driver: webdriver.Chrome, wait: WebDriverWait, items_per_page: int) -> int:
    total_items = 0
    logger.info("Attempting to determine total number of items...")
    try:
        total_items_element = wait.until(EC.visibility_of_element_located((By.ID, config.TOTAL_ITEMS_SPAN_ID)))
        total_items_text = total_items_element.text
        logger.debug(f"Raw total items text: '{total_items_text}'")
        match = re.search(r'(\d+)', total_items_text)
        if match:
            total_items = int(match.group(1))
            logger.info(f"Successfully parsed total items: {total_items}")
        else:
            logger.warning(f"Could not parse total items from '{total_items_text}'. Defaulting to 0 for calculation, returning 1 page as error.")
            return 1 
    except TimeoutException:
        logger.error(f"Timeout: Total items element '{config.TOTAL_ITEMS_SPAN_ID}' not found/visible.")
        if config.DEBUG: debug_page_source(driver, "total_items_not_found.html")
        return 1 
    except Exception as e:
        logger.error(f"Exception getting total items: {e}", exc_info=True)
        if config.DEBUG: debug_page_source(driver, "total_items_exception.html")
        return 1 

    if total_items == 0:
        logger.info("Total items parsed as 0. Returning 0 pages.")
        return 0
    if items_per_page == 0:
        logger.error("items_per_page is 0 in get_total_pages. Returning 0 pages to prevent error.")
        return 0
    total_pages = math.ceil(total_items / items_per_page)
    logger.info(f"Total pages: {total_pages} (Items: {total_items}, Items/Page: {items_per_page})")
    return int(total_pages)

def go_to_page(driver: webdriver.Chrome, wait: WebDriverWait, page: int) -> bool:
    if page <= 1:
        logger.info("Already on page 1 or invalid page number.")
        return True

    logger.info(f"Navigating to page {page}...")
    short_wait = WebDriverWait(driver, config.SHORT_WAIT_TIME)
    page_link_xpath = f"//div[@id='{config.PAGINATION_DIV_ID}']//a[text()='{page}']"
    try:
        wait.until(EC.presence_of_element_located((By.ID, config.PAGINATION_DIV_ID)))
        page_link_element_present = wait.until(EC.presence_of_element_located((By.XPATH, page_link_xpath)))
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", page_link_element_present)
        time.sleep(0.5) # Allow scroll to settle
        page_link = wait.until(EC.element_to_be_clickable(page_link_element_present))
        
        old_grid_body_element = None
        try:
            old_grid_body_element = driver.find_element(By.ID, config.RESULTS_GRID_BODY_ID)
            logger.debug("Storing old grid body reference before page click")
        except NoSuchElementException:
            logger.debug("No old grid body found before page click (may happen if grid was lost).")

        page_link.click()
        logger.info(f"Clicked page {page} link.")

        if old_grid_body_element:
            try:
                logger.debug(f"Waiting for old grid (elem: {old_grid_body_element.id[:10]}...) to become stale after page {page} click...")
                short_wait.until(EC.staleness_of(old_grid_body_element))
                logger.info(f"Old grid body is now stale after page {page} click.")
            except TimeoutException:
                logger.warning(f"Old grid body did not become stale after page {page} click. Page might not have reloaded as expected.")
            except Exception as e_stale:
                logger.warning(f"Error checking staleness for page {page}: {e_stale}")

        return wait_for_results_grid(driver, wait, page, is_initial_load=False)
    except (TimeoutException, NoSuchElementException) as e:
         logger.error(f"Could not find or click page link for page {page}: {e}")
         if config.DEBUG:
             debug_page_source(driver, f'page_{page}_pagination_fail.html')
         return False
    except Exception as e_main_goto:
        logger.error(f"Unexpected error in go_to_page for page {page}: {e_main_goto}", exc_info=True)
        if config.DEBUG: debug_page_source(driver, f'page_{page}_pagination_unexpected_error.html')
        return False

def get_current_page_html(driver: webdriver.Chrome, page: int) -> str | None:
    logger.info(f"Getting HTML source for page {page}...")
    html = driver.page_source
    if config.DEBUG:
        debug_page_source(driver, f'page_{page}_final_for_parse.html')
    return html 