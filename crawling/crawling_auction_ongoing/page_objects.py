from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException, ElementClickInterceptedException
import logging
import os
import requests
from urllib.parse import urljoin
import time
from selenium.webdriver.support.select import Select
import re
import math
import base64
from typing import Optional

from . import config # 상대 경로로 config 임포트
from .parsers import parse_detail_page, parse_ongoing_list
from .utils import retry # retry 데코레이터 임포트

logger = logging.getLogger(__name__)

class BasePage:
    def __init__(self, driver, wait):
        self.driver = driver
        self.wait = wait
        self.logger = logging.getLogger(self.__class__.__module__ + '.' + self.__class__.__name__)
        # WebDriverWaitのタイムアウトを保持（page_objectsから参照されるdefault_timeout用）
        # config.DEFAULT_WAIT_TIME を import している前提です
        from . import config
        self.default_timeout = config.DEFAULT_WAIT_TIME

class AuctionListPage(BasePage):
    def __init__(self, driver, wait):
        super().__init__(driver, wait)
        # Locators specific to AuctionListPage can be defined here or imported from config
        self.search_form_id = config.SEARCH_FORM_TABLE_ID
        self.search_court_input_id = config.COURT_SELECT_ID
        # self.search_car_type_id = config.CAR_TYPE_RADIO_ID # 주석 처리
        self.search_button_id = config.SEARCH_BUTTON_ID
        self.results_grid_selector = config.RESULTS_GRID_SELECTOR
        self.page_size_selector_id = config.PAGE_SIZE_SELECT_ID
        self.total_items_span_id = config.TOTAL_ITEMS_SPAN_ID
        # self.page_input_id = config.PAGE_INPUT_ID # 주석 처리
        # self.page_move_button_id = config.PAGE_MOVE_BUTTON_ID # 주석 처리
        self.results_grid_body_id = config.RESULTS_GRID_BODY_ID


    @retry(attempts=2, delay_seconds=3, backoff_factor=1.5)
    def initialize_search(self):
        """Navigates to the ongoing filter page, sets filters, and performs the search."""
        # Original logic from crawler.initialize_ongoing_search
        if config.DEBUG: logger.debug(f"Navigating to filter page: {config.URL_ONGOING_FILTER}")
        self.driver.get(config.URL_ONGOING_FILTER)
        if config.DEBUG: logger.debug(f"Initial page title: '{self.driver.title}'")

        if config.DEBUG:
            html_content = self.driver.page_source
            os.makedirs(config.DEBUG_DIR, exist_ok=True)
            initial_html_path = os.path.join(config.DEBUG_DIR, 'ongoing_initial_page.html')
            try:
                if not os.path.exists(initial_html_path):
                    with open(initial_html_path, 'w', encoding='utf-8') as f: f.write(html_content)
                    logger.debug(f"Saved initial page HTML to {initial_html_path}")
            except Exception as e: 
                logger.error(f"Error saving initial HTML: {e}", exc_info=True)
                pass

        try:
            if config.DEBUG: logger.debug(f"Waiting for search form table (ID: {config.SEARCH_FORM_TABLE_ID})...")
            self.wait.until(EC.presence_of_element_located((By.ID, config.SEARCH_FORM_TABLE_ID)))
            if config.DEBUG: logger.debug(f"Search form table found.")
        except TimeoutException:
            logger.error(f"Timeout waiting for search form table ({config.SEARCH_FORM_TABLE_ID}).")
            if config.DEBUG:
                debug_file_path = os.path.join(config.DEBUG_DIR, 'ongoing_filter_form_timeout.html')
                try:
                    with open(debug_file_path, 'w', encoding='utf-8') as f: f.write(self.driver.page_source)
                    logger.debug(f"Saved HTML on form timeout to {debug_file_path}")
                except Exception as e: 
                    logger.error(f"Error saving debug HTML: {e}", exc_info=True)
                    pass
            return False

        if config.DEBUG: logger.debug("Setting filters...")
        try:
            current_year = str(time.strftime("%Y")) # time 모듈 임포트 필요
            if config.DEBUG: logger.debug(f"Setting Case Year: {current_year}")
            year_select_element = self.wait.until(EC.element_to_be_clickable((By.ID, config.CASE_YEAR_SELECT_ID)))
            Select(year_select_element).select_by_visible_text(current_year)

            if config.DEBUG: logger.debug("Setting Court: '전체'...")
            # 수정: 직접 locator 튜플을 넘겨서 element_to_be_clickable 호출
            court_elem = self.wait.until(EC.element_to_be_clickable((By.ID, config.COURT_SELECT_ID)))
            Select(court_elem).select_by_visible_text("전체")


            if config.DEBUG: logger.debug(f"{time.strftime('%H:%M:%S')} - Waiting for search button (ID: {config.SEARCH_BUTTON_ID})...")
            
            # presence_of + element_to_be_clickable 중복 제거
            search_btn = self.wait.until(
                EC.element_to_be_clickable((By.ID, config.SEARCH_BUTTON_ID))
            )
            self.driver.execute_script("arguments[0].click();", search_btn)

            if config.DEBUG: logger.debug(f"{time.strftime('%H:%M:%S')} - Search click executed.")
            if config.DEBUG: logger.debug(f"{time.strftime('%H:%M:%S')} - Title after search: '{self.driver.title}'")
            return True
        except (NoSuchElementException, TimeoutException) as e:
            logger.error(f"Error during filter selection/search: {e}.", exc_info=True)
            if config.DEBUG:
                debug_file_path = os.path.join(config.DEBUG_DIR, 'ongoing_filter_error.html')
                try:
                    with open(debug_file_path, 'w', encoding='utf-8') as f: f.write(self.driver.page_source)
                    logger.debug(f"Saved HTML on filter error to {debug_file_path}")
                except Exception as save_e: 
                    logger.error(f"Error saving debug HTML: {save_e}", exc_info=True)
                    pass
            return False

    @retry(attempts=3, delay_seconds=2, backoff_factor=2, exceptions_to_catch=(TimeoutException, StaleElementReferenceException))
    def wait_for_grid(self, current_page_expected: int | None = 1, is_retry: bool = False) -> bool:
        """Waits for the search results grid (and optionally pagination) to be present and visible."""
        # __init__에서 한 번 저장해 둔 값 사용
        effective_wait_timeout = self.default_timeout
        time.sleep(0.2) # DOM 변경을 위한 최소 대기 시간

        log_page_str = 'any' if current_page_expected is None else str(current_page_expected)
        if config.DEBUG: logger.debug(f"{time.strftime('%H:%M:%S')} - Entering wait_for_results_grid (Page: {log_page_str}, Retry: {is_retry}, Timeout: {effective_wait_timeout:.1f}s)")

        try:
            grid_selector_present = WebDriverWait(self.driver, effective_wait_timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, config.RESULTS_GRID_SELECTOR)),
                message=f"Timeout waiting for RESULTS_GRID_SELECTOR ({config.RESULTS_GRID_SELECTOR}) presence."
            )
            if config.DEBUG: logger.debug(f"{time.strftime('%H:%M:%S')} - RESULTS_GRID_SELECTOR found.")

            grid_body_present = WebDriverWait(self.driver, effective_wait_timeout).until(
                EC.presence_of_element_located((By.ID, self.results_grid_body_id)),
                message=f"Timeout waiting for RESULTS_GRID_BODY_ID ({self.results_grid_body_id}) presence."
            )
            if config.DEBUG: logger.debug(f"{time.strftime('%H:%M:%S')} - RESULTS_GRID_BODY_ID found.")
            
            if current_page_expected is not None:
                pagination_div_present = WebDriverWait(self.driver, effective_wait_timeout).until(
                    EC.presence_of_element_located((By.ID, config.PAGINATION_DIV_ID)),
                    message=f"Timeout waiting for PAGINATION_DIV_ID ({config.PAGINATION_DIV_ID}) presence."
                )
                if config.DEBUG: logger.debug(f"{time.strftime('%H:%M:%S')} - PAGINATION_DIV_ID found.")

                # 페이지 번호 확인 XPath 수정: normalize-space() 사용 및 대기 시간 증가
                active_page_xpath = f"//div[@id='{config.PAGINATION_DIV_ID}']//strong[normalize-space(.)='{current_page_expected}'] | //div[@id='{config.PAGINATION_DIV_ID}']//a[contains(@class, 'w2pageList_label_selected') and normalize-space(.)='{current_page_expected}']"
                try:
                    if config.DEBUG: logger.debug(f"{time.strftime('%H:%M:%S')} - Attempting check for active page {current_page_expected} with XPath: {active_page_xpath}")
                    # 페이지 번호 확인 대기 시간을 조금 더 늘림 (예: 5초)
                    WebDriverWait(self.driver, 5).until(
                        EC.visibility_of_element_located((By.XPATH, active_page_xpath)),
                        message=f"Timeout waiting for active page {current_page_expected} (XPath: {active_page_xpath}) visibility."
                    )
                    if config.DEBUG: logger.debug(f"{time.strftime('%H:%M:%S')} - Active page {current_page_expected} confirmed by XPath.")
                except TimeoutException:
                    logger.warning(f"{time.strftime('%H:%M:%S')} - Active page {current_page_expected} (XPath: {active_page_xpath}) not visible within 5s. Fallback: checking for first grid row content.")
                    # 첫 번째 행의 내용 (예: 첫 번째 td의 존재)으로 그리드 로드 확인 강화
                    first_row_content_css = f"#{self.results_grid_body_id} > tr:nth-child(1) > td:nth-child(1)"
                    WebDriverWait(self.driver, effective_wait_timeout).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, first_row_content_css))
                    )
                    if config.DEBUG: logger.debug(f"{time.strftime('%H:%M:%S')} - First grid row content found.")
            
            # 최종적으로 그리드 전체가 보이는지 확인
            WebDriverWait(self.driver, effective_wait_timeout).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, config.RESULTS_GRID_SELECTOR)),
                message=f"Timeout waiting for RESULTS_GRID_SELECTOR ({config.RESULTS_GRID_SELECTOR}) visibility."
            )
            if config.DEBUG: logger.debug(f"{time.strftime('%H:%M:%S')} - Results grid (Page: {log_page_str}) is visible. Returning True.")
            return True
        except TimeoutException:
            logger.error(f"{time.strftime('%H:%M:%S')} - TimeoutException in wait_for_results_grid (Page: {log_page_str}, Retry: {is_retry}).")
            if config.DEBUG:
                debug_file_path = os.path.join(config.DEBUG_DIR, f'results_grid_timeout_error_page_{log_page_str}_retry_{is_retry}.html')
                try:
                    with open(debug_file_path, 'w', encoding='utf-8') as f: f.write(self.driver.page_source)
                    logger.debug(f"Saved grid timeout error page HTML to {debug_file_path}")
                except Exception as html_save_e:
                    logger.error(f"Could not save grid timeout error page HTML: {html_save_e}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"{time.strftime('%H:%M:%S')} - Exception in wait_for_results_grid (Page: {log_page_str}, Retry: {is_retry}): {e}", exc_info=True)
            if config.DEBUG:
                debug_file_path = os.path.join(config.DEBUG_DIR, f'results_grid_general_error_page_{log_page_str}_retry_{is_retry}.html')
                try:
                    with open(debug_file_path, 'w', encoding='utf-8') as f: f.write(self.driver.page_source)
                    logger.debug(f"Saved grid general error page HTML to {debug_file_path}")
                except Exception as html_save_e:
                    logger.error(f"Could not save grid general error page HTML: {html_save_e}", exc_info=True)
            return False

    @retry(attempts=2, delay_seconds=2)
    def set_items_per_page(self, items_per_page: int = config.ITEMS_PER_PAGE) -> tuple[bool, int]:
        """Attempts to set the number of items displayed per page. Returns success and actual items per page."""
        # Original logic from crawler.set_page_size
        actual_items_per_page = 10 # Default
        logger.info(f"Attempting to set page size to {items_per_page}...")
        try:
            
            # element_to_be_clickable에 locator 전달, sleep 제거
            page_size_element = self.wait.until(
                EC.element_to_be_clickable((By.ID, self.page_size_selector_id))
            )
            page_size_select = Select(page_size_element)

            available_options = [opt.text for opt in page_size_select.options]
            current_selection_text = page_size_select.first_selected_option.text
            
            current_selection_numeric_match = re.search(r'\d+', current_selection_text)
            if current_selection_numeric_match:
                actual_items_per_page = int(current_selection_numeric_match.group())
            else:
                logger.warning(f"Could not parse numeric part from current page size '{current_selection_text}'. Defaulting to 10.")
                actual_items_per_page = 10

            logger.info(f"Page size dropdown found. Current: '{current_selection_text}' ({actual_items_per_page} items/page). Options: {available_options}")

            desired_option_text_full = None
            for opt_text in available_options:
                opt_numeric_match = re.search(r'\d+', opt_text)
                if opt_numeric_match and int(opt_numeric_match.group()) == items_per_page:
                    desired_option_text_full = opt_text
                    break
            
            if desired_option_text_full:
                if current_selection_text != desired_option_text_full:
                    logger.info(f"Attempting to select page size option: '{desired_option_text_full}'")
                    try:
                        page_size_select.select_by_visible_text(desired_option_text_full)
                        logger.info(f"Selenium select_by_visible_text for '{desired_option_text_full}' executed.")
                    except Exception as e_select:
                        logger.warning(f"Selenium select_by_visible_text failed for '{desired_option_text_full}': {e_select}. Trying JavaScript fallback.")
                        try:
                            option_value_to_set = None
                            for option_element_selenium in page_size_select.options:
                                if option_element_selenium.text == desired_option_text_full:
                                    option_value_to_set = option_element_selenium.get_attribute("value")
                                    break
                            
                            if option_value_to_set is not None:
                                script = f"arguments[0].value = '{option_value_to_set}'; arguments[0].dispatchEvent(new Event('change', {{'bubbles': true}}));"
                                logger.info(f"Executing JS: {script}")
                                self.driver.execute_script(script, page_size_element)
                                logger.info(f"JavaScript fallback: Set page size to value '{option_value_to_set}' (for text '{desired_option_text_full}') and triggered change event.")
                            else:
                                logger.error(f"JavaScript fallback FAILED: Could not find value attribute for option text '{desired_option_text_full}'.")
                                raise e_select 
                        except Exception as e_js:
                            logger.error(f"JavaScript fallback for page size selection also FAILED: {e_js}", exc_info=True)
                            raise e_js

                    actual_items_per_page = items_per_page 
                    logger.info(f"Page size selection attempted for {items_per_page}. Waiting for page to potentially reload ({config.UI_ACTION_DELAY_SECONDS} seconds)...") # config 값 사용
                    time.sleep(config.UI_ACTION_DELAY_SECONDS) # config 값 사용, 또는 명시적 대기
                    
                    logger.debug(f"Current URL before grid check: {self.driver.current_url}")
                    logger.debug(f"Current Title before grid check: {self.driver.title}")
                    logger.debug("Checking if results grid reloaded properly after page size change attempt...")
                    
                    # wait_for_grid는 이제 self의 메서드이므로 self.wait_for_grid로 호출
                    grid_reloaded = self.wait_for_grid(current_page_expected=1) 
                    if grid_reloaded:
                        logger.info("Results grid considered reloaded successfully after page size change.")
                    else:
                        logger.error("ERROR: Results grid FAILED to reload or validate after page size change.")
                        self._debug_save_page_source("grid_reload_fail_after_page_size_set.html")
                    
                    logger.info(f"Actual items per page after attempting to set to {items_per_page} (final from function): {actual_items_per_page}")
                    return grid_reloaded, actual_items_per_page
                else:
                    logger.info(f"Page size already set to '{desired_option_text_full}'. Actual items per page: {actual_items_per_page}")
                    return True, actual_items_per_page 
            else:
                logger.warning(f"Desired page size {items_per_page} (option text like '{items_per_page}건씩') not found in {available_options}. Using current ({actual_items_per_page}).")
                grid_still_valid = self.wait_for_grid(current_page_expected=1) # self.wait_for_grid 사용
                logger.info(f"Actual items per page (requested size not available): {actual_items_per_page}")
                return grid_still_valid, actual_items_per_page
        except (NoSuchElementException, TimeoutException) as e:
            logger.warning(f"Could not find/interact with page size dropdown (ID: {self.page_size_selector_id}): {e}. Defaulting actual items/page to {actual_items_per_page}.")
            self._debug_save_page_source("page_size_dropdown_error.html")
            grid_still_valid = self.wait_for_grid(current_page_expected=1) # self.wait_for_grid 사용
            logger.info(f"Actual items per page (dropdown error, returning): {actual_items_per_page}")
            return grid_still_valid, actual_items_per_page
        except Exception as e:
            logger.error(f"Unexpected error in set_items_per_page: {e}. Defaulting actual items/page to {actual_items_per_page}.", exc_info=True)
            self._debug_save_page_source("page_size_unexpected_error.html")
            grid_still_valid = self.wait_for_grid(current_page_expected=1) # self.wait_for_grid 사용
            logger.info(f"Actual items per page (unexpected error, returning): {actual_items_per_page}")
            return grid_still_valid, actual_items_per_page

    @retry(attempts=2, delay_seconds=1)
    def _debug_save_page_source(self, filename: str):
        """Helper method to save current page source for debugging if DEBUG is True."""
        if config.DEBUG:
            if not hasattr(config, 'DEBUG_DIR') or not config.DEBUG_DIR:
                logger.warning("(_debug_save_page_source): config.DEBUG_DIR is not set. Cannot save debug HTML.")
                return
            
            debug_file_path = os.path.join(config.DEBUG_DIR, filename)
            try:
                os.makedirs(config.DEBUG_DIR, exist_ok=True)
                with open(debug_file_path, 'w', encoding='utf-8') as f:
                    f.write(self.driver.page_source)
                logger.debug(f"Saved debug HTML to {debug_file_path}")
            except Exception as e:
                logger.error(f"Could not save debug HTML to {debug_file_path}: {e}", exc_info=True)

    @retry(attempts=3, delay_seconds=1.5, exceptions_to_catch=(NoSuchElementException, ElementClickInterceptedException, StaleElementReferenceException))
    def get_total_pages_count(self, current_items_per_page: int) -> int:
        """
        Enhanced logic to get total pages, considering cases where total items span might not be reliable
        or pagination elements provide more direct information.
        """
        self.logger.debug("Attempting to get total pages with enhanced logic...")
        total_pages = 0
        
        try:
            # 1. Try to get total items from the dedicated span
            total_items_span = self.wait.until(
                EC.presence_of_element_located((By.ID, self.total_items_span_id))
            )
            total_items_text = total_items_span.text.strip() # 예: "384건"
            self.logger.debug(f"Total items text from span: '{total_items_text}'")

            # 숫자만 추출하도록 수정 (정규식 사용)
            match = re.search(r'\d+', total_items_text)
            if match:
                total_items = int(match.group(0))
                if total_items > 0 and current_items_per_page > 0:
                    total_pages = math.ceil(total_items / current_items_per_page)
                    self.logger.info(f"Calculated total pages: {total_pages} from total items {total_items} and {current_items_per_page} items/page.")
                    # return total_pages # 여기서 바로 반환하면 아래 로직을 타지 않음
            else:
                self.logger.warning(f"Could not parse total items from text: '{total_items_text}'. Will rely on pagination controls.")
        
        except (TimeoutException, NoSuchElementException, AttributeError, ValueError) as e:
            self.logger.warning(f"Could not find or parse total items span (ID: {self.total_items_span_id}, Text: '{total_items_text if 'total_items_text' in locals() else 'N/A'}'). Error: {e}. Will rely on pagination controls.")
            # total_pages는 0으로 유지

        # 페이지네이션 컨트롤을 통해 실제 페이지 수 확인
        max_page_found = 0
        try:
            pagination_div = self.wait.until(EC.presence_of_element_located((By.ID, config.PAGINATION_DIV_ID)))
            
            # 현재 보이는 페이지 번호들 중 최대값 찾기
            def get_max_visible_page(driver, pag_div):
                current_max = 0
                locator = (By.CSS_SELECTOR, config.PAGINATION_PAGE_NUMBER_LINK_SELECTOR)

                try:
                    # 현재 보이는 페이지 번호 앵커들을 '그때그때' 다시 로케이트
                    links = pag_div.find_elements(*locator)
                    texts_snapshot = []
                    for idx in range(len(links)):
                        try:
                            # 다시 로케이트(중요): 기존 핸들 대신 새 핸들
                            link = pag_div.find_elements(*locator)[idx]
                            # href가 안정적이면 href에서 숫자 파싱
                            href = link.get_attribute("href") or ""
                            m = re.search(r"[?&]page=(\d+)", href)
                            if m:
                                texts_snapshot.append(m.group(1))
                            else:
                                texts_snapshot.append(link.text.strip())
                        except StaleElementReferenceException:
                            # 해당 인덱스만 스킵
                            continue

                    for t in texts_snapshot:
                        if t.isdigit():
                            current_max = max(current_max, int(t))

                except Exception as e_vis:
                    self.logger.warning(f"Error getting visible page numbers: {e_vis}", exc_info=config.DEBUG)

                return current_max

            max_page_found = get_max_visible_page(self.driver, pagination_div)
            self.logger.debug(f"Initial max visible page: {max_page_found}")

            # "마지막 페이지" 버튼으로 직접 시도 (onclick 속성 파싱)
            # 이 방법은 웹사이트 구조에 따라 불안정할 수 있음. 제공된 HTML에는 onclick이 없음.
            # 여기서는 "마지막 페이지" 버튼을 클릭하고 그 결과를 보는 방식으로 수정
            try:
                last_page_button = pagination_div.find_element(By.CSS_SELECTOR, config.PAGINATION_LAST_PAGE_BUTTON_SELECTOR)
                if last_page_button.is_enabled() and last_page_button.is_displayed():
                    self.logger.debug("Attempting to click 'Last Page' button to determine total pages.")
                    # StaleElementReferenceException 방지를 위해 다시 찾을 수 있음
                    self.driver.execute_script("arguments[0].click();", last_page_button)
                    # 페이지 로드 대기 - wait_for_grid는 특정 페이지를 기대하므로, 여기서는 간단한 대기 또는 특정 요소 대기
                    self.wait.until(EC.staleness_of(pagination_div)) # 이전 페이지네이션 요소가 사라질 때까지
                    pagination_div = self.wait.until(EC.presence_of_element_located((By.ID, config.PAGINATION_DIV_ID))) # 새 페이지네이션 요소
                    time.sleep(config.UI_ACTION_DELAY_SECONDS) # 추가 안정화 시간
                    
                    last_page_nav_max = get_max_visible_page(self.driver, pagination_div)
                    self.logger.debug(f"Max visible page after clicking 'Last Page' button: {last_page_nav_max}")
                    max_page_found = max(max_page_found, last_page_nav_max)
                    
                    # "첫 페이지"로 돌아오거나, 다음 그룹 탐색을 위해 안정적인 상태로 복귀
                    first_page_button = pagination_div.find_element(By.CSS_SELECTOR, config.PAGINATION_FIRST_PAGE_BUTTON_SELECTOR)
                    if first_page_button.is_enabled() and first_page_button.is_displayed():
                         self.driver.execute_script("arguments[0].click();", first_page_button)
                         self.wait.until(EC.staleness_of(pagination_div))
                         pagination_div = self.wait.until(EC.presence_of_element_located((By.ID, config.PAGINATION_DIV_ID)))
                         time.sleep(config.UI_ACTION_DELAY_SECONDS)
                         self.logger.debug("Returned to first page group after 'Last Page' check.")
            except (NoSuchElementException, TimeoutException):
                self.logger.debug("'Last Page' button not found or not clickable, or timed out after click. Proceeding with iterative 'Next Group' clicking.")
            except Exception as e_last_page:
                 self.logger.warning(f"Error interacting with 'Last Page' button: {e_last_page}", exc_info=config.DEBUG)


            # "다음 목록" 버튼을 이용한 반복 탐색
            # 최대 10번의 "다음 그룹" 클릭 시도 (무한 루프 방지) 또는 total_pages 기반 제한
            # total_pages가 0이면, 아이템 수 파싱에 실패했으므로 더 많이 시도할 수 있음
            max_next_clicks = (total_pages // 10) + 5 if total_pages > 0 else 15 # 충분한 클릭 시도 횟수
            
            for click_count in range(max_next_clicks):
                try:
                    # 페이지네이션 div를 매번 다시 찾아서 StaleElement 예방
                    current_pagination_div = self.wait.until(EC.presence_of_element_located((By.ID, config.PAGINATION_DIV_ID)))
                    next_group_button = current_pagination_div.find_element(By.CSS_SELECTOR, config.PAGINATION_NEXT_GROUP_BUTTON_SELECTOR)
                    
                    if next_group_button.is_enabled() and next_group_button.is_displayed():
                        self.logger.debug(f"Clicking 'Next Group' button (Attempt {click_count + 1}). Current max_page_found: {max_page_found}")
                        self.driver.execute_script("arguments[0].click();", next_group_button)
                        
                        # 이전 페이지네이션 요소가 사라질 때까지 대기 (StaleElementReferenceException 방지)
                        self.wait.until(EC.staleness_of(current_pagination_div))
                        # 새 페이지네이션 요소가 로드될 때까지 대기
                        current_pagination_div = self.wait.until(EC.presence_of_element_located((By.ID, config.PAGINATION_DIV_ID)))
                        time.sleep(config.UI_ACTION_DELAY_SECONDS) # JS 실행 후 DOM 변경 대기
                        
                        newly_visible_max_page = get_max_visible_page(self.driver, current_pagination_div)
                        self.logger.debug(f"Max page visible after 'Next Group' click: {newly_visible_max_page}")
                        
                        if newly_visible_max_page > max_page_found:
                            max_page_found = newly_visible_max_page
                        else:
                            # 더 이상 페이지 번호가 증가하지 않으면, 마지막 페이지 그룹에 도달한 것으로 간주
                            self.logger.debug("Max visible page did not increase after 'Next Group' click. Assuming end of pages.")
                            break 
                    else:
                        self.logger.debug("'Next Group' button is not enabled or not displayed. Assuming end of pages.")
                        break # 다음 버튼이 없거나 비활성화면 종료
                except (NoSuchElementException, TimeoutException):
                    self.logger.debug("'Next Group' button not found or timed out waiting for new pagination. Assuming end of pages.")
                    break # 버튼을 찾지 못하면 종료
                except Exception as e_next_click:
                    self.logger.warning(f"Error clicking 'Next Group' button or processing after: {e_next_click}", exc_info=config.DEBUG)
                    break # 예기치 않은 오류 시 종료

            # "첫 페이지"로 돌아와서 다음 작업에 영향 없도록 함
            try:
                # Re-locate elements before interaction to avoid staleness from previous operations.
                current_pagination_div_for_first_btn = self.wait.until(EC.presence_of_element_located((By.ID, config.PAGINATION_DIV_ID)))
                first_page_button = current_pagination_div_for_first_btn.find_element(By.CSS_SELECTOR, config.PAGINATION_FIRST_PAGE_BUTTON_SELECTOR)
                
                if first_page_button.is_enabled() and first_page_button.is_displayed():
                    self.logger.debug("Attempting to return to the first page/group for stable state.")
                    self.driver.execute_script("arguments[0].click();", first_page_button)
                    
                    # Use a shorter wait for staleness check as it's non-critical and might time out
                    short_staleness_wait = WebDriverWait(self.driver, 3) # 3 seconds timeout
                    try:
                        short_staleness_wait.until(EC.staleness_of(current_pagination_div_for_first_btn))
                        # If staleness succeeded, then wait for the new pagination div with the default wait time
                        self.wait.until(EC.presence_of_element_located((By.ID, config.PAGINATION_DIV_ID)))
                        time.sleep(config.UI_ACTION_DELAY_SECONDS) # 안정화
                        self.logger.debug("Successfully returned to the first page/group.")
                    except TimeoutException:
                        self.logger.warning("Returning to first page/group: Timed out waiting for current pagination div to become stale within 3s. Page might not have reloaded or was already on the first group. Checking for pagination presence.")
                        # Even if staleness check fails, try to see if a pagination div is still present with default wait.
                        try:
                            self.wait.until(EC.presence_of_element_located((By.ID, config.PAGINATION_DIV_ID)))
                            self.logger.debug("A pagination div is still present after staleness check timeout.")
                        except TimeoutException:
                            self.logger.warning("Pagination div also not found after staleness check timeout. Page state might be unstable.")
                else:
                    self.logger.debug("First page button not enabled/displayed; no attempt to return to first page group.")

            except NoSuchElementException: 
                 self.logger.warning("Could not find 'First Page' button to return.", exc_info=False)
            except TimeoutException as e_timeout_finding_button: 
                 self.logger.warning(f"Timeout waiting for 'First Page' button: {e_timeout_finding_button}", exc_info=False)
            except Exception as e_return_first: 
                self.logger.warning(f"Unexpected error while trying to return to the first page/group: {type(e_return_first).__name__} - {e_return_first}", exc_info=config.DEBUG)

        except Exception as e_outer:
            self.logger.error(f"Major error in get_total_pages_count pagination logic: {e_outer}", exc_info=config.DEBUG)
            # max_page_found가 0이고 total_pages도 신뢰할 수 없다면, 기본값 반환
            if max_page_found == 0 and total_pages == 0: # calculated_pages -> total_pages
                self.logger.warning("Failed to determine page count through both calculation and pagination controls. Defaulting to 1.")
                return 1 # 또는 0, 상황에 따라
            # 아니면 둘 중 하나라도 값이 있으면 그 값을 사용


        # 최종 페이지 수 결정
        if max_page_found > 0:
            if total_pages > 0 and total_pages != max_page_found: # calculated_pages -> total_pages
                self.logger.warning(f"Final check: Calculated pages ({total_pages}) and pages found via controls ({max_page_found}) differ. Trusting controls.")
            self.logger.info(f"Total pages determined by pagination controls: {max_page_found}")
            return max_page_found
        elif total_pages > 0: # calculated_pages -> total_pages
            self.logger.info(f"Total pages determined by item count calculation (pagination controls failed or gave no info): {total_pages}")
            return total_pages
        else:
            # 두 방법 모두 실패한 극단적인 경우
            self.logger.error("Failed to determine total pages by any method. Returning 0. This will likely stop pagination.")
            # 목록에 아이템이 있는지 한번 더 확인하여 1 또는 0을 결정할 수도 있음
            try:
                self.driver.find_element(By.CSS_SELECTOR, f"#{self.results_grid_body_id} > tr")
                self.logger.warning("Found at least one item row, but page count failed. Defaulting to 1 page.")
                return 1
            except NoSuchElementException:
                self.logger.warning("No item rows found and page count failed. Defaulting to 0 pages.")
                return 0

    def get_current_page_number_from_pagination(self) -> int | None:
        """Reads the currently active page number from the pagination control."""
        try:
            pagination_div = self.wait.until(EC.presence_of_element_located((By.ID, config.PAGINATION_DIV_ID)))
            # 현재 페이지는 보통 strong 태그로 표시되거나, 특정 클래스를 가짐
            # 예시: <div id="mf_wfm_mainFrame_pgl_gdsDtlSrchPage_inner"><strong title="현재페이지">1</strong> ...</div>
            # 또는 <a class="w2pageList_control_label w2pageList_label_selected">1</a>
            active_page_element = pagination_div.find_element(By.XPATH, ".//strong[@title='현재페이지'] | .//a[contains(@class, 'w2pageList_label_selected')]")
            page_text = active_page_element.text.strip()
            if page_text.isdigit():
                current_page = int(page_text)
                if config.DEBUG: self.logger.debug(f"Current active page number from pagination: {current_page}")
                return current_page
            else:
                self.logger.warning(f"Could not parse current page number from pagination text: '{page_text}'")
                return None
        except (NoSuchElementException, TimeoutException):
            self.logger.warning("Could not find or read active page number from pagination.")
            return None
        except Exception as e:
            self.logger.error(f"Error getting current page number from pagination: {e}", exc_info=config.DEBUG)
            return None

    @retry(attempts=3, delay_seconds=2, backoff_factor=1.5)
    def go_to_page_number(self, target_page: int) -> bool:
        """Navigates to a specific page number using pagination controls."""
        if config.DEBUG: logger.debug(f"Attempting to go to page {target_page} using pagination controls...")

        current_page_num_from_ui = self.get_current_page_number_from_pagination()
        if current_page_num_from_ui == target_page:
            logger.info(f"Already on target page {target_page}. No navigation needed.")
            return True

        try:
            pagination_div = self.wait.until(EC.presence_of_element_located((By.ID, config.PAGINATION_DIV_ID)))
            
            # 전략 1: 페이지 번호 링크 직접 클릭 (가장 일반적)
            # 대상 페이지 번호와 정확히 일치하는 텍스트를 가진 <a> 태그 또는 <strong> 태그 찾기
            # (현재 페이지는 strong, 다른 페이지는 a 태그일 수 있음)
            page_link_xpath = f".//a[normalize-space(text())='{target_page}'] | .//strong[normalize-space(text())='{target_page}']"
            
            try:
                page_link = WebDriverWait(pagination_div, 5).until(
                    EC.element_to_be_clickable((By.XPATH, page_link_xpath))
                )
                logger.info(f"Found clickable page link for {target_page}. Clicking...")
                self.driver.execute_script("arguments[0].click();", page_link)
                # 클릭 후 페이지 로드 확인은 호출하는 쪽에서 wait_for_grid를 통해 수행
                return True
            except TimeoutException:
                logger.warning(f"Direct page link for {target_page} not found or not clickable within 5s. Trying 'Next Group' button strategy if applicable.")
            except Exception as e_click_direct:
                logger.error(f"Error clicking direct page link for {target_page}: {e_click_direct}", exc_info=config.DEBUG)
                # 이 경우에도 다음 전략으로 넘어갈 수 있도록 return False는 하지 않음

            # 전략 2: "다음 목록" 버튼을 사용하여 목표 페이지에 도달할 때까지 클릭
            # 이 전략은 target_page가 현재 페이지보다 클 때만 유효
            # 또한, 중간에 페이지 번호를 정확히 클릭할 수 없는 경우 (예: ... 으로 생략된 경우)에 유용
            if current_page_num_from_ui is not None and target_page > current_page_num_from_ui:
                max_next_group_clicks = 15 # 무한 루프 방지
                for _ in range(max_next_group_clicks):
                    current_pagination_div_for_next = self.wait.until(EC.presence_of_element_located((By.ID, config.PAGINATION_DIV_ID)))
                    active_page_after_next_click = self.get_current_page_number_from_pagination()
                    if active_page_after_next_click == target_page:
                        logger.info(f"Reached target page {target_page} by checking after potential 'Next Group' clicks.")
                        return True
                    
                    # 현재 보이는 페이지들 중 target_page가 있는지 다시 확인 (직접 클릭 가능하면 클릭)
                    try:
                        page_link_on_current_view = WebDriverWait(current_pagination_div_for_next, 2).until(
                             EC.element_to_be_clickable((By.XPATH, f".//a[normalize-space(text())='{target_page}']"))
                        )
                        logger.info(f"Found page link for {target_page} after some 'Next Group' considerations. Clicking...")
                        self.driver.execute_script("arguments[0].click();", page_link_on_current_view)
                        return True
                    except TimeoutException:
                        logger.debug(f"Target page {target_page} link not immediately visible/clickable. Will try 'Next Group' if available.")

                    try:
                        next_group_button = current_pagination_div_for_next.find_element(By.CSS_SELECTOR, config.PAGINATION_NEXT_GROUP_BUTTON_SELECTOR)
                        if next_group_button.is_enabled() and next_group_button.is_displayed():
                            logger.info(f"Clicking 'Next Group' button to reach page {target_page}. Current: {active_page_after_next_click}")
                            self.driver.execute_script("arguments[0].click();", next_group_button)
                            self.wait.until(EC.staleness_of(current_pagination_div_for_next)) # 이전 페이지네이션 요소가 사라질 때까지
                            time.sleep(config.UI_ACTION_DELAY_SECONDS) # 새 페이지네이션 로드 대기
                        else:
                            logger.warning(f"'Next Group' button not available or not interactable. Cannot reach page {target_page} this way.")
                            break # 다음 그룹 버튼이 없으면 루프 종료
                    except NoSuchElementException:
                        logger.warning(f"'Next Group' button not found. Cannot reach page {target_page} this way.")
                        break # 버튼 없으면 루프 종료
                    except Exception as e_next_group:
                        logger.error(f"Error clicking 'Next Group' button: {e_next_group}", exc_info=config.DEBUG)
                        break # 오류 시 루프 종료
            
            # 여기에 JavaScript f_goPage(target_page) 직접 호출을 최후의 수단으로 추가 고려 가능
            # 하지만 현재 f_goPage가 정의되지 않았다는 오류이므로, 이 방법은 제외.
            logger.error(f"Failed to navigate to page {target_page} using available pagination strategies.")
            self._debug_save_page_source(f'page_nav_failed_to_{target_page}.html')
            return False

        except TimeoutException:
            logger.error(f"Timeout finding pagination div (ID: {config.PAGINATION_DIV_ID}) for page navigation to {target_page}.")
            self._debug_save_page_source(f'page_nav_pagination_div_timeout_to_{target_page}.html')
            return False
        except Exception as e:
            logger.error(f"Error navigating to page {target_page}: {e}", exc_info=True)
            self._debug_save_page_source(f'page_nav_error_to_{target_page}.html')
            return False

    def get_current_page_items(self, current_page_number: int) -> list[dict]:
        """Gets current page HTML, parses it, and returns auction items."""
        if config.DEBUG: logger.debug(f"Getting and parsing items for page {current_page_number}...")
        try:
            # 결과 그리드가 확실히 로드되었는지 여기서 한 번 더 확인하거나, 호출하는 쪽에서 보장해야 함.
            # AuctionListPage.wait_for_grid 가 이미 호출된 후 이 메소드가 호출된다고 가정.
            current_html = self.driver.page_source
            # parse_ongoing_list는 이 파일 상단에서 from .parsers import parse_ongoing_list 로 가져옴
            parsed_items = parse_ongoing_list(current_html)
            if config.DEBUG: 
                logger.debug(f"Page {current_page_number} parsed. Found {len(parsed_items)} base items.")
            
            items_with_index = []
            for idx, item_info in enumerate(parsed_items):
                item_info['_item_index_on_page'] = idx # 페이지 내 0-indexed 순서 추가
                if config.DEBUG:
                    dc_no = item_info.get('display_case_no', '[NOT_FOUND]') 
                    it_no = item_info.get('item_no', '[NOT_FOUND]')
                    auc_no = item_info.get('auction_no', '[NOT_FOUND]')
                    item_idx_on_page = item_info.get('_item_index_on_page', -1)
                    logger.debug(f"  Item {idx}: auction_no='{auc_no}', display_case_no='{dc_no}', item_no='{it_no}', _item_index_on_page='{item_idx_on_page}'")
                items_with_index.append(item_info)
            return items_with_index
        except Exception as e:
            logger.error(f"Error parsing page {current_page_number}: {e}", exc_info=True)
            # _debug_save_page_source는 self의 메서드이므로 호출 가능
            self._debug_save_page_source(f"page_parse_error_page_{current_page_number}.html")
            return []

    @retry(attempts=3, delay_seconds=1.5, exceptions_to_catch=(NoSuchElementException, ElementClickInterceptedException, StaleElementReferenceException))
    def click_item_detail_link(self,
                             display_case_text: str,
                             item_no_text: str,
                             full_auction_no_for_onclick_fallback: str,
                             case_year_for_onclick_fallback: str,
                             case_number_part_for_onclick_fallback: str,
                             item_index_on_page_for_onclick_fallback: int
                             ) -> bool:
        """
        Attempts to click the detail link for an item in the auction list.
        It tries multiple strategies to locate and click the link.

        Args:
            display_case_text: The case number text as displayed on the page (e.g., "2023타경12345").
                               Used by Strategy 0 for text-based matching.
            item_no_text: The item number text (e.g., "1"). Used by Strategy 0.
            full_auction_no_for_onclick_fallback: Full auction number (e.g., "2023타경12345-1"). Potentially for logging or future use.
            case_year_for_onclick_fallback: Year part of case number (e.g., "2023"). Potentially for logging or future use.
            case_number_part_for_onclick_fallback: Number part of case number (e.g., "12345"). Potentially for logging or future use.
            item_index_on_page_for_onclick_fallback: The 0-based index of the item on the current page. Used for moveStPage JS call.

        Returns:
            True if the click was successful and navigation to detail page is expected, False otherwise.
        """
        logger.info(f"Attempting to click detail link for Case: '{display_case_text}', Item No: '{item_no_text}', ItemIndexOnPage: {item_index_on_page_for_onclick_fallback}")

        js_call_succeeded = False
        last_error_from_fallbacks = "No strategies attempted or all failed before error could be logged."

        # New Main Strategy: Using JavaScript moveStPage(item_index_on_page) - TRY THIS FIRST
        if item_index_on_page_for_onclick_fallback >= 0:
            logger.info(f"Main JS Strategy (Priority): Attempting JS call with moveStPage({item_index_on_page_for_onclick_fallback}).")
            try:
                js_script_main = f"moveStPage({item_index_on_page_for_onclick_fallback});"
                logger.debug(f"Main JS Strategy (Priority): Executing JS: {js_script_main}")
                self.driver.execute_script(js_script_main)
                js_call_succeeded = True
                logger.info(f"Main JS Strategy (Priority): Successfully executed JS moveStPage({item_index_on_page_for_onclick_fallback}) for item originally '{display_case_text}-{item_no_text}'.")
                return True # 성공 시 즉시 True 반환
            except Exception as e_js_main:
                logger.warning(f"Main JS Strategy (Priority) (moveStPage({item_index_on_page_for_onclick_fallback})) failed for item '{display_case_text}-{item_no_text}': {e_js_main}. Proceeding to XPath strategy.", exc_info=config.DEBUG) # DEBUG 레벨로 변경
                last_error_from_fallbacks = f"Main JS Strategy (Priority) failed: {e_js_main}"
        else:
            logger.info(f"Main JS Strategy (Priority): Invalid item_index_on_page_for_onclick_fallback ({item_index_on_page_for_onclick_fallback}). Skipping direct JS call, proceeding to XPath strategy.")
            last_error_from_fallbacks = f"Main JS Strategy (Priority): Invalid item_index ({item_index_on_page_for_onclick_fallback})"


        # Fallback Strategy 0: Text-based matching (기존 로직, JS 우선 호출 실패 시 실행)
        if not js_call_succeeded:
            if display_case_text and item_no_text:
                try:
                    logger.info(f"Fallback Strategy (XPath): Attempting text-based match with Case Text: '{display_case_text}', Item No: '{item_no_text}'")
                    # ... (기존 XPath 로직은 여기에 유지) ...
                    input_case_no_part_for_match = ""
                    if display_case_text:
                        parts = display_case_text.split('-')
                        if parts and parts[0].strip():
                            input_case_no_part_for_match = parts[0].strip()
                        else: 
                            logger.warning(f"Fallback Strategy (XPath): display_case_text ('{display_case_text}') could not be split by '-' to get a valid case number part, or the part was empty.")
                    else: 
                        logger.warning("Fallback Strategy (XPath): display_case_text is empty for text-based match.")

                    xpath_strategy_0 = f"""
                        //div[@id='{config.RESULTS_GRID_BODY_ID}']//tr[
                            (
                                normalize-space(td[2]//text()) = '{display_case_text}' 
                                or 
                                (contains('{display_case_text}', '-') and normalize-space(substring-before(td[2]//text(), '-')) = '{input_case_no_part_for_match}' and '{input_case_no_part_for_match}' != '')
                                or
                                (normalize-space(td[2]//text()) = '{input_case_no_part_for_match}' and '{input_case_no_part_for_match}' != '')
                            )
                            and 
                            normalize-space(td[3]//text()) = '{item_no_text}'
                        ]/td//a[contains(@onclick, 'moveStPage') or contains(@onclick, 'f_moveStPage')][1]
                    """
                    logger.debug(f"Fallback Strategy (XPath) XPath: {xpath_strategy_0}")

                    link_to_click = self.wait.until(EC.element_to_be_clickable((By.XPATH, xpath_strategy_0)))
                    logger.info(f"Fallback Strategy (XPath): Link found and clickable for Case: '{display_case_text}', Item No: '{item_no_text}'. Attempting click...")
                    
                    logger.debug(f"Link details: Tag={link_to_click.tag_name}, Text='{link_to_click.text}', Visible={link_to_click.is_displayed()}, Enabled={link_to_click.is_enabled()}")

                    try:
                        link_to_click.click()
                        # js_call_succeeded = True # 이 변수는 더 이상 여기서 주된 성공 지표가 아님
                        logger.info(f"Fallback Strategy (XPath): Successfully clicked item link for Case: '{display_case_text}', Item No: '{item_no_text}' using text-based XPath.")
                        return True 
                    except ElementClickInterceptedException as e_click_intercepted:
                        logger.warning(f"Fallback Strategy (XPath): ElementClickInterceptedException for Case '{display_case_text}', Item '{item_no_text}'. Error: {e_click_intercepted}. Trying JS click as fallback for XPath.")
                        try:
                            self.driver.execute_script("arguments[0].click();", link_to_click)
                            logger.info(f"Fallback Strategy (XPath - JS Fallback): Successfully clicked item link using JavaScript for Case: '{display_case_text}', Item No: '{item_no_text}'.")
                            return True 
                        except Exception as e_js_click:
                            logger.error(f"Fallback Strategy (XPath - JS Fallback): JavaScript click also failed for Case '{display_case_text}', Item '{item_no_text}'. Error: {e_js_click}", exc_info=True)
                            last_error_from_fallbacks = f"Fallback Strategy (XPath - JS Fallback) failed: {e_js_click}"
                    except Exception as e_click:
                        logger.error(f"Fallback Strategy (XPath): Click failed for Case '{display_case_text}', Item '{item_no_text}'. Error: {e_click}", exc_info=True)
                        last_error_from_fallbacks = f"Fallback Strategy (XPath) Click failed: {e_click}"

                except TimeoutException as e_timeout:
                    logger.warning(f"Fallback Strategy (XPath) failed for '{display_case_text}-{item_no_text}' with Timeout: {e_timeout.msg.splitlines()[0] if e_timeout.msg else 'No message'}")
                    last_error_from_fallbacks = f"Fallback Strategy (XPath) Timeout: {e_timeout.msg.splitlines()[0] if e_timeout.msg else 'No message'}"
                except Exception as e_strategy0:
                    logger.error(f"Fallback Strategy (XPath) for '{display_case_text}-{item_no_text}' encountered an unexpected error: {e_strategy0}", exc_info=True)
                    last_error_from_fallbacks = f"Fallback Strategy (XPath) Unexpected Error: {e_strategy0}"
            else:
                logger.info("Fallback Strategy (XPath) skipped due to missing display_case_text or item_no_text.")

        # 만약 JS 우선 호출이 실패하고, XPath 전략도 시도되었지만 실패했거나 스킵되었다면,
        # 이전에 사용하던 추가적인 JS Fallback (f_moveStPage)은 주석 처리/제거된 상태이므로 여기서는 더 이상 시도하지 않음.

        # 모든 전략 실패 시
        # if not js_call_succeeded: # js_call_succeeded는 이제 우선 JS 호출의 성공 여부만 나타냄. XPath 성공 시 이미 return True 되었음.
        # 위 주석은 잘못됨. js_call_succeeded는 초기 JS 시도에 대한 것이고, XPath 성공 시에는 return 되었으므로 이 지점에 도달하지 않음.
        # 따라서, 이 지점에 도달했다면 모든 시도가 실패한 것임.
        logger.error(f"All click strategies failed for Case Text: '{display_case_text}', Item No: '{item_no_text}', Index: {item_index_on_page_for_onclick_fallback}. Last error from attempts: {last_error_from_fallbacks}")
        return False # 모든 전략 실패

    @retry(attempts=3, delay_seconds=2, backoff_factor=1.5, exceptions_to_catch=(TimeoutException, NoSuchElementException))
    def search_auction_by_criteria(self, court_name: str, case_year: str, case_number: str) -> bool:
        """특정 조건으로 경매 검색"""
        try:
            logger.info(f"검색 조건 설정: 법원={court_name}, 연도={case_year}, 사건번호={case_number}")
            
            # 법원 선택
            if court_name and court_name != "전체":
                court_elem = self.wait.until(EC.element_to_be_clickable((By.ID, config.COURT_SELECT_ID)))
                Select(court_elem).select_by_visible_text(court_name)
                logger.debug(f"법원 선택: {court_name}")
            
            # 사건년도 선택
            if case_year:
                year_elem = self.wait.until(EC.element_to_be_clickable((By.ID, config.CASE_YEAR_SELECT_ID)))
                Select(year_elem).select_by_visible_text(case_year)
                logger.debug(f"사건년도 선택: {case_year}")
            
            # 사건번호 입력 (필요한 경우)
            if case_number:
                # 사건번호 입력 필드가 있다면 입력 (config에서 확인 필요)
                case_number_input_id = getattr(config, 'CASE_NUMBER_INPUT_ID', None)
                if case_number_input_id:
                    case_number_elem = self.wait.until(EC.element_to_be_clickable((By.ID, case_number_input_id)))
                    case_number_elem.clear()
                    case_number_elem.send_keys(case_number)
                    logger.debug(f"사건번호 입력: {case_number}")
            
            # 검색 버튼 클릭
            search_btn = self.wait.until(EC.element_to_be_clickable((By.ID, config.SEARCH_BUTTON_ID)))
            self.driver.execute_script("arguments[0].click();", search_btn)
            logger.debug("검색 버튼 클릭")
            
            # 결과 그리드 대기
            if self.wait_for_grid():
                logger.info("검색 완료 및 결과 그리드 로드 확인")
                return True
            else:
                logger.error("검색 후 그리드 로드 실패")
                return False
                
        except Exception as e:
            logger.error(f"검색 중 오류 발생: {e}", exc_info=True)
            return False


class AuctionDetailPage(BasePage):
    def __init__(self, driver, wait):
        super().__init__(driver, wait)
        # Locators for AuctionDetailPage
        self.photo_container_selector = config.PHOTO_CONTAINER_SELECTOR
        self.appraisal_button_id = config.APPRAISAL_BUTTON_ID
        self.modal_overlay_selector = config.MODAL_OVERLAY_SELECTOR
        self.appraisal_popup_iframe_id = config.APPRAISAL_POPUP_IFRAME_ID
        self.appraisal_inner_iframe_selector = config.APPRAISAL_INNER_IFRAME_SELECTOR
        self.modal_close_button_selector = config.MODAL_CLOSE_BUTTON_SELECTOR

    @retry(attempts=2, delay_seconds=1)
    def _debug_save_page_source(self, filename: str):
        """Helper method to save current page source for debugging if DEBUG is True."""
        if config.DEBUG:
            if not hasattr(config, 'DEBUG_DIR') or not config.DEBUG_DIR:
                logger.warning("(_debug_save_page_source): config.DEBUG_DIR is not set. Cannot save debug HTML.")
                return
            
            debug_file_path = os.path.join(config.DEBUG_DIR, filename)
            try:
                os.makedirs(config.DEBUG_DIR, exist_ok=True)
                with open(debug_file_path, 'w', encoding='utf-8') as f:
                    f.write(self.driver.page_source)
                logger.debug(f"Saved debug HTML to {debug_file_path}")
            except Exception as e:
                logger.error(f"Could not save debug HTML to {debug_file_path}: {e}", exc_info=True)

    @retry(attempts=3, delay_seconds=2, backoff_factor=2, exceptions_to_catch=(TimeoutException, StaleElementReferenceException))
    def wait_for_load(self) -> bool:
        """Waits for the detail page to fully load."""
        # Original logic from crawler.wait_for_detail_page_load
        if config.DEBUG: logger.debug("Waiting for detail page to load...")
        try:
            # 상세 페이지의 특정 요소가 나타날 때까지 대기합니다.
            # 예: 물건종류 span (config.DETAIL_PAGE_LOAD_INDICATOR_ID)
            # 또는 사진 컨테이너 (self.photo_container_selector)
            # 또는 특정 테이블 ID (config.DETAIL_PAGE_INFO_TABLE_ID)
            # 여기서는 config.DETAIL_PAGE_LOAD_INDICATOR_ID 를 사용합니다.
            self.wait.until(EC.presence_of_element_located((By.ID, config.DETAIL_PAGE_LOAD_INDICATOR_ID)))
            # 추가적으로, 페이지 제목이나 URL 변경을 확인할 수도 있습니다.
            # 예를 들어, 특정 URL fragment를 포함하는지 확인
            # self.wait.until(lambda d: "expected_url_part" in d.current_url)
            if config.DEBUG: logger.debug(f"Detail page indicator '{config.DETAIL_PAGE_LOAD_INDICATOR_ID}' found. Page assumed loaded.")
            
            # 모달 오버레이가 있다면 사라질 때까지 대기 (옵션, 페이지 로드 후 나타나는 경우가 있음)
            try:
                WebDriverWait(self.driver, config.MODAL_VISIBILITY_TIMEOUT_SECONDS).until(
                    EC.invisibility_of_element_located((By.CSS_SELECTOR, self.modal_overlay_selector))
                )
                if config.DEBUG: logger.debug("Modal overlay (if any) became invisible after detail page load.")
            except TimeoutException:
                logger.debug("Modal overlay did not disappear or was not present after detail page load (timeout).")
            except Exception as e_modal:
                logger.warning(f"Error while waiting for modal invisibility on detail page: {e_modal}", exc_info=True)

            return True
        except TimeoutException:
            logger.error("Timeout waiting for detail page load indicator.")
            self._debug_save_page_source('detail_page_load_timeout.html') # _debug_save_page_source 사용
            return False
        except Exception as e:
            logger.error(f"Error waiting for detail page load: {e}", exc_info=True)
            self._debug_save_page_source('detail_page_load_error.html') # _debug_save_page_source 사용
            return False

    def load_all_photos_on_page(self, case_no_for_log: str, item_no_for_log: str) -> list[dict]:
        """
        상세 페이지의 모든 사진(관련사진, 위치도 등)을 수집합니다.
        Base64 인코딩된 이미지와 외부 URL 이미지를 모두 처리합니다.
        사진 개수를 파악하고, '다음' 버튼을 클릭하며 모든 사진을 수집합니다.

        Args:
            case_no_for_log: 로깅 및 파일명에 사용될 사건번호 또는 전체 경매번호.
            item_no_for_log: 로깅 및 파일명에 사용될 물건번호.

        Returns:
            수집 및 처리된 사진 정보 딕셔너리의 리스트.
            각 딕셔너리는 'path', 'original_src', 'type', 'index' 등의 키를 가질 수 있습니다.
        """
        self.item_no_for_log = item_no_for_log
        all_collected_image_srcs = set()
        
        logger_name = getattr(self.logger, 'name', 'crawling.page_objects')
        local_logger = logging.getLogger(logger_name)

        photo_list_ul_id = getattr(config, 'DETAIL_PAGE_PHOTO_LIST_UL_ID', None)
        photo_text_count_xpath = getattr(config, 'PHOTO_TEXT_COUNT_XPATH', None)
        next_button_selector = getattr(config, 'PHOTO_NEXT_BUTTON_SELECTOR', None)
        # initial_visible_photos = getattr(config, 'INITIAL_VISIBLE_PHOTOS', 5) # 현재 로직에서 직접 사용 빈도 낮음
        short_wait_time = max(1, config.DEFAULT_WAIT_TIME // 3)

        local_logger.debug(f"PHOTO_DEBUG ([{case_no_for_log}-{item_no_for_log}]): ENTERING load_all_photos_on_page.")
        local_logger.debug(f"PHOTO_DEBUG ([{case_no_for_log}-{item_no_for_log}]): Using: UL_ID='{photo_list_ul_id}', Count_XPath='{photo_text_count_xpath}', Next_Btn_CSS='{next_button_selector}'")

        if not photo_list_ul_id:
            local_logger.error(f"PHOTO_ERROR ([{case_no_for_log}-{item_no_for_log}]): DETAIL_PAGE_PHOTO_LIST_UL_ID is not configured.")
            return []

        expected_photo_count_total = 0
        try:
            # --- 1. 사진 개수 파악 ---
            if photo_text_count_xpath:
                try:
                    count_elements = WebDriverWait(self.driver, short_wait_time).until(
                        EC.presence_of_all_elements_located((By.XPATH, photo_text_count_xpath))
                    )
                    photo_count_texts = []
                    for elem in count_elements:
                        try:
                            text = elem.text.strip()
                            if text: photo_count_texts.append(text)
                            count_match = re.search(r'\\((\\d+)\\)', text)
                            if count_match:
                                expected_photo_count_total += int(count_match.group(1))
                        except StaleElementReferenceException:
                            local_logger.warning(f"PHOTO_DEBUG ([{case_no_for_log}-{item_no_for_log}]): Stale element in photo count.")
                        except Exception as e_parse_text: # 개별 텍스트 파싱 오류
                             local_logger.warning(f"PHOTO_DEBUG ([{case_no_for_log}-{item_no_for_log}]): Error parsing count text '{text}': {e_parse_text}")
                    local_logger.debug(f"PHOTO_DEBUG ([{case_no_for_log}-{item_no_for_log}]): Photo count texts: {photo_count_texts}. Total expected: {expected_photo_count_total}")
                except TimeoutException:
                    local_logger.warning(f"PHOTO_DEBUG ([{case_no_for_log}-{item_no_for_log}]): Timeout for photo count elements (XPath: {photo_text_count_xpath})")
                except Exception as e_count_main: # 사진 개수 파악 로직의 다른 예외
                    local_logger.error(f"PHOTO_ERROR ([{case_no_for_log}-{item_no_for_log}]): Error getting photo count: {e_count_main}", exc_info=config.DEBUG)
            else:
                local_logger.warning(f"PHOTO_DEBUG ([{case_no_for_log}-{item_no_for_log}]): PHOTO_TEXT_COUNT_XPATH not configured. Count unknown.")

            # --- 2. 초기 이미지 스캔 ---
            local_logger.debug(f"PHOTO_DEBUG ([{case_no_for_log}-{item_no_for_log}]): Waiting for photo list UL (ID: {photo_list_ul_id})...")
            photo_list_ul = WebDriverWait(self.driver, config.DEFAULT_WAIT_TIME).until(
                EC.presence_of_element_located((By.ID, photo_list_ul_id))
            )
            
            initial_srcs_found_count = 0
            for scan_attempt in range(2): # 최대 2번 스캔
                current_lis_in_ul = photo_list_ul.find_elements(By.XPATH, './/li//img')
                newly_found_this_scan = 0
                for img_element in current_lis_in_ul:
                    try:
                        src = img_element.get_attribute('src')
                        if src and src.startswith('data:image') and src not in all_collected_image_srcs:
                            all_collected_image_srcs.add(src)
                            newly_found_this_scan += 1
                    except StaleElementReferenceException:
                        local_logger.warning(f"PHOTO_DEBUG ([{case_no_for_log}-{item_no_for_log}]): Stale <img> in initial scan {scan_attempt + 1}.")
                        break 
                initial_srcs_found_count += newly_found_this_scan
                if newly_found_this_scan == 0 and initial_srcs_found_count > 0 : 
                    break
                if scan_attempt < 1: time.sleep(0.5) 

            local_logger.debug(f"PHOTO_DEBUG ([{case_no_for_log}-{item_no_for_log}]): Initial scan collected {initial_srcs_found_count} new. Total unique: {len(all_collected_image_srcs)}.")

            # --- 3. \"다음\" 버튼 클릭 로직 ---
            clicked_next_at_least_once = False
            if next_button_selector:
                max_clicks = 25 
                # local_logger.debug(f"PHOTO_DEBUG ([{case_no_for_log}-{item_no_for_log}]): Entering 'next' button loop. Max clicks: {max_clicks}")

                for click_count in range(max_clicks):
                    if expected_photo_count_total > 0 and len(all_collected_image_srcs) >= expected_photo_count_total:
                        # local_logger.debug(f"PHOTO_DEBUG ([{case_no_for_log}-{item_no_for_log}]): Collected all expected photos. Stopping 'next' clicks.")
                        break
                    
                    next_btn_element = None
                    try: # next_btn_element 찾는 과정부터 click 까지 포함하는 try 블록
                        next_btn_element = WebDriverWait(self.driver, short_wait_time).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, next_button_selector))
                        )
                        if not (next_btn_element.is_displayed() and next_btn_element.is_enabled()):
                            local_logger.debug(f"PHOTO_DEBUG ([{case_no_for_log}-{item_no_for_log}]): 'Next' button not interactable (click {click_count + 1}).")
                            break
                        
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", next_btn_element)
                        time.sleep(0.2) 
                        
                        try:
                            next_btn_element.click() 
                            # local_logger.debug(f"PHOTO_DEBUG ([{case_no_for_log}-{item_no_for_log}]): Clicked 'next' (std, attempt {click_count + 1}).")
                        except ElementClickInterceptedException:
                            local_logger.warning(f"PHOTO_DEBUG ([{case_no_for_log}-{item_no_for_log}]): 'Next' click intercepted (attempt {click_count + 1}). Retrying with JS.")
                            self.driver.execute_script("arguments[0].click();", next_btn_element)
                            local_logger.debug(f"PHOTO_DEBUG ([{case_no_for_log}-{item_no_for_log}]): Clicked 'next' (JS, attempt {click_count + 1}).")
                        
                        clicked_next_at_least_once = True
                        time.sleep(config.PHOTO_LOAD_DELAY) 

                        # 새 이미지 스캔 (StaleElement 예외 처리를 위해 try-except 추가)
                        try:
                            current_photo_list_ul = self.driver.find_element(By.ID, photo_list_ul_id) 
                            current_imgs_after_click = current_photo_list_ul.find_elements(By.XPATH, './/li//img')
                        except (NoSuchElementException, StaleElementReferenceException) as e_refind_ul:
                            local_logger.warning(f"PHOTO_DEBUG ([{case_no_for_log}-{item_no_for_log}]): Error finding UL after click {click_count +1}: {e_refind_ul}. Re-locating.")
                            try: # UL 재탐색
                                current_photo_list_ul = WebDriverWait(self.driver, short_wait_time).until(EC.presence_of_element_located((By.ID, photo_list_ul_id)))
                                current_imgs_after_click = current_photo_list_ul.find_elements(By.XPATH, './/li//img')
                            except Exception as e_relocate_fatal:
                                local_logger.error(f"PHOTO_ERROR ([{case_no_for_log}-{item_no_for_log}]): Failed to re-locate UL: {e_relocate_fatal}. Breaking loop.")
                                break # 다음 버튼 루프 중단
                        
                        newly_found_this_iteration = 0
                        for img_element in current_imgs_after_click: # current_imgs_after_click가 정의되지 않았을 수 있음 -> 위에서 break 처리
                            try:
                                src = img_element.get_attribute('src')
                                if src and src.startswith('data:image') and src not in all_collected_image_srcs:
                                    all_collected_image_srcs.add(src)
                                    newly_found_this_iteration += 1
                            except StaleElementReferenceException:
                                local_logger.warning(f"PHOTO_DEBUG ([{case_no_for_log}-{item_no_for_log}]): Stale <img> in 'next' loop after click {click_count + 1}.")
                        
                        local_logger.debug(f"PHOTO_DEBUG ([{case_no_for_log}-{item_no_for_log}]): After click {click_count + 1}, found {newly_found_this_iteration} new. Total unique: {len(all_collected_image_srcs)}.")
                        if newly_found_this_iteration == 0 and clicked_next_at_least_once:
                            local_logger.debug(f"PHOTO_DEBUG ([{case_no_for_log}-{item_no_for_log}]): No new images after click {click_count + 1}, breaking.")
                            break
                    
                    except TimeoutException: # next_btn_element를 기다리는 것에 대한 Timeout
                        local_logger.debug(f"PHOTO_DEBUG ([{case_no_for_log}-{item_no_for_log}]): 'Next' button timed out or not clickable (attempt {click_count + 1}).")
                        break 
                    except Exception as e_next_loop: # next_btn_element 찾기 또는 클릭 로직 내 다른 예외
                        local_logger.error(f"PHOTO_ERROR ([{case_no_for_log}-{item_no_for_log}]): Error in 'next' loop (attempt {click_count + 1}): {e_next_loop}", exc_info=config.DEBUG)
                        self._debug_save_page_source(f"_{case_no_for_log}_{item_no_for_log}_photo_error_next_loop_{click_count}.html")
                        break
            else:
                local_logger.debug(f"PHOTO_DEBUG ([{case_no_for_log}-{item_no_for_log}]): No 'next' button selector. Skipping 'next' clicks.")

        except Exception as e_main_collection_logic: # 사진 수집 로직 전체를 감싸는 try-except
            local_logger.error(f"PHOTO_ERROR ([{case_no_for_log}-{item_no_for_log}]): Major error in photo collection logic: {e_main_collection_logic}", exc_info=config.DEBUG)
            self._debug_save_page_source(f"_{case_no_for_log}_{item_no_for_log}_photo_major_error.html")
        
        # --- 최종 처리 및 반환 ---
        final_collected_count = len(all_collected_image_srcs)
        local_logger.info(f"PHOTO_INFO ([{case_no_for_log}-{item_no_for_log}]): Collection END. Expected: {expected_photo_count_total if expected_photo_count_total > 0 else 'Unknown'}, Got: {final_collected_count} unique SRCs.")

        if not all_collected_image_srcs:
            return []
            
        processed_photo_objects = []
        try:
            processed_photo_objects = self._process_collected_image_sources(
                image_sources=sorted(list(all_collected_image_srcs)),
                auction_id_for_filename=case_no_for_log, 
                item_no_for_filename=item_no_for_log,
                save_dir=config.IMAGE_STORAGE_PATH
            )
        except Exception as e_process_src: # _process_collected_image_sources 호출 자체의 오류
            local_logger.error(f"PHOTO_ERROR ([{case_no_for_log}-{item_no_for_log}]): Error calling _process_collected_image_sources: {e_process_src}", exc_info=config.DEBUG)
            # 오류 발생 시 빈 리스트 반환
            processed_photo_objects = [] # 이 부분을 추가하여 오류 시에도 변수가 정의되도록 함

        local_logger.debug(f"PHOTO_DEBUG ([{case_no_for_log}-{item_no_for_log}]): Returning {len(processed_photo_objects)} processed photo objects.")
        return processed_photo_objects

    def _process_collected_image_sources(self, image_sources: list[str], auction_id_for_filename: str, item_no_for_filename: str, save_dir: str) -> list[dict]:
        """
        수집된 이미지 소스(base64, URL 등)를 처리하여 로컬에 저장하거나 URL을 그대로 사용하고,
        각 이미지에 대한 상세 정보(경로, 원본 src, 타입 등)를 담은 딕셔너리의 리스트를 반환합니다.
        """
        logger_name = getattr(self.logger, 'name', 'crawling.page_objects')
        local_logger = logging.getLogger(logger_name)

        local_logger.debug(f"PHOTO_PROCESS ([{auction_id_for_filename}-{item_no_for_filename}]): Processing {len(image_sources)} image sources.")
        processed_results = []
        if not image_sources:
            return []
        
        os.makedirs(save_dir, exist_ok=True)

        for idx, src_data in enumerate(image_sources):
            photo_info_dict = {
                'original_src': src_data,
                'path': '', 
                'type': 'unknown',
                'index': idx,
                'error': None
            }
            try:
                if src_data.startswith('data:image'):
                    photo_info_dict['type'] = 'base64_data'
                    header, encoded_data = src_data.split(',', 1)
                    mime_match = re.match(r'data:image/(?P<ext>[a-zA-Z0-9.+]+);base64', header)
                    ext = mime_match.group('ext').split('+')[0] if mime_match else 'png'
                    
                    image_data_bytes = base64.b64decode(encoded_data)
                    
                    # auction_id_for_filename이 "사건번호-물건번호" 형태 (예: "2024타경109686-1")라고 가정합니다.
                    safe_auction_id_part = "".join(c for c in auction_id_for_filename if c.isalnum() or c in ('-', '_'))
                    # item_no_for_filename은 파일명에 직접 사용하지 않고, auction_id_for_filename에 이미 포함된 것으로 간주합니다.
                    # 법원명 플레이스홀더 - 제거됨
                    # safe_court_placeholder = "UnknownCourt"
                    
                    # 새로운 파일 이름 형식: "사건번호-물건번호_인덱스.확장자"
                    image_filename = f"{safe_auction_id_part}_{idx}.{ext}"
                    image_filepath_absolute = os.path.join(save_dir, image_filename)
                    
                    with open(image_filepath_absolute, 'wb') as img_file:
                        img_file.write(image_data_bytes)
                    
                    try:
                        photo_info_dict['path'] = os.path.relpath(image_filepath_absolute, config.PROJECT_ROOT).replace('\\', '/')
                    except ValueError: 
                        photo_info_dict['path'] = image_filepath_absolute.replace('\\', '/')
                    # local_logger.debug(f"PHOTO_PROCESS ([{auction_id_for_filename}-{item_no_for_filename}]): Saved base64 image {idx} to {photo_info_dict['path']}")

                elif src_data.startswith('http'):
                    photo_info_dict['type'] = 'http_url'
                    photo_info_dict['path'] = src_data
                    local_logger.debug(f"PHOTO_PROCESS ([{auction_id_for_filename}-{item_no_for_filename}]): Detected http URL for image {idx}: {src_data}")
                
                elif src_data.startswith('blob:http'):
                    photo_info_dict['type'] = 'blob_url'
                    photo_info_dict['path'] = src_data
                    local_logger.warning(f"PHOTO_PROCESS ([{auction_id_for_filename}-{item_no_for_filename}]): Blob URL for image {idx}: {src_data}. May not be usable.")
                
                else:
                    photo_info_dict['type'] = 'unknown_format'
                    photo_info_dict['path'] = src_data 
                    local_logger.warning(f"PHOTO_PROCESS ([{auction_id_for_filename}-{item_no_for_filename}]): Unhandled src format for image {idx}: {src_data[:100]}...")
            
            except Exception as e_proc_img:
                error_message = f"Error processing image source {idx} ('{src_data[:70]}...'): {e_proc_img}"
                local_logger.error(f"PHOTO_PROCESS_ERROR ([{auction_id_for_filename}-{item_no_for_filename}]): {error_message}", exc_info=config.DEBUG)
                photo_info_dict['error'] = error_message
                if not photo_info_dict['path']: photo_info_dict['path'] = src_data

            processed_results.append(photo_info_dict)
        
        local_logger.debug(f"PHOTO_PROCESS ([{auction_id_for_filename}-{item_no_for_filename}]): Finished. Returning {len(processed_results)} photo data objects.")
        return processed_results

    def get_detail_html(self):
        """Returns the HTML source of the current detail page."""
        return self.driver.page_source

    def parse_details(self, html, auction_no, item_no, photo_data):
        """Parses the detail page HTML."""
        return parse_detail_page(html, auction_no, item_no, photo_data)

    @retry(attempts=2, delay_seconds=1)
    def click_appraisal_report_button(self):
        """Clicks the button to open the appraisal report popup."""
        try:
            appraisal_btn = self.wait.until(EC.element_to_be_clickable((By.ID, self.appraisal_button_id)))
            try:
                WebDriverWait(self.driver, config.MODAL_VISIBILITY_TIMEOUT_SECONDS).until(EC.invisibility_of_element_located((By.CSS_SELECTOR, self.modal_overlay_selector)))
            except Exception:
                logger.debug(f"감정평가서 버튼 클릭 전 오버레이 제거 대기시간 만료")
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", appraisal_btn)
            self.driver.execute_script("arguments[0].click();", appraisal_btn)
            return True
        except Exception as e:
            logger.error(f"감정평가서 버튼 클릭 실패.", exc_info=e)
            return False

    @retry(attempts=2, delay_seconds=2, backoff_factor=1.5, exceptions_to_catch=(TimeoutException, NoSuchElementException, StaleElementReferenceException, Exception)) # requests.get 예외도 포함 가능
    def download_appraisal_pdf_from_popup(self, target_auction_no):
        """Downloads the appraisal PDF from the popup iframe.
        This method encapsulates the logic from the original _download_appraisal_pdf function.
        Returns file_path if successful, None otherwise.
        """
        popup_iframe_locator = (By.ID, self.appraisal_popup_iframe_id)
        inner_iframe_locator = (By.CSS_SELECTOR, self.appraisal_inner_iframe_selector)

        try:
            popup_iframe = self.wait.until(EC.presence_of_element_located(popup_iframe_locator))
            self.driver.switch_to.frame(popup_iframe)

            def pdf_src_is_loaded_in_iframe(driver_instance):
                try:
                    iframe_element = driver_instance.find_element(*inner_iframe_locator)
                    src_attr = iframe_element.get_attribute('src')
                    if src_attr and '.pdf' in src_attr.lower():
                        return src_attr
                except StaleElementReferenceException:
                    iframe_element = driver_instance.find_element(*inner_iframe_locator)
                    src_attr = iframe_element.get_attribute('src')
                    if src_attr and '.pdf' in src_attr.lower():
                        return src_attr
                except NoSuchElementException:
                    return False
                return False

            pdf_src = WebDriverWait(self.driver, config.PDF_SRC_LOAD_TIMEOUT_SECONDS).until(pdf_src_is_loaded_in_iframe)
            if not pdf_src:
                raise Exception(f"({target_auction_no}) nested iframe src PDF URL 확인 실패: 최종 pdf_src가 None입니다.")

            full_pdf_url = urljoin(self.driver.current_url, pdf_src)
            cookies = {c['name']: c['value'] for c in self.driver.get_cookies()}
            headers = {'Referer': self.driver.current_url}
            
            resp = requests.get(full_pdf_url, cookies=cookies, headers=headers, stream=True)
            resp.raise_for_status()
            
            save_dir = config.APPRAISAL_REPORTS_PATH
            os.makedirs(save_dir, exist_ok=True)
            file_path = os.path.join(save_dir, f"{str(target_auction_no)}_감정평가서.pdf")
            
            with open(file_path, 'wb') as fp:
                for chunk in resp.iter_content(chunk_size=8192):
                    fp.write(chunk)
            logger.info(f"({target_auction_no}) 감정평가서 저장 완료: {file_path}")

            # PDF 다운로드 후 내부 iframe 정리 시도
            try:
                # 현재 컨텍스트는 popup_iframe 내부여야 함.
                inner_iframe_element_for_blanking = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located(inner_iframe_locator) # inner_iframe_locator는 이미 정의되어 있음
                )
                if inner_iframe_element_for_blanking:
                    self.driver.execute_script("arguments[0].src = 'about:blank';", inner_iframe_element_for_blanking)
                    if config.DEBUG: logger.debug(f"Set inner PDF iframe src to 'about:blank' for auction {target_auction_no} to help free resources.")
                else: # 만약 inner_iframe_element_for_blanking 이 None이라면 (이론상 발생 안해야 함)
                    if config.DEBUG: logger.debug(f"Inner PDF iframe element not found for blanking for auction {target_auction_no}, though WebDriverWait should have ensured presence.")
            except TimeoutException:
                 if config.DEBUG: logger.warning(f"Timeout finding inner PDF iframe for blanking (src to 'about:blank') for {target_auction_no}. It might have disappeared.", exc_info=True)
            except Exception as e_blank_iframe:
                if config.DEBUG: logger.warning(f"Could not set inner PDF iframe src to 'about:blank' for {target_auction_no}: {e_blank_iframe}", exc_info=True)
            
            return file_path
        except Exception as e_pdf:
            logger.error(f"오류: {target_auction_no} 감정평가서 저장 실패.", exc_info=e_pdf)
            return None
        finally:
            # 이 함수는 PDF 다운로드에만 집중하므로, iframe 해제는 호출자가 담당.
            pass

    @retry(attempts=2, delay_seconds=0.5)
    def switch_to_default_content_from_appraisal_iframe(self):
        """Switches back to the default content from an iframe, typically the appraisal PDF iframe."""
        try:
            self.driver.switch_to.default_content()
            return True
        except Exception:
            logger.warning(f"감정평가서 iframe_context 복원 중 오류 발생", exc_info=True)
            return False

    @retry(attempts=2, delay_seconds=1)
    def close_appraisal_popup(self):
        """Closes the appraisal report popup.
        Returns True if successfully closed, False otherwise.
        """
        self.logger.debug("Attempting to close appraisal popup...")
        try: # 전체 로직을 감싸는 try
            close_btn_locator = (By.CSS_SELECTOR, self.modal_close_button_selector)
            
            # 1. 버튼 찾기 (클릭 가능할 때까지 대기)
            close_btn = None # close_btn 초기화
            try:
                close_btn = WebDriverWait(self.driver, config.MODAL_VISIBILITY_TIMEOUT_SECONDS).until(
                    EC.element_to_be_clickable(close_btn_locator)
                )
            except TimeoutException:
                self.logger.warning("Appraisal popup close button not clickable within timeout.")
                self._debug_save_page_source("appraisal_close_button_not_clickable.html")
                # 버튼이 안보이거나 클릭 불가능하면, popup_iframe_locator 확인
                try:
                    self.driver.find_element(By.ID, self.appraisal_popup_iframe_id)
                    self.logger.info("Appraisal popup iframe is still present when close button not clickable.")
                except NoSuchElementException:
                    self.logger.info("Appraisal popup iframe NOT present when close button not clickable. Popup might be already closed or failed to open.")
                    return True # 아이프레임이 없으면 이미 닫혔거나 문제가 있었던 것으로 간주하고 성공으로 처리
                # 그래도 버튼 못찾으면 False 반환
                return False
            
            # 2. 버튼 클릭
            if close_btn: # 버튼을 찾았으면
                try:
                    self.driver.execute_script("arguments[0].click();", close_btn)
                    self.logger.info("Clicked appraisal popup close button via JS.")
                except Exception as e_click:
                    self.logger.error(f"Error clicking appraisal popup close button: {e_click}", exc_info=True)
                    self._debug_save_page_source("appraisal_close_button_click_error.html")
                    return False
            else: # 버튼을 못찾은 경우 (위에서 이미 처리되었어야 함)
                self.logger.error("Appraisal popup close button was not found, though TimeoutException was not raised. This should not happen.")
                return False

            # 3. 팝업 사라짐 확인 (iframe 기준)
            popup_iframe_locator_for_invisibility = (By.ID, self.appraisal_popup_iframe_id)
            try:
                WebDriverWait(self.driver, config.MODAL_VISIBILITY_TIMEOUT_SECONDS).until(
                    EC.invisibility_of_element_located(popup_iframe_locator_for_invisibility)
                )
                self.logger.info("Appraisal popup (iframe) became invisible after close click.")
                return True
            except TimeoutException:
                self.logger.error("Timeout waiting for appraisal popup (iframe) to become invisible after close click.")
                self._debug_save_page_source("appraisal_iframe_still_visible_after_close.html")
                # 추가 확인: iframe이 DOM에서 완전히 사라졌는지 (invisibility는 style만 볼 수 있음)
                try:
                    self.driver.find_element(*popup_iframe_locator_for_invisibility) # * 사용
                    self.logger.warning("Appraisal iframe is still present in DOM after invisibility timeout.")
                    return False # DOM에 남아있으면 실패
                except NoSuchElementException:
                    self.logger.info("Appraisal iframe is no longer in DOM after invisibility timeout. Considered closed.")
                    return True # DOM에서 사라졌으면 성공
        except Exception as e_overall: # 이 함수 전체의 예외 처리
            self.logger.error(f"Overall error in close_appraisal_popup: {e_overall}", exc_info=True)
            self._debug_save_page_source("appraisal_close_overall_error.html")
            return False

    @retry(attempts=2, delay_seconds=1.5, exceptions_to_catch=(NoSuchElementException, ElementClickInterceptedException, TimeoutException))
    def go_back_to_list_page(self, auction_list_page: AuctionListPage, expected_page_number: int | None) -> bool:
        """Clicks the 'back' button and verifies navigation to the auction list page."""
        self.logger.info(f"Attempting to go back to auction list page (expected page: {expected_page_number}).")
        try:
            back_button = self.wait.until(EC.element_to_be_clickable((By.ID, config.BACK_BUTTON_ID)))
            self.driver.execute_script("arguments[0].click();", back_button)
            self.logger.info(f"Clicked 'back' button (ID: {config.BACK_BUTTON_ID}).")
            
            # 목록 페이지 그리드 확인
            # auction_list_page는 AuctionListPage의 인스턴스여야 함
            if isinstance(auction_list_page, AuctionListPage):
                # wait_for_grid가 current_page_expected 인자를 받으므로 전달
                if auction_list_page.wait_for_grid(current_page_expected=expected_page_number, is_retry=True):
                    self.logger.info(f"Successfully navigated back to auction list page and grid for page {expected_page_number} is stable.")
                    return True
                else:
                    self.logger.error(f"Failed to confirm auction list page grid (page {expected_page_number}) after clicking back.")
                    self._debug_save_page_source("go_back_grid_confirmation_failed.html")
                    return False
            else:
                self.logger.error("auction_list_page argument is not an instance of AuctionListPage. Cannot confirm grid.")
                return False # auction_list_page 객체가 잘못되었으므로 실패 처리

        except TimeoutException:
            self.logger.error(f"Timeout waiting for 'back' button (ID: {config.BACK_BUTTON_ID}) to be clickable.")
            self._debug_save_page_source("go_back_button_timeout.html")
            return False
        except NoSuchElementException:
            self.logger.error(f"'Back' button (ID: {config.BACK_BUTTON_ID}) not found.")
            self._debug_save_page_source("go_back_button_not_found.html")
            return False
        except ElementClickInterceptedException:
            self.logger.error(f"'Back' button (ID: {config.BACK_BUTTON_ID}) click intercepted.")
            self._debug_save_page_source("go_back_button_click_intercepted.html")
            # JS 클릭으로 재시도해볼 수 있으나, 현재 @retry 데코레이터가 이미 ElementClickInterceptedException을 처리할 수 있음
            return False # 또는 여기서 직접 JS 클릭 시도 후 결과 반환
        except Exception as e:
            self.logger.error(f"An unexpected error occurred in go_back_to_list_page: {e}", exc_info=True)
            self._debug_save_page_source("go_back_unexpected_error.html")
            return False

    @retry(attempts=3, delay_seconds=2, backoff_factor=1.5, exceptions_to_catch=(TimeoutException, NoSuchElementException))
    def search_auction_by_criteria(self, court_name: str, case_year: str, case_number: str) -> bool:
        """특정 조건으로 경매 검색"""
        try:
            logger.info(f"검색 조건 설정: 법원={court_name}, 연도={case_year}, 사건번호={case_number}")
            
            # 법원 선택
            if court_name and court_name != "전체":
                court_elem = self.wait.until(EC.element_to_be_clickable((By.ID, config.COURT_SELECT_ID)))
                Select(court_elem).select_by_visible_text(court_name)
                logger.debug(f"법원 선택: {court_name}")
            
            # 사건년도 선택
            if case_year:
                year_elem = self.wait.until(EC.element_to_be_clickable((By.ID, config.CASE_YEAR_SELECT_ID)))
                Select(year_elem).select_by_visible_text(case_year)
                logger.debug(f"사건년도 선택: {case_year}")
            
            # 사건번호 입력 (필요한 경우)
            if case_number:
                # 사건번호 입력 필드가 있다면 입력 (config에서 확인 필요)
                case_number_input_id = getattr(config, 'CASE_NUMBER_INPUT_ID', None)
                if case_number_input_id:
                    case_number_elem = self.wait.until(EC.element_to_be_clickable((By.ID, case_number_input_id)))
                    case_number_elem.clear()
                    case_number_elem.send_keys(case_number)
                    logger.debug(f"사건번호 입력: {case_number}")
            
            # 검색 버튼 클릭
            search_btn = self.wait.until(EC.element_to_be_clickable((By.ID, config.SEARCH_BUTTON_ID)))
            self.driver.execute_script("arguments[0].click();", search_btn)
            logger.debug("검색 버튼 클릭")
            
            # 결과 그리드 대기
            if self.wait_for_grid():
                logger.info("검색 완료 및 결과 그리드 로드 확인")
                return True
            else:
                logger.error("검색 후 그리드 로드 실패")
                return False
                
        except Exception as e:
            logger.error(f"검색 중 오류 발생: {e}", exc_info=True)
            return False

    @retry(attempts=3, delay_seconds=2, backoff_factor=1.5, exceptions_to_catch=(TimeoutException, NoSuchElementException))
    def go_to_detail_page_by_item_no(self, item_no: str) -> Optional['AuctionDetailPage']:
        """물건번호로 상세 페이지 이동"""
        try:
            logger.info(f"물건번호 {item_no}으로 상세 페이지 이동 시도")
            
            # 현재 페이지의 모든 아이템 가져오기
            current_page_items = self.get_current_page_items(1)  # 현재 페이지 번호는 1로 가정
            
            # 해당 물건번호 찾기
            target_item = None
            for item in current_page_items:
                if str(item.get('item_no', '')) == str(item_no):
                    target_item = item
                    break
            
            if not target_item:
                logger.error(f"물건번호 {item_no}에 해당하는 경매를 찾을 수 없음")
                return None
            
            # 상세 페이지로 이동
            display_case_text = target_item.get('display_case_text', '')
            item_no_text = str(item_no)
            full_auction_no = target_item.get('auction_no', '')
            case_year = target_item.get('case_year', '')
            case_number = target_item.get('case_number', '')
            item_index = target_item.get('item_index_on_page', 0)
            
            if self.click_item_detail_link(
                display_case_text, item_no_text, full_auction_no, 
                case_year, case_number, item_index
            ):
                # AuctionDetailPage 생성 및 반환
                detail_page = AuctionDetailPage(self.driver, self.wait)
                if detail_page.wait_for_detail_page_load():
                    logger.info(f"상세 페이지 로드 완료: {full_auction_no}")
                    return detail_page
                else:
                    logger.error("상세 페이지 로드 실패")
                    return None
            else:
                logger.error("상세 페이지 링크 클릭 실패")
                return None
                
        except Exception as e:
            logger.error(f"상세 페이지 이동 중 오류: {e}", exc_info=True)
            return None