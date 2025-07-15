#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Configuration file for the Court Auction Car Updater.
Contains constants, file paths, URLs, and element selectors.
"""
import os

# --- General Configuration ---
# DEBUG = False # 기존 DEBUG 설정은 .env 또는 환경 변수로 관리되도록 주석 처리 또는 삭제 고려
DEBUG = os.getenv('DEBUG', 'True').lower() in ('true', '1', 't') # 환경변수 DEBUG 사용
ITEMS_PER_PAGE = int(os.getenv('ITEMS_PER_PAGE', 40)) # Desired items per page
DEFAULT_WAIT_TIME = int(os.getenv('DEFAULT_WAIT_TIME', 10)) # Default wait time in seconds
MAX_ITEMS_TO_PROCESS = int(os.getenv('MAX_ITEMS_TO_PROCESS', 10)) # Limit detail processing
PHOTO_LOAD_DELAY = float(os.getenv('PHOTO_LOAD_DELAY', 0.5)) # Delay for photo loading

# --- 프로젝트 루트 및 Public 디렉토리 설정 ---
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
PUBLIC_DIR_NAME = os.getenv('PUBLIC_DIR_NAME', "public")

# --- File Paths (프로젝트 루트 기준) ---
# DEBUG_DIR = 'debug_updater' # 기존 상대 경로
DEBUG_DIR = os.path.join(PROJECT_ROOT, os.getenv('DEBUG_DIR_NAME', 'debug_updater_ongoing')) # 프로젝트 루트 하위로 변경 및 환경변수 사용

UPLOADS_BASE_DIR_NAME = os.getenv('UPLOADS_BASE_DIR_NAME', 'uploads')
AUCTION_IMAGES_DIR_NAME = os.getenv('AUCTION_IMAGES_DIR_NAME', 'auction_images')
APPRAISAL_REPORTS_DIR_NAME = os.getenv('APPRAISAL_REPORTS_DIR_NAME', 'appraisal_reports')
LOG_FILE_NAME = os.getenv('LOG_FILE_NAME_ONGOING', "update_ongoing_auctions.log") # 로그 파일명 환경변수화

IMAGE_STORAGE_PATH = os.path.join(PROJECT_ROOT, PUBLIC_DIR_NAME, UPLOADS_BASE_DIR_NAME, AUCTION_IMAGES_DIR_NAME)
APPRAISAL_REPORTS_PATH = os.path.join(PROJECT_ROOT, PUBLIC_DIR_NAME, UPLOADS_BASE_DIR_NAME, APPRAISAL_REPORTS_DIR_NAME)

# --- URLs ---
DEFAULT_BASE_URL = os.getenv('DEFAULT_BASE_URL', "https://www.courtauction.go.kr") # DEFAULT_BASE_URL 정의

# URL for "기일별 검색" page (Ongoing auctions filter)
URL_ONGOING_FILTER = (
    'https://www.courtauction.go.kr/pgj/index.on'
    '?w2xPath=/pgj/ui/pgj100/PGJ154M00.xml'
)

# 검색 결과 페이지 URL (initialize_search 후 변경될 수 있는 URL, 목록으로 간주할 수 있는 부분)
URL_ONGOING_LIST = os.getenv('URL_ONGOING_LIST', DEFAULT_BASE_URL + "/ ನ್ಯಾಯર્થી/목록화면경로") # 실제 경로로 수정 필요
URL_ONGOING_LIST_KEYWORD = os.getenv('URL_ONGOING_LIST_KEYWORD', "SrchList.do") # 예시: 목록 페이지 URL에 자주 포함되는 키워드

# --- Element IDs & Selectors ---

# Filter Form Elements ("자동차·중기검색" - PGJ154M00.xml)
SEARCH_FORM_TABLE_ID = 'mf_wfm_mainFrame_wq_uuid_335'
CASE_YEAR_SELECT_ID = 'mf_wfm_mainFrame_sbx_carTmidCsNo'
COURT_SELECT_ID = 'mf_wfm_mainFrame_sbx_carTmidCortOfc'
SEARCH_BUTTON_ID = 'mf_wfm_mainFrame_btn_srchCarTmid'

# Results List / Pagination Elements
RESULTS_GRID_SELECTOR = 'div#mf_wfm_mainFrame_grd_gdsDtlSrchResult'
RESULTS_GRID_BODY_ID = 'mf_wfm_mainFrame_grd_gdsDtlSrchResult_body_tbody'
PAGE_SIZE_SELECT_ID = 'mf_wfm_mainFrame_sbx_pageSize'
PAGINATION_DIV_ID = 'mf_wfm_mainFrame_pgl_gdsDtlSrchPage'
TOTAL_ITEMS_SPAN_ID = 'mf_wfm_mainFrame_gna_srhcTitle_1_spn_srchCtt'

# 페이지네이션 상세 버튼 선택자 (제공된 HTML 기반)
PAGINATION_FIRST_PAGE_BUTTON_SELECTOR = "button.w2pageList_col_prevPage[title='첫 페이지']"
PAGINATION_PREV_GROUP_BUTTON_SELECTOR = "button.w2pageList_col_prev[title='이전 목록']"
PAGINATION_NEXT_GROUP_BUTTON_SELECTOR = "button.w2pageList_col_next[title='다음 목록']"
PAGINATION_LAST_PAGE_BUTTON_SELECTOR = "button.w2pageList_col_nextPage[title='마지막 페이지']"
PAGINATION_PAGE_NUMBER_LINK_SELECTOR = "a.w2pageList_control_label" # 페이지네이션 div 내부의 페이지 숫자 링크

# Detail Page Elements
DETAIL_PAGE_LOAD_INDICATOR_ID = "mf_wfm_mainFrame_spn_gdsDtlSrchGdsKnd" # '물건종류' span
DETAIL_DOCS_LIST_SELECTOR = "a[onclick*='f_viewDoc']" # Document view links
DETAIL_DATE_HISTORY_TABLE_SELECTOR = "#mf_wfm_mainFrame_grd_dxdyDtsLst_body_tbody" # 기일내역 table rows
DETAIL_SIMILAR_STATS_CONTENT_DIV_ID = "mf_wfm_mainFrame_tac_aroundGdsExm_contents_content1" # 유사매각통계 tab content div
# NEXT_PHOTO_BUTTON_SELECTOR_CSS = "input#mf_wfm_mainFrame_btn_next.btn_cm.bt_next" # 사진 다음 버튼 CSS # 주석 처리 또는 아래와 통합
PHOTO_NEXT_BUTTON_SELECTOR = "input#mf_wfm_mainFrame_btn_next"  # 사진 다음 버튼 CSS 선택자 (ID 기반)
INITIAL_VISIBLE_PHOTOS = int(os.getenv('INITIAL_VISIBLE_PHOTOS', 5)) # Number of initially visible photos
BACK_BUTTON_ID = "mf_wfm_mainFrame_btn_prevBtn" # '이전' button ID

# Selectors for parsing specific detail sections (used within parse_detail_page)
PHOTO_CONTAINER_SELECTOR = "#mf_wfm_mainFrame_wq_uuid_735" # Div containing photo slider
PHOTO_IMG_SELECTOR = "img[id*='img_reltPic']" # Img tags for photos
PHOTO_COUNT_ID_SELECTOR = "#mf_wfm_mainFrame_gen_picTbox_0_tbx_picDvsCdNm" # Element containing photo count text
PHOTO_TEXT_COUNT_XPATH = "//div[@id='mf_wfm_mainFrame_gen_picTbox']/div[contains(@class, 'w2textbox')]" # XPath for all text elements containing photo counts
PHOTO_COUNT_FALLBACK_TEXT = "관련사진" # Fallback text to find photo count

# Header texts used to find sections in detail page parsing
HEADER_BASIC_INFO = "기본내역"
HEADER_CASE_INFO = "사건내역"
HEADER_DATE_HISTORY = "기일내역"
HEADER_ITEM_DETAILS = "목록내역"
HEADER_APPRAISAL = "감정평가요항표"

# Field names used in detail page parsing by label
LABEL_KIND = "물건종류"
LABEL_APPRAISAL_PRICE = "감정평가액"
LABEL_MIN_BID_PRICE = "최저매각가격"
LABEL_BID_METHOD = "입찰방법"
LABEL_SALE_DATE_TIME_LOC = "매각기일"
LABEL_LOCATION_ADDRESS = "소재지"
LABEL_DEPARTMENT = "담당"
LABEL_ITEM_REMARKS = "물건비고"
LABEL_CASE_RECEIVED = "사건접수"
LABEL_AUCTION_START_DATE = "경매개시일"
LABEL_DISTRIBUTION_DUE_DATE = "배당요구종기"
LABEL_CLAIM_AMOUNT = "청구금액"
LABEL_CAR_NAME = "차명"
LABEL_CAR_TYPE = "차종"
LABEL_REG_NUMBER = "등록번호"
LABEL_MODEL_YEAR = "연식"
LABEL_MANUFACTURER = "제조사"
LABEL_FUEL_TYPE = "연료종류"
LABEL_TRANSMISSION = "변속기"
LABEL_ENGINE_TYPE = "원동기형식"
LABEL_APPROVAL_NUMBER = "승인번호"
LABEL_VIN = "차대번호"
LABEL_DISPLACEMENT = "배기량"
LABEL_MILEAGE = "주행거리"
LABEL_STORAGE_LOCATION = "보관장소"

# --- New fields for Case Detail Inquiry ---
# 필드명은 실제 파싱 결과에 따라 정확히 정의해야 합니다.
# FIELDNAME_CASE_DEPARTMENT = '담당계'
# FIELDNAME_DIVIDEND_INFO = '배당요구종기내역'
# Define new constant for storage method
# FIELDNAME_DIVIDEND_STORAGE_METHOD = 'dividend_storage_method'

# --- New debug path for Case Detail Inquiry page ---
# DEBUG = True 일 때 사용
# CASE_DETAIL_INQUIRY_HTML_FILENAME_TEMPLATE = "case_inquiry_{case_no}_{item_no}.html"

# --- URL Prefixes (If identifiable and useful for waiting conditions) ---
# CASE_DETAIL_INQUIRY_PAGE_URL_FRAGMENT = "some_url_part_specific_to_case_inquiry" # 예시

# --- Element IDs and Selectors for crawling ---
DETAIL_PAGE_INFO_TABLE_ID = "mf_wfm_mainFrame_tbl_detailInfo" # 상세 정보 테이블 ID
DETAIL_PAGE_PHOTO_TAB_ID = "mf_wfm_mainFrame_attachimagetab"
DETAIL_PAGE_PHOTO_LIST_UL_ID = "mf_wfm_mainFrame_gen_pic" # 사진 목록 ul ID (수정됨)
DETAIL_PAGE_NEXT_PHOTO_BUTTON_ID = "mf_wfm_mainFrame_btn_next" # 다음 사진 버튼 ID
# DETAIL_PAGE_CASE_DETAIL_INQUIRY_BUTTON_ID = "mf_wfm_mainFrame_btn_moveCsDtl" # 사건상세조회 버튼 ID

# Appraisal report button ID (감정평가서)
APPRAISAL_BUTTON_ID = "mf_wfm_mainFrame_btn_aeeWevl1"

# Base uploads directory (public/uploads)
UPLOADS_BASE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'public', 'uploads'))
# Storage path for appraisal reports (감정평가서)
APPRAISAL_REPORTS_PATH = os.path.join(UPLOADS_BASE_PATH, 'appraisal_reports')

# '사건상세조회' 페이지 관련 ID
# CASE_DETAIL_TAB_CONTENT_BODY_ID = "mf_wfm_mainFrame_tac_srchRsltDvs_contents_content1_body" # 사건내역 탭 내용 div
# CASE_DETAIL_CASE_NUMBER_SPAN_ID = "mf_wfm_mainFrame_spn_csBasDtsCsNo" # 사건상세조회 페이지의 사건번호 span ID
# ... (다른 설정들) ... 

# --- 추가된 설정 (환경 변수에서 로드) ---
# CSS 셀렉터
MODAL_OVERLAY_SELECTOR = os.getenv('MODAL_OVERLAY_SELECTOR', "div.w2modal") # 모달 오버레이
MODAL_CLOSE_BUTTON_SELECTOR = os.getenv('MODAL_CLOSE_BUTTON_SELECTOR', "input.w2window_close") # 모달 닫기 버튼
APPRAISAL_POPUP_IFRAME_ID = os.getenv('APPRAISAL_POPUP_IFRAME_ID', "sbx_iframeTest") # 감정평가서 팝업 iframe ID
APPRAISAL_INNER_IFRAME_SELECTOR = os.getenv('APPRAISAL_INNER_IFRAME_SELECTOR', 'iframe[id^="F"]') # 감정평가서 내부 iframe

# 타임아웃 값 (초 단위)
CRAWLING_TOTAL_TIMEOUT_SECONDS = int(os.getenv('CRAWLING_TOTAL_TIMEOUT_SECONDS', 60 * 3)) # 전체 크롤링 작업 타임아웃
ITEM_PROCESSING_TIMEOUT_SECONDS = int(os.getenv('ITEM_PROCESSING_TIMEOUT_SECONDS', 60 * 3)) # 개별 아이템 처리 타임아웃 (기본 3분)
MODAL_VISIBILITY_TIMEOUT_SECONDS = int(os.getenv('MODAL_VISIBILITY_TIMEOUT_SECONDS', 5)) # 모달 표시/사라짐 대기
PDF_SRC_LOAD_TIMEOUT_SECONDS = int(os.getenv('PDF_SRC_LOAD_TIMEOUT_SECONDS', 10)) # PDF URL 로드 대기 

# UI 액션 후 대기 시간 (페이지 크기 변경 등)
UI_ACTION_DELAY_SECONDS = float(os.getenv('UI_ACTION_DELAY_SECONDS', 1.0)) # 초 단위 

# 오류 발생 시 재시도 전 대기 시간
DELAY_ON_ERROR = float(os.getenv('DELAY_ON_ERROR', 3.0)) # 초 단위

# 페이지 간 이동 시 대기 시간
DELAY_BETWEEN_PAGES = float(os.getenv('DELAY_BETWEEN_PAGES', 1.0)) # 초 단위

# 상세 페이지 제목에 포함될 수 있는 키워드 (목록 페이지와 구분하기 위함)
AUCTION_DETAIL_PAGE_TITLE_KEYWORD = os.getenv('AUCTION_DETAIL_PAGE_TITLE_KEYWORD', "상세") 

# --- 조건부 크롤링 설정 ---
# DB에 데이터가 존재할 때, 특정 필드가 아래 값들 중 하나이면 크롤링 재시도
CONDITIONAL_CRAWL_FIELD_NAME = os.getenv('CONDITIONAL_CRAWL_FIELD_NAME', 'sale_date')
CONDITIONAL_CRAWL_MISSING_VALUES_STR = os.getenv('CONDITIONAL_CRAWL_MISSING_VALUES', "None,,정보 없음,N/A")
# 문자열을 리스트로 변환 (None은 실제 None 객체로 처리 필요)
_values = [val.strip() for val in CONDITIONAL_CRAWL_MISSING_VALUES_STR.split(',')]
CONDITIONAL_CRAWL_MISSING_VALUES = []
for v in _values:
    if v.upper() == 'NONE':
        CONDITIONAL_CRAWL_MISSING_VALUES.append(None)
    else:
        CONDITIONAL_CRAWL_MISSING_VALUES.append(v)

# --- 감정평가요항표 상세 항목 ID ---
# (parsers.py에서 id 뒤의 #은 select_one 사용시 붙여야 함)
APPRAISAL_SUMMARY_IDS = {
    'year_mileage': "mf_wfm_mainFrame_gen_aeeEvlMnpntCtt_0_tbx_aeeEvlMnpntCtt",
    'color': "mf_wfm_mainFrame_gen_aeeEvlMnpntCtt_1_tbx_aeeEvlMnpntCtt",
    'management_status': "mf_wfm_mainFrame_gen_aeeEvlMnpntCtt_2_tbx_aeeEvlMnpntCtt",
    'fuel': "mf_wfm_mainFrame_gen_aeeEvlMnpntCtt_3_tbx_aeeEvlMnpntCtt",
    'inspection_validity': "mf_wfm_mainFrame_gen_aeeEvlMnpntCtt_4_tbx_aeeEvlMnpntCtt",
    'options_etc': "mf_wfm_mainFrame_gen_aeeEvlMnpntCtt_5_tbx_aeeEvlMnpntCtt",
} 

# --- Retry Decorator Settings ---
RETRY_ATTEMPTS = int(os.getenv('RETRY_ATTEMPTS', 3))
RETRY_DELAY = int(os.getenv('RETRY_DELAY', 2)) # seconds
RETRY_BACKOFF_FACTOR = int(os.getenv('RETRY_BACKOFF_FACTOR', 2))
STALENESS_CHECK_TIMEOUT_SECONDS = int(os.getenv('STALENESS_CHECK_TIMEOUT_SECONDS', 5)) # staleness_of 대기 시간
# --- 감정평가서 다운로드 설정 ---
DOWNLOAD_APPRAISAL_PDF = os.getenv('DOWNLOAD_APPRAISAL_PDF', 'True').lower() in ('true', '1', 't') 