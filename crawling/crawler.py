#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Web crawling logic for interacting with the Court Auction website.
Includes navigation, searching, pagination, detail page access, and dynamic actions.
"""
import os
import time
import math
import re
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException

import config
from parsers import parse_ongoing_list

def initialize_ongoing_search(driver: WebDriver, wait: WebDriverWait) -> bool:
    """Navigates to the ongoing filter page, sets filters, and performs the search."""
    if config.DEBUG: print(f"Navigating to filter page: {config.URL_ONGOING_FILTER}")
    driver.get(config.URL_ONGOING_FILTER)
    if config.DEBUG: print(f"Initial page title: '{driver.title}'")

    if config.DEBUG:
        html_content = driver.page_source
        os.makedirs(config.DEBUG_DIR, exist_ok=True)
        initial_html_path = os.path.join(config.DEBUG_DIR, 'ongoing_initial_page.html')
        try:
            if not os.path.exists(initial_html_path):
                with open(initial_html_path, 'w', encoding='utf-8') as f: f.write(html_content)
                print(f"Saved initial page HTML to {initial_html_path}")
        except Exception as e: 
            print(f"Error saving initial HTML: {e}")
            pass

    try:
        if config.DEBUG: print(f"Waiting for search form table (ID: {config.SEARCH_FORM_TABLE_ID})...")
        wait.until(EC.presence_of_element_located((By.ID, config.SEARCH_FORM_TABLE_ID)))
        if config.DEBUG: print(f"Search form table found.")
    except TimeoutException:
        print(f"Timeout waiting for search form table ({config.SEARCH_FORM_TABLE_ID}).")
        if config.DEBUG:
            debug_file_path = os.path.join(config.DEBUG_DIR, 'ongoing_filter_form_timeout.html')
            try:
                with open(debug_file_path, 'w', encoding='utf-8') as f: f.write(driver.page_source)
                print(f"Saved HTML on form timeout to {debug_file_path}")
            except Exception as e: 
                print(f"Error saving debug HTML: {e}")
                pass
        return False

    if config.DEBUG: print("Setting filters...")
    try:
        current_year = str(time.strftime("%Y"))
        if config.DEBUG: print(f"Setting Case Year: {current_year}")
        year_select_element = wait.until(EC.presence_of_element_located((By.ID, config.CASE_YEAR_SELECT_ID)))
        Select(wait.until(EC.element_to_be_clickable(year_select_element))).select_by_visible_text(current_year)

        if config.DEBUG: print("Setting Court: '전체'...")
        court_select_element = wait.until(EC.presence_of_element_located((By.ID, config.COURT_SELECT_ID)))
        Select(wait.until(EC.element_to_be_clickable(court_select_element))).select_by_visible_text("전체")

        if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - Waiting for search button (ID: {config.SEARCH_BUTTON_ID})...")
        search_btn_element = wait.until(EC.presence_of_element_located((By.ID, config.SEARCH_BUTTON_ID)))
        search_btn = wait.until(EC.element_to_be_clickable(search_btn_element))
        if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - Clicking search button...")
        driver.execute_script("arguments[0].click();", search_btn)
        if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - Search click executed.")
        if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - Title after search: '{driver.title}'")
        return True
    except (NoSuchElementException, TimeoutException) as e:
        print(f"Error during filter selection/search: {e}.")
        if config.DEBUG:
            debug_file_path = os.path.join(config.DEBUG_DIR, 'ongoing_filter_error.html')
            try:
                with open(debug_file_path, 'w', encoding='utf-8') as f: f.write(driver.page_source)
                print(f"Saved HTML on filter error to {debug_file_path}")
            except Exception as save_e: 
                print(f"Error saving debug HTML: {save_e}")
                pass
        return False

def wait_for_results_grid(driver: WebDriver, wait: WebDriverWait, current_page_expected: int | None = 1, is_retry: bool = False) -> bool:
    """Waits for the search results grid (and optionally pagination) to be present and visible.
    Args:
        driver: The Selenium WebDriver instance.
        wait: The WebDriverWait instance.
        current_page_expected: The page number that should be active. If None, page check is skipped.
        is_retry: If True, uses a shorter timeout or less stringent checks, assuming page should already be mostly loaded.
    Returns:
        True if the grid (and pagination if checked) is found, False otherwise.
    """
    effective_wait_timeout = wait._timeout 
    log_page_str = 'any' if current_page_expected is None else str(current_page_expected)
    if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - Entering wait_for_results_grid (Page: {log_page_str}, Retry: {is_retry}, Timeout: {effective_wait_timeout:.1f}s)")

    try:
        if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - Waiting for presence of RESULTS_GRID_SELECTOR: {config.RESULTS_GRID_SELECTOR}")
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, config.RESULTS_GRID_SELECTOR)))
        if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - RESULTS_GRID_SELECTOR found.")

        if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - Waiting for presence of RESULTS_GRID_BODY_ID: {config.RESULTS_GRID_BODY_ID}")
        wait.until(EC.presence_of_element_located((By.ID, config.RESULTS_GRID_BODY_ID)))
        if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - RESULTS_GRID_BODY_ID found.")
        
        if current_page_expected is not None:
            if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - Waiting for presence of PAGINATION_DIV_ID: {config.PAGINATION_DIV_ID}")
            pagination_div = wait.until(EC.presence_of_element_located((By.ID, config.PAGINATION_DIV_ID)))
            if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - PAGINATION_DIV_ID found.")

            active_page_strong_xpath = f"//div[@id='{config.PAGINATION_DIV_ID}']//strong[text()='{current_page_expected}']"
            try:
                if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - Attempting quick check for active page: {active_page_strong_xpath}")
                short_wait = WebDriverWait(driver, 3)
                short_wait.until(EC.visibility_of_element_located((By.XPATH, active_page_strong_xpath)))
                if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - Active page {current_page_expected} confirmed quickly.")
            except TimeoutException:
                if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - Active page {current_page_expected} (strong tag) not visible within 3s. Fallback: checking for first grid row.")
                first_row_xpath = f"#{config.RESULTS_GRID_BODY_ID} > tr"
                if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - Waiting for presence of first row: {first_row_xpath}")
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, first_row_xpath)))
                if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - First grid row found.")
                pass 

        if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - Waiting for visibility of RESULTS_GRID_SELECTOR: {config.RESULTS_GRID_SELECTOR}")
        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, config.RESULTS_GRID_SELECTOR)))
        if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - Results grid (Page: {log_page_str}) is visible. Returning True.")
        return True
    except TimeoutException:
        print(f"{time.strftime('%H:%M:%S')} - TimeoutException in wait_for_results_grid (Page: {log_page_str}, Retry: {is_retry}).")
        if config.DEBUG:
            debug_file_path = os.path.join(config.DEBUG_DIR, f'results_grid_timeout_error_page_{log_page_str}_retry_{is_retry}.html')
            try:
                with open(debug_file_path, 'w', encoding='utf-8') as f: f.write(driver.page_source)
                print(f"Saved grid timeout error page HTML to {debug_file_path}")
            except Exception as html_save_e:
                print(f"Could not save grid timeout error page HTML: {html_save_e}")
        return False
    except Exception as e:
        print(f"{time.strftime('%H:%M:%S')} - Exception in wait_for_results_grid (Page: {log_page_str}, Retry: {is_retry}): {e}")
        if config.DEBUG:
            debug_file_path = os.path.join(config.DEBUG_DIR, f'results_grid_general_error_page_{log_page_str}_retry_{is_retry}.html')
            try:
                with open(debug_file_path, 'w', encoding='utf-8') as f: f.write(driver.page_source)
                print(f"Saved grid general error page HTML to {debug_file_path}")
            except Exception as html_save_e:
                print(f"Could not save grid general error page HTML: {html_save_e}")
        return False

def set_page_size(driver: WebDriver, wait: WebDriverWait, items_per_page: int) -> tuple[bool, int]:
    """Attempts to set the number of items displayed per page. Returns success and actual items per page."""
    actual_items_per_page = 10 # Default
    print(f"Attempting to set page size to {items_per_page}...")
    try:
        page_size_element = wait.until(EC.presence_of_element_located((By.ID, config.PAGE_SIZE_SELECT_ID)))
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", page_size_element)
        time.sleep(0.5)

        page_size_select = Select(wait.until(EC.element_to_be_clickable(page_size_element)))
        available_options = [opt.text for opt in page_size_select.options]
        current_selection_text = page_size_select.first_selected_option.text
        
        current_selection_numeric_match = re.search(r'\d+', current_selection_text)
        if current_selection_numeric_match:
            actual_items_per_page = int(current_selection_numeric_match.group())
        else:
            print(f"Warning: Could not parse numeric part from current page size '{current_selection_text}'. Defaulting to 10.")
            actual_items_per_page = 10

        print(f"Page size dropdown found. Current: '{current_selection_text}' ({actual_items_per_page} items/page). Options: {available_options}")

        desired_option_text_full = None
        for opt_text in available_options:
            opt_numeric_match = re.search(r'\d+', opt_text)
            if opt_numeric_match and int(opt_numeric_match.group()) == items_per_page:
                desired_option_text_full = opt_text
                break
        
        if desired_option_text_full:
            if current_selection_text != desired_option_text_full:
                 print(f"Attempting to select page size option: '{desired_option_text_full}'")
                 selection_done_by_selenium = False
                 try:
                     page_size_select.select_by_visible_text(desired_option_text_full)
                     print(f"Selenium select_by_visible_text for '{desired_option_text_full}' executed.")
                     selection_done_by_selenium = True
                 except Exception as e_select:
                     print(f"Selenium select_by_visible_text failed for '{desired_option_text_full}': {e_select}. Trying JavaScript fallback.")
                     try:
                         option_value_to_set = None
                         for option_element_selenium in page_size_select.options:
                             if option_element_selenium.text == desired_option_text_full:
                                 option_value_to_set = option_element_selenium.get_attribute("value")
                                 break
                         
                         if option_value_to_set is not None:
                             script = f"arguments[0].value = '{option_value_to_set}'; arguments[0].dispatchEvent(new Event('change', {{'bubbles': true}}));"
                             print(f"Executing JS: {script}")
                             driver.execute_script(script, page_size_element)
                             print(f"JavaScript fallback: Set page size to value '{option_value_to_set}' (for text '{desired_option_text_full}') and triggered change event.")
                         else:
                             print(f"JavaScript fallback FAILED: Could not find value attribute for option text '{desired_option_text_full}'.")
                             raise e_select 
                     except Exception as e_js:
                         print(f"JavaScript fallback for page size selection also FAILED: {e_js}")
                         raise e_js

                 actual_items_per_page = items_per_page 
                 print(f"Page size selection attempted for {items_per_page}. Waiting for page to potentially reload (3 seconds)...")
                 time.sleep(3) 
                 
                 print(f"Current URL before grid check: {driver.current_url}")
                 print(f"Current Title before grid check: {driver.title}")
                 print("Checking if results grid reloaded properly after page size change attempt...")
                 
                 grid_reloaded = wait_for_results_grid(driver, wait, 1) 
                 if grid_reloaded:
                     print("Results grid considered reloaded successfully after page size change.")
                 else:
                     print("ERROR: Results grid FAILED to reload or validate after page size change.")
                     debug_page_source(driver, "grid_reload_fail_after_page_size_set.html")
                 
                 print(f"Actual items per page after attempting to set to {items_per_page} (final from function): {actual_items_per_page}")
                 return grid_reloaded, actual_items_per_page
            else:
                 print(f"Page size already set to '{desired_option_text_full}'. Actual items per page: {actual_items_per_page}")
                 return True, actual_items_per_page 
        else:
             print(f"Warning: Desired page size {items_per_page} (option text like '{items_per_page}건씩') not found in {available_options}. Using current ({actual_items_per_page}).")
             grid_still_valid = wait_for_results_grid(driver, wait, 1) 
             print(f"Actual items per page (requested size not available): {actual_items_per_page}")
             return grid_still_valid, actual_items_per_page
    except (NoSuchElementException, TimeoutException) as e:
        print(f"Warning: Could not find/interact with page size dropdown (ID: {config.PAGE_SIZE_SELECT_ID}): {e}. Defaulting actual items/page to {actual_items_per_page}.")
        debug_page_source(driver, "page_size_dropdown_error.html")
        grid_still_valid = wait_for_results_grid(driver, wait, 1)
        print(f"Actual items per page (dropdown error, returning): {actual_items_per_page}")
        return grid_still_valid, actual_items_per_page
    except Exception as e:
        print(f"Warning: Unexpected error in set_page_size: {e}. Defaulting actual items/page to {actual_items_per_page}.")
        debug_page_source(driver, "page_size_unexpected_error.html")
        grid_still_valid = wait_for_results_grid(driver, wait, 1)
        print(f"Actual items per page (unexpected error, returning): {actual_items_per_page}")
        return grid_still_valid, actual_items_per_page

def get_total_pages(driver: WebDriver, wait: WebDriverWait, current_items_per_page: int) -> int:
    """Gets the total number of result pages."""
    if config.DEBUG: print("Attempting to get total pages...")
    total_pages = 1
    try:
        total_items_element = wait.until(EC.visibility_of_element_located((By.ID, config.TOTAL_ITEMS_SPAN_ID)))
        total_items_text = total_items_element.text.strip()
        match = re.search(r'(\d+)', total_items_text)
        if match:
            total_items = int(match.group(1))
            if total_items > 0 and current_items_per_page > 0:
                total_pages = math.ceil(total_items / current_items_per_page)
                if config.DEBUG: print(f"Found {total_items} items. {total_pages} pages ({current_items_per_page} items/page).")
            elif config.DEBUG: print(f"Found '{total_items_text}', but calc error. Defaulting to 1.")
        elif config.DEBUG: print(f"Could not extract number from '{total_items_text}'. Defaulting to 1.")
    except (TimeoutException, NoSuchElementException):
        if config.DEBUG: print(f"Could not find total items ({config.TOTAL_ITEMS_SPAN_ID}). Assuming 1.")
        pass
    except Exception as e: 
        if config.DEBUG: print(f"Error getting total pages: {e}. Assuming 1.")
        pass
    return total_pages

def go_to_page(driver: WebDriver, wait: WebDriverWait, target_page: int) -> bool:
    # target_page가 1 이하인 경우는 update_car_auctions.py의 메인 루프에서
    # go_to_page를 호출하지 않으므로, 이 함수는 target_page > 1인 경우에만 호출됨을 가정합니다.
    if target_page <= 1: 
        if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - go_to_page called with target_page <= 1 ({target_page}). Verifying page 1 grid.")
        if target_page == 1:
            return wait_for_results_grid(driver, wait, current_page_expected=1, is_retry=True)
        return True # target_page <= 0 이면 True 반환 (호출되지 않을 것으로 예상)


    if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - Navigating to page {target_page}...")
    
    target_page_link_xpath = f"//div[@id='{config.PAGINATION_DIV_ID}']//a[normalize-space(text())='{target_page}']"
    next_block_button_li_id = "mf_wfm_mainFrame_pgl_gdsDtlSrchPage_next_btn" 
    next_block_button_xpath = f"//li[@id='{next_block_button_li_id}']/button[@class='w2pageList_col_next']"

    max_attempts = getattr(config, 'MAX_PAGINATION_BLOCK_CLICKS', 60) 

    for attempt_num in range(max_attempts + 1): 
        try:
            if config.DEBUG: print(f"  Attempt {attempt_num + 1}/{max_attempts + 1}: Checking for page {target_page} link.")
            page_link_wait_time = 5 if attempt_num > 0 else config.DEFAULT_WAIT_TIME # 첫 시도에는 기본 대기, 이후에는 짧게
            page_link = WebDriverWait(driver, page_link_wait_time).until(
                EC.element_to_be_clickable((By.XPATH, target_page_link_xpath))
            )
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", page_link)
            driver.execute_script("arguments[0].click();", page_link)
            if config.DEBUG: print(f"  Successfully clicked page {target_page} link.")
            return wait_for_results_grid(driver, wait, current_page_expected=target_page, is_retry=False)
        
        except TimeoutException: 
            if config.DEBUG: print(f"  Page {target_page} link not found or not clickable on attempt {attempt_num + 1}.")
            
            if attempt_num >= max_attempts: 
                print(f"  Exhausted all {max_attempts + 1} attempts to find page {target_page}.")
                if config.DEBUG:
                    debug_path = os.path.join(config.DEBUG_DIR, f'go_to_page_fail_target_{target_page}_final_attempt.html')
                    try:
                        os.makedirs(config.DEBUG_DIR, exist_ok=True)
                        with open(debug_path, 'w', encoding='utf-8') as f: f.write(driver.page_source)
                        print(f"  Saved HTML on final failure to {debug_path}")
                    except Exception as e_save: print(f"  Error saving debug HTML: {e_save}")
                return False

            if config.DEBUG: print(f"  Attempting to click 'Next Page Block' (button click {attempt_num + 1}).")
            try:
                next_button_li_element = driver.find_element(By.ID, next_block_button_li_id)
                if "w2pageList_control_disabled" in next_button_li_element.get_attribute("class").lower():
                    print(f"  'Next Page Block' button is disabled. Cannot proceed further to find page {target_page}.")
                    return False 
                
                next_button = WebDriverWait(driver, config.DEFAULT_WAIT_TIME).until(
                    EC.element_to_be_clickable((By.XPATH, next_block_button_xpath))
                )
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
                driver.execute_script("arguments[0].click();", next_button)
                if config.DEBUG: print(f"  Clicked 'Next Page Block'.")

                if not wait_for_results_grid(driver, wait, current_page_expected=None, is_retry=True):
                    print("  Grid did not reload properly after 'Next Page Block' click.")
                    return False 
                time.sleep(0.5) 

            except (NoSuchElementException, TimeoutException) as e_next:
                print(f"  'Next Page Block' button not found or not clickable: {e_next}")
                if config.DEBUG:
                    current_html_path = os.path.join(config.DEBUG_DIR, f'next_block_button_fail_target_{target_page}_attempt_{attempt_num}.html')
                    try:
                        os.makedirs(config.DEBUG_DIR, exist_ok=True)
                        with open(current_html_path, 'w', encoding='utf-8') as f: f.write(driver.page_source)
                        print(f"  Saved HTML on 'Next Block' button failure to {current_html_path}")
                    except Exception as e_save: print(f"  Error saving debug HTML: {e_save}")
                return False 
            except Exception as e_gen_next: 
                print(f"  Unexpected error clicking 'Next Page Block': {type(e_gen_next).__name__} - {e_gen_next}")
                return False
        
        except Exception as e_outer: 
            print(f"  An unexpected error ({type(e_outer).__name__}) occurred while trying to click page {target_page} link: {e_outer}")
            if attempt_num >= max_attempts:
                if config.DEBUG: print(f"  Error occurred on last attempt for page {target_page}")
                return False
            if config.DEBUG: print(f"  Retrying after short delay due to {type(e_outer).__name__}.")
            time.sleep(1) 
            # continue to the next iteration of the for loop

    print(f"Error: go_to_page function exited loop unexpectedly for target page {target_page}.")
    return False

def get_and_parse_page(driver: WebDriver, page: int) -> list[dict]:
    """Gets current page source and parses it for auction records."""
    if config.DEBUG: print(f"Getting HTML source for page {page}...")
    html = driver.page_source
    if config.DEBUG:
        debug_html_path = os.path.join(config.DEBUG_DIR, f'ongoing_page_{page}_final.html')
        try:
            os.makedirs(config.DEBUG_DIR, exist_ok=True)
            with open(debug_html_path, 'w', encoding='utf-8') as f: f.write(html)
            print(f"Saved final HTML for page {page} to {debug_html_path}")
        except Exception as e: 
            print(f"Error saving debug HTML: {e}")
            pass
    if config.DEBUG: print(f"Parsing HTML for page {page}...")
    return parse_ongoing_list(html)

def click_case_detail_inquiry_button(driver, wait, case_no, item_no):
    """
    물건 상세 페이지에서 '사건상세조회' 버튼을 클릭합니다.
    """
    try:
        # 로딩 오버레이(모달) 사라질 때까지 대기 (최대 5초)
        try:
            WebDriverWait(driver, 5).until(EC.invisibility_of_element_located((By.CSS_SELECTOR, "div.w2modal")))
        except Exception:
            if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - DEBUG: 로딩 오버레이가 여전히 표시 중입니다.")
        # Use configured button ID for case inquiry
        case_detail_button_id = config.DETAIL_PAGE_CASE_DETAIL_INQUIRY_BUTTON_ID
        if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - DEBUG: [click_case_detail_inquiry_button] Locating button ID: {case_detail_button_id}")
        # Try locating by ID, fall back to input[value='사건상세조회'] if not found
        try:
            button = wait.until(EC.element_to_be_clickable((By.ID, case_detail_button_id)))
        except Exception:
            if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - DEBUG: [click_case_detail_inquiry_button] Fallback: locating by XPath input[@value='사건상세조회']")
            button = wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@value='사건상세조회']")))
        if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - DEBUG: [click_case_detail_inquiry_button] Clicking button for {case_no}-{item_no}")
        # JS 클릭으로 오버레이 문제 우회
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
        driver.execute_script("arguments[0].click();", button)
        if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - DEBUG: [click_case_detail_inquiry_button] Clicked. Waiting 0.2 seconds for page transition...")
        time.sleep(0.2)
        
        if config.DEBUG:
            current_url = driver.current_url
            current_title = driver.title
            print(f"{time.strftime('%H:%M:%S')} - DEBUG: [click_case_detail_inquiry_button] After click & sleep - URL: {current_url}, Title: {current_title}")
        return True
    except Exception as e:
        print(f"{time.strftime('%H:%M:%S')} - ERROR: [click_case_detail_inquiry_button] Error clicking button for {case_no}-{item_no}: {e}")
        if config.DEBUG:
            debug_html_path = os.path.join(config.DEBUG_HTML_DIR, f'click_case_inquiry_button_error_{case_no}_{item_no}.html')
            os.makedirs(os.path.dirname(debug_html_path), exist_ok=True)
            try:
                with open(debug_html_path, 'w', encoding='utf-8') as f: f.write(driver.page_source)
                print(f"{time.strftime('%H:%M:%S')} - Saved HTML on click error to {debug_html_path}")
            except Exception as save_e:
                print(f"{time.strftime('%H:%M:%S')} - Error saving debug HTML: {save_e}")
        return False

def wait_for_case_detail_inquiry_page_load(driver, wait, case_no: str):
    """
    '사건상세조회' 페이지 내용(사건기본내역 섹션의 사건번호)이 올바르게 로드될 때까지 기다립니다.
    Args:
        case_no: 기대하는 사건번호 (예: "2024타경101828")
    """
    target_span_id = config.CASE_DETAIL_CASE_NUMBER_SPAN_ID
    if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - DEBUG: [wait_for_case_detail_inquiry_page_load] Waiting for case number '{case_no}' in span ID: {target_span_id}")
    try:
        WebDriverWait(driver, config.DEFAULT_WAIT_TIME).until(
            EC.text_to_be_present_in_element((By.ID, target_span_id), case_no)
        )
        WebDriverWait(driver, 2).until(
            EC.visibility_of_element_located((By.ID, target_span_id))
        )
        if config.DEBUG: 
            print(f"{time.strftime('%H:%M:%S')} - DEBUG: [wait_for_case_detail_inquiry_page_load] Span ID: {target_span_id} with text '{case_no}' is visible.")
            current_url = driver.current_url
            current_title = driver.title
            print(f"{time.strftime('%H:%M:%S')} - DEBUG: [wait_for_case_detail_inquiry_page_load] Current URL after wait: {current_url}")
            print(f"{time.strftime('%H:%M:%S')} - DEBUG: [wait_for_case_detail_inquiry_page_load] Current Title after wait: {current_title}")
        return True
    except TimeoutException:
        print(f"{time.strftime('%H:%M:%S')} - ERROR: Timeout while waiting for '사건상세조회' page for case {case_no} (span ID: {target_span_id} with text '{case_no}').")
        if config.DEBUG:
            sanitized_case_no = case_no.replace('/', '-').replace('\\\\', '-')
            debug_html_path = os.path.join(config.DEBUG_HTML_DIR, f'case_inquiry_timeout_{sanitized_case_no}_{time.strftime("%Y%m%d%H%M%S")}.html')
            os.makedirs(os.path.dirname(debug_html_path), exist_ok=True)
            with open(debug_html_path, 'w', encoding='utf-8') as f:
                f.write(driver.page_source)
            print(f"{time.strftime('%H:%M:%S')} - Saved page source to {debug_html_path}")
        return False
    except Exception as e:
        print(f"{time.strftime('%H:%M:%S')} - ERROR: An unexpected error occurred in wait_for_case_detail_inquiry_page_load for case {case_no}: {e}")
        return False

def navigate_from_case_detail_inquiry_to_list(driver, wait):
    """
    '사건상세조회' 페이지(탭 뷰)에서 '이전' 버튼을 클릭하여 검색 목록 페이지로 돌아갑니다.
    HTML 분석 결과, 적합한 '이전' 버튼 ID는 mf_wfm_mainFrame_btn_prevBtn 로 보입니다.
    """
    try:
        back_button_id_on_case_inquiry_page = "mf_wfm_mainFrame_btn_prevBtn" 
        if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - Locating '이전' button on '사건상세조회' view with ID: {back_button_id_on_case_inquiry_page}")
        back_button = wait.until(EC.element_to_be_clickable((By.ID, back_button_id_on_case_inquiry_page)))
        if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - Clicking '이전' button to return to list from '사건상세조회' view.")
        back_button.click()
        
        if not wait_for_results_grid(driver, wait, current_page_expected=None, is_retry=True):
             print(f"Failed to confirm navigation to results list from case inquiry view.")
             return False
        if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - Successfully navigated back to results list from '사건상세조회' view.")
        return True
    except Exception as e:
        print(f"Error navigating back to list from '사건상세조회' view: {e}")
        if config.DEBUG:
            debug_file_path = os.path.join(config.DEBUG_DIR, 'case_inquiry_navigate_back_fail.html')
            try:
                with open(debug_file_path, 'w', encoding='utf-8') as f: f.write(driver.page_source)
                print(f"Saved HTML on case inquiry navigate back failure to {debug_file_path}")
            except Exception as save_e: 
                print(f"Error saving debug HTML: {save_e}")
                pass
        return False

def load_all_photos(driver: WebDriver, wait: WebDriverWait, case_no: str, item_no: str) -> list[str]:
    if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - Starting photo loading process for {case_no}-{item_no} (collecting ALL photos)...")
    NEXT_PHOTO_BUTTON_SELECTOR = (By.CSS_SELECTOR, config.NEXT_PHOTO_BUTTON_SELECTOR_CSS)
    thumbnail_list_ul_id = "mf_wfm_mainFrame_gen_pic"
    
    # 위치도, 전경도, 관련사진 개수 파싱 로직은 유지 (정보 로깅 목적)
    num_wichido_photos = 0
    num_jeongyeongdo_photos = 0
    num_vehicle_photos = 0
    # photo_count_info_available = False # 이 플래그는 더 이상 수집 로직에 직접적인 영향을 주지 않음

    try:
        pic_info_container = driver.find_element(By.ID, "mf_wfm_mainFrame_gen_picTbox")
        textboxes = pic_info_container.find_elements(By.CLASS_NAME, "w2textbox")
        for textbox in textboxes:
            text_content = textbox.text.strip()
            if "위치도(" in text_content:
                match = re.search(r'위치도\((\d+)\)', text_content)
                if match: num_wichido_photos = int(match.group(1))
            elif "전경도(" in text_content:
                match = re.search(r'전경도\((\d+)\)', text_content)
                if match: num_jeongyeongdo_photos = int(match.group(1))
            elif "관련사진(" in text_content:
                match = re.search(r'관련사진\((\d+)\)', text_content)
                if match: num_vehicle_photos = int(match.group(1))
        
        if config.DEBUG:
            print(f"{time.strftime('%H:%M:%S')} - Photo counts parsed: 위치도({num_wichido_photos}), 전경도({num_jeongyeongdo_photos}), 관련사진({num_vehicle_photos})")
            # photo_count_info_available = True # 로깅용으로만 사용되므로, 활성화 여부는 중요하지 않음

    except NoSuchElementException:
        if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - WARNING: Photo count info container (mf_wfm_mainFrame_gen_picTbox) not found.")
    except Exception as e:
        if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - WARNING: Error parsing photo count info: {e}.")

    MAX_CLICKS = 15 
    click_count = 0
    all_thumbnail_srcs_ordered = [] 
    seen_thumbnail_srcs_for_loop_check = set() 
    consecutive_no_new_photos_count = 0
    MAX_CONSECUTIVE_NO_NEW_PHOTOS = 2 

    if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - DEBUG_PHOTO: Initializing photo collection for {case_no}-{item_no}. All photos will be collected.")

    while click_count < MAX_CLICKS:
        num_unique_photos_before_processing_view = len(seen_thumbnail_srcs_for_loop_check)
        current_view_srcs_this_iteration = []

        try:
            thumbnail_list_element = WebDriverWait(driver, 3).until(
                EC.presence_of_element_located((By.ID, thumbnail_list_ul_id))
            )
            thumbnail_li_elements = thumbnail_list_element.find_elements(By.CSS_SELECTOR, "li")
            if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - DEBUG_PHOTO: Loop {click_count + 1}. Found {len(thumbnail_li_elements)} <li> elements.")

            if not thumbnail_li_elements and click_count > 0:
                if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - No <li> elements found after click. Assuming end.")
                break

            for idx, li_element in enumerate(thumbnail_li_elements):
                try:
                    img_tag = li_element.find_element(By.CSS_SELECTOR, "img[id*='img_reltPic']")
                    img_src = img_tag.get_attribute('src')
                    alt_text = img_tag.get_attribute('alt') 
                    
                    if not img_src:
                        if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - DEBUG_PHOTO:   Skipping <li> {idx+1} (empty img_src, alt: '{alt_text}').")
                        continue
                    
                    current_view_srcs_this_iteration.append(img_src)
                    seen_thumbnail_srcs_for_loop_check.add(img_src)
                    if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - DEBUG_PHOTO:   Collected src from <li> {idx+1} (alt: '{alt_text}'). Unique for loop: {len(seen_thumbnail_srcs_for_loop_check)}")
                except NoSuchElementException:
                    if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - DEBUG_PHOTO:   No img_reltPic in <li> {idx+1}. Skipping.")
                    continue
            
            if current_view_srcs_this_iteration:
                all_thumbnail_srcs_ordered.extend(current_view_srcs_this_iteration)
                if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - DEBUG_PHOTO:   Added {len(current_view_srcs_this_iteration)} srcs to ordered list. Total ordered (may have duplicates): {len(all_thumbnail_srcs_ordered)}")
            
            # 모든 사진을 수집하므로, 특정 개수 도달 시 종료하는 로직은 제거하거나 주석 처리합니다.
            # if photo_count_info_available and total_thumbnails_to_aim_for > 0: 
            #     if len(seen_thumbnail_srcs_for_loop_check) >= total_thumbnails_to_aim_for:
            #         if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - Collected {len(seen_thumbnail_srcs_for_loop_check)} unique thumbnails, meets/exceeds target. Ending.")
            #         break 
            
            num_unique_photos_after_processing_view = len(seen_thumbnail_srcs_for_loop_check)
            if num_unique_photos_after_processing_view == num_unique_photos_before_processing_view and click_count > 0 and thumbnail_li_elements:
                consecutive_no_new_photos_count += 1
                if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - No new unique photos seen. Consecutive count: {consecutive_no_new_photos_count}")
            else:
                consecutive_no_new_photos_count = 0 

            if consecutive_no_new_photos_count >= MAX_CONSECUTIVE_NO_NEW_PHOTOS:
                if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - Reached max consecutive ({MAX_CONSECUTIVE_NO_NEW_PHOTOS}) with no new unique photos. Assuming end.")
                break

        except TimeoutException:
            if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - Timeout finding thumbnail list. Assuming end.")
            break
        except NoSuchElementException:
             if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - Thumbnail list ul#{thumbnail_list_ul_id} not found. Assuming end.")
             break
        except Exception as e:
             if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - Error during thumbnail processing: {type(e).__name__} {e}")
             break
            
        if click_count < MAX_CLICKS -1 :
            try:
                WebDriverWait(driver, 3).until(EC.presence_of_element_located(NEXT_PHOTO_BUTTON_SELECTOR))
                next_button = WebDriverWait(driver, 1).until(EC.element_to_be_clickable(NEXT_PHOTO_BUTTON_SELECTOR))
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
                time.sleep(0.2) 
                driver.execute_script("arguments[0].click();", next_button)
                click_count += 1
                time.sleep(config.PHOTO_LOAD_DELAY) 
            except TimeoutException: 
                if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - Next photo button not found/clickable. Assuming all photos loaded.")
                break
            except ElementClickInterceptedException:
                if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - Next photo button click intercepted. Assuming end.")
                break 
            except Exception as click_err:
                if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - Error clicking next photo: {type(click_err).__name__} {click_err}. Stopping.")
                break
        else: 
            break

    final_unique_ordered_srcs = []
    temp_seen_for_final_list = set()
    for src in all_thumbnail_srcs_ordered:
        if src not in temp_seen_for_final_list:
            final_unique_ordered_srcs.append(src)
            temp_seen_for_final_list.add(src)

    # 모든 사진을 저장하므로, 기존의 num_photos_to_skip_at_start 관련 로직을 제거합니다.
    # vehicle_photo_srcs_final 변수명을 all_collected_photo_srcs 등으로 변경하는 것도 고려할 수 있으나, 일단 유지하고 로직만 수정합니다.
    if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - DEBUG_PHOTO: Collected {len(final_unique_ordered_srcs)} unique photos in order. All will be returned.")
    
    # 이전에는 여기서 vehicle_photo_srcs_final = final_unique_ordered_srcs[num_photos_to_skip_at_start:] 와 같이 필터링을 했으나,
    # 이제 모든 사진을 반환하므로, 필터링 없이 final_unique_ordered_srcs를 사용합니다.
    all_collected_photo_srcs = final_unique_ordered_srcs

    if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - Finished photo loading. Final all collected photo srcs: {len(all_collected_photo_srcs)}")
    return all_collected_photo_srcs

def navigate_back_to_list(driver: WebDriver, wait: WebDriverWait) -> bool:
    """Clicks the 'Previous' button to return to the results list."""
    back_button_id = config.BACK_BUTTON_ID
    print(f"[navigate_back_to_list] 시도: '이전' 버튼 ID: {back_button_id}")
    try:
        print(f"[navigate_back_to_list] 버튼 탐색 대기 중...")
        back_button = wait.until(EC.element_to_be_clickable((By.ID, back_button_id)))
        print(f"[navigate_back_to_list] 버튼 탐색 성공. 스크롤 및 클릭 시도...")
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", back_button)
        driver.execute_script("arguments[0].click();", back_button)
        print(f"[navigate_back_to_list] 버튼 클릭 완료. 목록 그리드 로딩 대기...")
        result = wait_for_results_grid(driver, wait, current_page_expected=None, is_retry=True)
        print(f"[navigate_back_to_list] 목록 그리드 로딩 결과: {result}")
        return result
    except TimeoutException as e:
        print(f"[navigate_back_to_list] ERROR: TimeoutException - 버튼 클릭/탐색 실패: {e}")
        if config.DEBUG:
            debug_file_path = os.path.join(config.DEBUG_DIR, 'navigate_back_fail.html')
            try:
                with open(debug_file_path, 'w', encoding='utf-8') as f: f.write(driver.page_source)
                print(f"[navigate_back_to_list] HTML 저장: {debug_file_path}")
            except Exception as save_e:
                print(f"[navigate_back_to_list] HTML 저장 실패: {save_e}")
        return False
    except NoSuchElementException as e:
        print(f"[navigate_back_to_list] ERROR: NoSuchElementException - 버튼 없음: {e}")
        if config.DEBUG:
            debug_file_path = os.path.join(config.DEBUG_DIR, 'navigate_back_fail.html')
            try:
                with open(debug_file_path, 'w', encoding='utf-8') as f: f.write(driver.page_source)
                print(f"[navigate_back_to_list] HTML 저장: {debug_file_path}")
            except Exception as save_e:
                print(f"[navigate_back_to_list] HTML 저장 실패: {save_e}")
        return False
    except ElementClickInterceptedException as e:
        print(f"[navigate_back_to_list] ERROR: ElementClickInterceptedException - 클릭 가로채임: {e}")
        if config.DEBUG:
            debug_file_path = os.path.join(config.DEBUG_DIR, 'navigate_back_fail.html')
            try:
                with open(debug_file_path, 'w', encoding='utf-8') as f: f.write(driver.page_source)
                print(f"[navigate_back_to_list] HTML 저장: {debug_file_path}")
            except Exception as save_e:
                print(f"[navigate_back_to_list] HTML 저장 실패: {save_e}")
        return False
    except Exception as e:
        print(f"[navigate_back_to_list] ERROR: 기타 예외 발생: {type(e).__name__} - {e}")
        if config.DEBUG:
            debug_file_path = os.path.join(config.DEBUG_DIR, 'navigate_back_fail.html')
            try:
                with open(debug_file_path, 'w', encoding='utf-8') as f: f.write(driver.page_source)
                print(f"[navigate_back_to_list] HTML 저장: {debug_file_path}")
            except Exception as save_e:
                print(f"[navigate_back_to_list] HTML 저장 실패: {save_e}")
        return False 

def click_detail_link(driver: WebDriver, wait: WebDriverWait, case_year: str, case_number: str, item_no: str) -> bool:
    """
    주어진 경매 번호(case_year, case_number, item_no)에 해당하는 행의 '소재지' 링크를 클릭하여 상세 페이지로 이동합니다.
    """
    try:
        case_no_text = f"{case_year}타경{case_number}"
        # XPath 수정: 사건번호와 물건번호를 모두 사용하여 정확한 행을 찾도록 개선
        # 물건번호(item_no)는 일반적으로 세 번째 td 요소에 표시됨 (parsers.py의 parse_ongoing_list 참조)
        # normalize-space()를 사용하여 텍스트 앞뒤 공백을 제거하고 비교합니다.
        row_xpath = (
            f"//tbody[@id='{config.RESULTS_GRID_BODY_ID}']"
            f"/tr[@data-tr-id='row2']"
            f"[.//nobr[contains(., '{case_no_text}')]]"  # 사건번호 포함 확인
            f"[./td[3][normalize-space(.)='{item_no}']]"  # 물건번호(세 번째 td) 일치 확인
        )
        
        if config.DEBUG:
            print(f"{time.strftime('%H:%M:%S')} - DEBUG_XPATH: For {case_no_text}-{item_no}, attempting XPath: {row_xpath}")

        row = wait.until(EC.presence_of_element_located((By.XPATH, row_xpath)))
        
        # '소재지' 링크(<a onclick='moveStPage(...)'>)는 보통 네 번째 td 안에 있음 (parsers.py의 title_text, location_text 파싱 위치 참조)
        # 정확한 링크를 찾기 위해 td의 인덱스를 명시하거나, 더 구체적인 XPath 사용 가능
        # 여기서는 row 내에서 첫 번째로 발견되는 moveStPage 링크를 사용
        detail_link_xpath = ".//td[4]//a[contains(@onclick, 'moveStPage')]" # 네 번째 td 안의 링크로 가정
        detail_link = row.find_element(By.XPATH, detail_link_xpath)
        
        if config.DEBUG:
            print(f"Link found for {case_no_text}-{item_no}. Scrolling and clicking...")

        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", detail_link)
        # 클릭이 가로채일 가능성을 줄이기 위해 JavaScript 클릭 사용 고려
        driver.execute_script("arguments[0].click();", detail_link)
        # detail_link.click() # 원래 클릭 방식

        if config.DEBUG:
            print(f"Click executed for {case_no_text}-{item_no}.")
        
        time.sleep(0.2) # 페이지 전환을 위한 약간의 대기
        return True
    except Exception as e:
        print(f"{time.strftime('%H:%M:%S')} - ERROR: [click_detail_link] {case_year}타경{case_number}-{item_no} 상세 링크 클릭 실패: {e}")
        if config.DEBUG:
            print(f"Failed XPath was: {row_xpath}") # 실패한 XPath 로깅
        return False

def wait_for_detail_page_load(driver: WebDriver, wait: WebDriverWait) -> bool:
    """
    상세 페이지 로드를 기다립니다 (물건종류 표시 요소 확인).
    """
    try:
        # 1. 로딩 오버레이(div.w2modal)가 사라질 때까지 먼저 대기
        try:
            WebDriverWait(driver, 30).until(EC.invisibility_of_element_located((By.CSS_SELECTOR, "div.w2modal")))
        except Exception:
            print(f"[wait_for_detail_page_load] 경고: 로딩 오버레이(w2modal)가 10초 내에 사라지지 않았습니다.")
        # 2. '물건종류' span 등장 대기
        wait.until(EC.presence_of_element_located((By.ID, config.DETAIL_PAGE_LOAD_INDICATOR_ID)))
        return True
    except Exception as e:
        print(f"{time.strftime('%H:%M:%S')} - ERROR: [wait_for_detail_page_load] 상세 페이지 로드 대기 실패: {e}")
        return False 