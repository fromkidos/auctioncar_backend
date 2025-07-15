import os

# --- General Configuration ---
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
ITEMS_PER_PAGE = 40  # Desired items per page
DEBUG_DIR = 'debug'
DEFAULT_WAIT_TIME = 30  # Default wait time in seconds
SHORT_WAIT_TIME = 5  # For quick checks

# --- Filter Texts & URLs ---
FILTER_USE_LARGE = '차량및운송장비'
MIDDLE_CATEGORIES_TO_CRAWL = ['차량', '중기', '선박', '항공기', '이륜차']
FILTER_SALE_RESULT_SOLD = '전체'  # 매각결과 필터 값

URL_FILTER = (
    'https://www.courtauction.go.kr/pgj/index.on'
    '?w2xPath=/pgj/ui/pgj100/PGJ158M00.xml'
)


HOST = os.getenv('HOST', "192.168.0.10")
PORT = os.getenv('PORT', "4000")

# --- NestJS API Configuration ---
# URL을 직접 문자열 포맷팅으로 구성
NESTJS_API_URL = f"http://{HOST}:{PORT}/internal/auctions/result"
NESTJS_API_KEY = os.getenv("INTERNAL_API_KEY")

# --- Element IDs & Selectors ---
# Filter Form
SEARCH_FORM_TABLE_ID = 'mf_wfm_mainFrame_wq_uuid_327'
LARGE_CAT_SELECT_ID = 'mf_wfm_mainFrame_sbx_dspslRsltSrchLclLst'
MIDDLE_CAT_SELECT_ID = 'mf_wfm_mainFrame_sbx_dspslRsltSrchMclLst'
COURT_SELECT_ID = 'mf_wfm_mainFrame_sbx_dspslRsltSrchCortOfc'
SALE_RESULT_SELECT_ID = 'mf_wfm_mainFrame_sbx_dspslRsltLst'
SEARCH_BUTTON_ID = 'mf_wfm_mainFrame_btn_dspslRsltSrch'

# Results / Pagination
RESULTS_GRID_SELECTOR = 'div#mf_wfm_mainFrame_grd_gdsDtlSrchResult'
RESULTS_GRID_BODY_ID = 'mf_wfm_mainFrame_grd_gdsDtlSrchResult_body_tbody'
PAGE_SIZE_SELECT_ID = 'mf_wfm_mainFrame_sbx_pageSize'
TOTAL_ITEMS_SPAN_ID = 'mf_wfm_mainFrame_gna_srhcTitle_1_spn_srchCtt'
PAGINATION_DIV_ID = 'mf_wfm_mainFrame_grp_rletPageInfo' 