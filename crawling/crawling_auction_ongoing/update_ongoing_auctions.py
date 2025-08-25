#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Main script to update car auctions.
Orchestrates the process using helper modules and improved structure.
"""
import os
import time
import traceback
import base64
import re
import datetime
import requests
from urllib.parse import urljoin
import signal

from dotenv import load_dotenv
import logging.config

from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException,
    ElementClickInterceptedException, StaleElementReferenceException
)
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

from .utils import retry, handle_unexpected_alert

# --- 환경변수 로드 (한 번만) ---
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path=dotenv_path)

# --- 설정 & 페이지 객체 ---
from . import config
from .driver_utils import initialize_driver
from .page_objects import AuctionListPage, AuctionDetailPage

# --- DB 핸들러 ---
from .. import db_manager
from ..db_manager import (
    get_db_connection, insert_auction_base_info, insert_auction_date_history,
    insert_photo_urls, insert_auction_detail_info, insert_similar_sale,
    get_auction_base_by_auction_no, delete_rows_by_auction_no,
    insert_or_update_appraisal_summary
)

# --- 로거 설정 통합 ---
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "std": {"format": "%(asctime)s - %(levelname)s - %(name)s - %(funcName)s:%(lineno)d - %(message)s"}
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "std",
            "level": "DEBUG" if config.DEBUG else "INFO",
            "stream": "ext://sys.stdout"
        },
        "file": {
            "class": "logging.FileHandler",
            "formatter": "std",
            "level": "DEBUG" if config.DEBUG else "INFO",
            "filename": os.path.join(config.DEBUG_DIR, config.LOG_FILE_NAME),
            "encoding": "utf-8",
            "mode": "a"
        }
    },
    "loggers": {
        "selenium.webdriver.remote.remote_connection": {
            "level": "INFO",
            "handlers": ["console", "file"],
            "propagate": False
        },
        "urllib3.connectionpool": {
            "level": "INFO",
            "handlers": ["console", "file"],
            "propagate": False
        }
    },
    "root": {
        "level": "DEBUG" if config.DEBUG else "INFO",
        "handlers": ["console", "file"]
    }
}
os.makedirs(config.DEBUG_DIR, exist_ok=True)
logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)


# --- 전역 DB 연결 참조 변수 및 시그널 핸들링 ---
_current_db_connection_for_signal_handler = None

def signal_handler(signum, frame):
    global _current_db_connection_for_signal_handler
    logger.warning(f"시그널 {signum} 수신. 프로그램을 종료합니다...")
    if _current_db_connection_for_signal_handler:
        try:
            logger.info("DB 연결에 대한 롤백 및 닫기 시도...")
            _current_db_connection_for_signal_handler.rollback() # 명시적 롤백
            _current_db_connection_for_signal_handler.close()
            logger.info("DB 롤백 및 연결 닫기 완료.")
        except Exception as e_signal_db:
            logger.error(f"시그널 핸들러에서 DB 정리 중 오류: {e_signal_db}")
    # 프로그램 즉시 종료 (다른 정리 작업이 필요하다면 여기서 추가)
    exit(1) # 또는 os._exit(1) for immediate exit without further cleanup


# --- 날짜 변환 헬퍼 함수 ---
def parse_date_string_to_datetime(date_str: str, formats: list[str] = ["%Y.%m.%d %H:%M", "%Y-%m-%d %H:%M", "%Y.%m.%d.", "%Y.%m.%d", "%Y-%m-%d"]):
    if not date_str or not isinstance(date_str, str) or date_str.strip().upper() == 'N/A':
        return None
    # 공백 및 불필요한 문자 제거 (예: "2023.01.01.")
    cleaned_date_str = date_str.strip().rstrip('.')
    for fmt in formats:
        try:
            return datetime.datetime.strptime(cleaned_date_str, fmt)
        except ValueError:
            continue
    logger.warning(f"날짜 문자열 파싱 실패: '{date_str}'. 지원하는 형식: {formats} 시도된 값: '{cleaned_date_str}'")
    return None


# --- Deadline 타임아웃 헬퍼 ---
class Deadline:
    def __init__(self, timeout_sec: float):
        self.deadline = time.monotonic() + timeout_sec
    def expired(self) -> bool:
        return time.monotonic() > self.deadline


# --- 예외 정의 ---
class DetailClickError(Exception): pass
class DetailLoadError(Exception): pass


# --- 세부 처리 유틸리티 함수들 ---
def _click_and_wait_detail(auction_list_page, detail_page, display_case_text, item_no, full_auction_no, year, number):
    if not auction_list_page.click_item_detail_link(
        display_case_text=display_case_text,
        item_no_text=item_no,
        full_auction_no_for_onclick_fallback=full_auction_no,
        case_year_for_onclick_fallback=year,
        case_number_part_for_onclick_fallback=number
    ):
        raise DetailClickError("링크 클릭 실패")
    if not detail_page.wait_for_load():
        raise DetailLoadError("상세 페이지 로드 실패")
    return detail_page

def _collect_photos(detail_page: AuctionDetailPage, full_auction_no: str, case_no: str, item_no: str) -> list[dict]:
    """상세 페이지에서 모든 사진 정보를 수집하고 처리합니다.

    Args:
        detail_page: AuctionDetailPage 객체.
        full_auction_no: 전체 경매 번호 (예: "2023-12345-001").
        case_no: 사건 번호 (예: "2023타경12345").
        item_no: 물건 번호 (예: "1").

    Returns:
        처리된 사진 정보 딕셔너리의 리스트.
        각 딕셔너리는 'path' (저장 경로 또는 URL)와 'index' 키를 가집니다.
        예: [{'path': 'public/uploads/auction_images/...jpg', 'index': 0}, ...]
    """
    logger.debug(f"_collect_photos 호출됨: {full_auction_no=}, {case_no=}, {item_no=}")
    photo_objects_from_page_object = detail_page.load_all_photos_on_page(case_no_for_log=full_auction_no, item_no_for_log=item_no)
    
    logger.debug(f"""[{full_auction_no}-{item_no}] load_all_photos_on_page 반환값 ({len(photo_objects_from_page_object)}개):
                 {str(photo_objects_from_page_object)[:500]}...""")

    processed_photo_info_list = []
    public_dir_name = getattr(config, 'PUBLIC_DIR_NAME', 'public')
    image_storage_base_path = config.IMAGE_STORAGE_PATH # 예: /abs/path/to/project/public/uploads/auction_images

    for idx, photo_obj in enumerate(photo_objects_from_page_object):
        try:
            path_from_page_object = photo_obj.get('path')
            image_type_from_page_object = photo_obj.get('type') # page_objects.py에서 설정한 타입 가져오기

            if not path_from_page_object:
                logger.warning(f"[{full_auction_no}-{item_no}] Photo object {idx}에 'path'가 없습니다: {photo_obj}")
                continue

            current_photo_path_for_db = path_from_page_object # 기본값은 전체 경로

            if image_type_from_page_object == 'base64_data':
                # 이미지가 로컬에 파일로 저장된 경우(type: 'base64_data'), 파일명만 추출
                current_photo_path_for_db = os.path.basename(path_from_page_object)
                # logger.debug(f"[{full_auction_no}-{item_no}] DB에 저장할 경로 (파일명만): {current_photo_path_for_db} (원본 전체 경로: {path_from_page_object})")
            elif image_type_from_page_object == 'http_url':
                logger.debug(f"[{full_auction_no}-{item_no}] DB에 저장할 경로 (HTTP URL): {current_photo_path_for_db}")
            elif image_type_from_page_object == 'blob_url':
                logger.warning(f"[{full_auction_no}-{item_no}] DB에 저장할 경로 (Blob URL): {current_photo_path_for_db}. 직접 사용이 어려울 수 있습니다.")
            # 다른 타입(예: 'unknown_format'이면서 URL이 아닌 경우 등)은 기본적으로 전체 경로 유지
            # page_objects.py에서 'base64_data' 외에는 URL이거나 원본 src를 그대로 path로 반환하므로, 여기서는 파일명 추출 불필요
            else:
                 logger.debug(f"[{full_auction_no}-{item_no}] DB에 저장할 경로 (타입: {image_type_from_page_object}, 경로: {current_photo_path_for_db})")

            if current_photo_path_for_db:
                processed_photo_info_list.append({'path': current_photo_path_for_db, 'index': photo_obj.get('index', idx)})
            
        except Exception as e_photo_proc: 
            logger.error(f"[{full_auction_no}-{item_no}] 사진 정보 최종 처리 중 오류 (인덱스 {idx}, 객체: {str(photo_obj)[:100]}...): {e_photo_proc}", exc_info=config.DEBUG)
            path_from_po_fallback = photo_obj.get('path')
            if path_from_po_fallback:
                 processed_photo_info_list.append({'path': os.path.basename(path_from_po_fallback) if photo_obj.get('type') == 'base64_data' else path_from_po_fallback, 
                                                 'index': photo_obj.get('index', idx), 
                                                 'error_during_final_processing': True})
                 logger.info(f"[{full_auction_no}-{item_no}] 사진 최종 처리 중 오류 발생, page_objects에서 제공한 경로 사용 (필요시 파일명만): {processed_photo_info_list[-1]['path']}")

    logger.debug(f"[{full_auction_no}-{item_no}] _collect_photos 완료. 처리된 사진 개수: {len(processed_photo_info_list)}")
    return processed_photo_info_list

def _download_pdf(detail_page, auction_no):
    if not detail_page.click_appraisal_report_button():
        return None
    path = detail_page.download_appraisal_pdf_from_popup(auction_no)
    
    # iframe 컨텍스트에서 기본 컨텐츠로 전환
    if not detail_page.switch_to_default_content_from_appraisal_iframe():
        logger.warning(f"[{auction_no}] 감정평가서 iframe에서 기본 컨텐츠로 전환 실패. 팝업 닫기를 시도하지만 문제가 발생할 수 있음.")
        # 전환 실패 시에도 팝업 닫기는 시도해볼 수 있음

    # 팝업 닫기 시도 및 결과 로깅
    if detail_page.close_appraisal_popup():
        logger.info(f"[{auction_no}] 감정평가서 팝업 닫기 성공.")
    else:
        logger.warning(f"[{auction_no}] 감정평가서 팝업 닫기 실패. 후속 작업에 영향이 있을 수 있음.")
        # 여기서 추가적인 복구 로직 고려 가능 (예: ESC 키 전송, 페이지 새로고침 등)
        # 하지만 현재는 경고만 남기고 진행
    
    return path


PAGE_LOAD_CONFIRM_TIMEOUT = config.DEFAULT_WAIT_TIME # 페이지 이동 후 그리드 확인 대기 시간 (기본값 사용)

@retry(attempts=config.RETRY_ATTEMPTS, delay_seconds=config.RETRY_DELAY, backoff_factor=config.RETRY_BACKOFF_FACTOR, exceptions_to_catch=(TimeoutException, StaleElementReferenceException, DetailClickError, DetailLoadError, ConnectionResetError, requests.exceptions.RequestException)) # 네트워크 관련 예외 추가
def process_single_auction_item(driver, wait, auction_list_page: AuctionListPage, base_info: dict):
    target = base_info['auction_no']
    item_original_page_number = base_info.get('_current_page_for_item', 1) # 아이템이 원래 있던 페이지 번호
    item_deadline = Deadline(config.ITEM_PROCESSING_TIMEOUT_SECONDS)
    detail_page = AuctionDetailPage(driver, wait)

    display_case_text = base_info.get('display_case_no', '') # 상세 페이지 클릭용
    full_auction_no = base_info['auction_no'] # "2023타경12345-1" 형식
    case_no_part = base_info.get('display_case_no', '') # "2023타경12345" 형식 (항목 파싱 시 생성)
    item_no_part = base_info.get('item_no', '') # "1" 형식 (항목 파싱 시 생성)
    item_index_on_page = base_info.get('_item_index_on_page', -1) # 페이지 내 아이템 인덱스 (0-based)
    
    case_year_str = "" 
    case_number_str = "" 

    logger.info(f"[{target}] 사건번호 파싱 시도. court_case_no: '{case_no_part}'")
    if case_no_part and isinstance(case_no_part, str):
        match = re.match(r"(\d{4})타경(\d+)", case_no_part)
        if match:
            case_year_str = match.group(1)
            case_number_str = match.group(2)
            logger.info(f"[{target}] 사건번호 파싱 성공: case_year_str='{case_year_str}', case_number_str='{case_number_str}'")
        else:
            logger.warning(f"[{target}] 사건번호 형식 ('{case_no_part}')이 정규식과 불일치. case_year, case_number 추출 실패.")
    else:
        logger.warning(f"[{target}] court_case_no ('{case_no_part}')가 유효하지 않아 사건번호 파싱 불가.")

    if not case_year_str:
        logger.error(f"[{target}] DB 저장을 위한 case_year가 확정되지 않았습니다. (파싱된 값: '{case_year_str}'). 이 아이템 처리를 중단합니다.")
        raise ValueError(f"[{target}] case_year 파싱 실패로 DB 저장 불가.")

    try:
        logger.info(f"[{target}] 상세 정보 처리 시작 (원래 페이지: {item_original_page_number}).")

        logger.info(f"[{target}] 상세 페이지 링크 클릭 시도. display_case_text: '{display_case_text}', item_no: '{item_no_part}'")
        if not auction_list_page.click_item_detail_link(
            display_case_text=display_case_text,
            item_no_text=item_no_part,
            full_auction_no_for_onclick_fallback=full_auction_no,
            case_year_for_onclick_fallback=case_year_str,
            case_number_part_for_onclick_fallback=case_number_str,
            item_index_on_page_for_onclick_fallback=item_index_on_page
        ):
            raise DetailClickError(f"[{target}] 상세 페이지 링크 클릭 모든 전략 실패.")

        if not detail_page.wait_for_load():
            raise DetailLoadError(f"[{target}] 상세 페이지 로드 시간 초과 또는 실패.")
        
        detail_html = detail_page.get_detail_html()
        if not detail_html:
            raise Exception(f"[{target}] 상세 페이지 HTML 가져오기 실패")

        # --- 사진 존재 여부 및 기존 대표 사진 인덱스 확인 (단 한번, 사진 수집 전) ---
        photos_already_exist_in_db = False
        new_representative_photo_index = None 
        existing_base_info_for_rep_photo_idx = None

        with get_db_connection() as temp_db_conn_for_photo_check:
            if not temp_db_conn_for_photo_check:
                logger.warning(f"[{target}] 사진 존재 여부 확인을 위한 DB 연결 실패. 사진 수집을 기본으로 진행합니다.")
            else:
                existing_base_info_for_rep_photo_idx = get_auction_base_by_auction_no(temp_db_conn_for_photo_check, target)
                if existing_base_info_for_rep_photo_idx:
                    try:
                        photos_already_exist_in_db = db_manager.check_photos_exist(temp_db_conn_for_photo_check, target)
                        logger.info(f"[{target}] DB 사진 존재 여부 사전 확인 결과: {photos_already_exist_in_db}")
                        if photos_already_exist_in_db:
                            new_representative_photo_index = existing_base_info_for_rep_photo_idx.get('representative_photo_index')
                            logger.info(f"[{target}] 기존 대표 사진 인덱스 ({new_representative_photo_index})를 사용합니다.")
                        # else, new_representative_photo_index는 None으로 유지 (새로 수집 시 설정됨)
                    except Exception as e_check_photo_early:
                        logger.error(f"[{target}] DB에서 사진 존재 여부 사전 확인 중 오류: {e_check_photo_early}. 사진 수집을 시도합니다.")
                        photos_already_exist_in_db = False # 오류 시 수집 시도
                else:
                    logger.info(f"[{target}] 기존 AuctionBaseInfo가 DB에 없어 사진 존재 여부 확인 불가. 사진 수집을 진행합니다.")
                    photos_already_exist_in_db = False # 정보 없으면 수집

        collected_photos_data = []
        pdf_path = None
        
        if not photos_already_exist_in_db:
            logger.info(f"[{target}] DB에 사진 정보가 없거나 확인할 수 없어 사진 및 PDF 수집을 진행합니다.")
            collected_photos_data = _collect_photos(detail_page, full_auction_no, case_no_part, item_no_part)
            if collected_photos_data:
                # 새로 수집한 사진이 있으면 첫 번째 사진의 인덱스를 대표 인덱스로 설정 (예시)
                new_representative_photo_index = collected_photos_data[0].get('index', 0) if isinstance(collected_photos_data[0].get('index'), int) else 0
                logger.info(f"[{target}] 새 사진 {len(collected_photos_data)}개 수집 후 대표 사진 인덱스를 {new_representative_photo_index}(으)로 설정합니다.")
            else:
                logger.info(f"[{target}] 사진 수집을 시도했지만, 수집된 사진이 없습니다. 대표 사진 인덱스는 None입니다.")
                new_representative_photo_index = None # 확실히 None으로

            if config.DOWNLOAD_APPRAISAL_PDF:
                if item_deadline.expired():
                    logger.warning(f"[{target}] 사진 수집 후 아이템 처리 시간 초과로 PDF 다운로드 건너뜀.")
                else:
                    pdf_path = _download_pdf(detail_page, target)
                    if item_deadline.expired():
                        logger.warning(f"[{target}] 감정평가서 다운로드 중 아이템 처리 시간 초과.")
        else:
            logger.info(f"[{target}] DB에 이미 사진 정보가 존재하므로 사진 및 PDF 수집을 건너뜁니다. (기존 대표 사진 인덱스: {new_representative_photo_index})")
            # new_representative_photo_index는 위에서 existing_base_info_for_rep_photo_idx.get()을 통해 이미 설정됨

        # 상세 정보 파싱 (사진 수집 여부와 관계없이 항상 수행, collected_photos_data는 비어있을 수 있음)
        parsed_details = detail_page.parse_details(detail_html, target, item_no_part, collected_photos_data)
        if not parsed_details:
            raise Exception(f"[{target}] 상세 정보 파싱 실패")

        logger.debug(f"[{target}] Parsed Details: {str(parsed_details)[:1000]}...")
        
        with get_db_connection() as db_conn: # 메인 DB 작업용 연결
            if not db_conn:
                 raise Exception(f"[{target}] DB 연결 실패 - get_db_connection()이 None을 반환했습니다.")

            # --- 자식 테이블 데이터 삭제 (테이블명 직접 사용) ---
            tables_to_delete_always = [
                "DateHistory", "SimilarSale", 
                "AuctionDetailInfo", "AuctionAppraisalSummary"
            ]
            logger.debug(f"[{target}] DB 저장 전, 자식 테이블 기존 데이터 삭제 시도 ({', '.join(tables_to_delete_always)}).")
            for table_name in tables_to_delete_always:
                delete_rows_by_auction_no(db_conn, table_name, target)

            if not photos_already_exist_in_db: 
                logger.info(f"[{target}] 신규 사진을 처리하므로 기존 PhotoURL 테이블 데이터를 삭제합니다.")
                delete_rows_by_auction_no(db_conn, "PhotoURL", target) 
            else: 
                logger.info(f"[{target}] 기존 사진 데이터가 DB에 존재하므로 PhotoURL 테이블 삭제를 건너뜁니다.")

            # --- 데이터베이스 저장 ---
            base_info_to_save = {
                'auction_no': target,
                'court_name': base_info.get('court_name'),
                'case_year': case_year_str,
                'case_number': case_number_str,
                'item_no': item_no_part,
                'appraisal_price': base_info.get('appraisal_price'),
                'min_bid_price': base_info.get('min_bid_price'),
                'min_bid_price_2': None, # 목록 페이지에는 없는 정보이므로 None으로 설정
                'sale_date': parsed_details.get('sale_date'), 
                'status': parsed_details.get('status_detail') or base_info.get('status'),
                'car_name': parsed_details.get('car_name'),
                'car_model_year': parsed_details.get('car_model_year'),
                'car_reg_number': parsed_details.get('car_reg_number'),
                'car_mileage': parsed_details.get('mileage'), 
                'car_fuel': parsed_details.get('car_fuel'),
                'car_transmission': parsed_details.get('car_transmission'),
                'car_type': parsed_details.get('car_type'),
                'manufacturer': parsed_details.get('manufacturer'),
                'representative_photo_index': new_representative_photo_index 
            }
            logger.debug(f"[{target}] Value for appraisal_price before DB insert: {base_info_to_save.get('appraisal_price')}")
            insert_auction_base_info(db_conn, base_info_to_save)

            if collected_photos_data and not photos_already_exist_in_db:
                logger.info(f"[{target}] 수집된 새 사진 {len(collected_photos_data)}개를 DB에 저장합니다.")
                insert_photo_urls(db_conn, target, base_info.get('court_name'), collected_photos_data)
            elif not collected_photos_data and not photos_already_exist_in_db:
                logger.info(f"[{target}] 수집된 새 사진이 없어 PhotoURL에 저장할 내용이 없습니다 (DB에도 원래 없었음).")
            
            date_history_entries = parsed_details.get('parsed_auction_date_history', [])
            if date_history_entries:
                court_name_for_history = base_info.get('court_name', '')
                if not insert_auction_date_history(db_conn, target, court_name_for_history, date_history_entries):
                    logger.warning(f"[{target}] AuctionDateHistory 저장 실패 또는 부분 실패.")
                else:
                    logger.info(f"[{target}] AuctionDateHistory {len(date_history_entries)}건 저장 완료.")

            # --- AuctionDetailInfo 저장 ---
            # parsed_details에서 AuctionDetailInfo에 필요한 모든 필드를 가져와서 딕셔너리 생성
            detail_info_to_save = {
                'auction_no': target,
                'court_name': base_info.get('court_name'),
                'location_address': parsed_details.get('location_address'),
                'sale_time': parsed_details.get('sale_time'),
                'sale_location': parsed_details.get('sale_location'),
                'car_vin': parsed_details.get('car_vin'),
                'other_details': parsed_details.get('other_details'),
                'documents': parsed_details.get('documents_json_str') or parsed_details.get('documents'), # JSON 문자열 우선, 없으면 기존 값
                'kind': parsed_details.get('kind'),
                'bid_method': parsed_details.get('bid_method'),
                'case_received_date': parsed_details.get('case_received_date'),
                'auction_start_date': parsed_details.get('auction_start_date'),
                'distribution_due_date': parsed_details.get('distribution_due_date'),
                'claim_amount': parsed_details.get('claim_amount'),
                'engine_type': parsed_details.get('engine_type'),
                'approval_number': parsed_details.get('approval_number'),
                'displacement': parsed_details.get('displacement'),
                'department_info': parsed_details.get('department_info'),
                'dividend_demand_details': parsed_details.get('dividend_demand_details'),
                'dividend_storage_method': parsed_details.get('dividend_storage_method'),
                'appraisal_summary_text': parsed_details.get('appraisal_summary_text')
            }
            
            # 비어있지 않은 경우에만 저장 시도
            # appraisal_summary_text는 길 수 있으므로 로깅에서 제외하거나 축약할 수 있음
            has_detail_data_to_save = any(value is not None for key, value in detail_info_to_save.items() if key not in ['auction_no', 'court_name'])

            if has_detail_data_to_save:
                logger.info(f"[{target}] AuctionDetailInfo 저장 시도. 데이터: { {k:v for k,v in detail_info_to_save.items() if k != 'appraisal_summary_text'} }...") # appraisal_summary_text 제외하고 로깅
                if not insert_auction_detail_info(db_conn, detail_info_to_save):
                    logger.warning(f"[{target}] AuctionDetailInfo 저장 실패.")
                else:
                    logger.info(f"[{target}] AuctionDetailInfo 저장 완료.")
            else:
                logger.info(f"[{target}] AuctionDetailInfo - 저장할 유효한 상세 정보가 없어 건너뜁니다.")

            # AuctionAppraisalSummary 저장 로직
            appraisal_summary_data = {}
            for key, value in parsed_details.items():
                if key.startswith("summary_"):
                    appraisal_summary_data[key] = value
            
            if appraisal_summary_data:
                if not insert_or_update_appraisal_summary(db_conn, target, appraisal_summary_data):
                    logger.warning(f"[{target}] AuctionAppraisalSummary 저장 실패.")
                else:
                    logger.info(f"[{target}] AuctionAppraisalSummary 저장 완료.")
            else:
                logger.info(f"[{target}] AuctionAppraisalSummary - appraisal_summary_data가 비어 있어 저장 건너뜀.")

            similar_sales_data = parsed_details.get('parsed_similar_sales', [])
            if similar_sales_data:
                all_similar_saved = True
                for sale_item_raw in similar_sales_data:
                    sale_item_for_insert = {
                        **sale_item_raw,
                        "auction_no": target,
                        "court_name": base_info.get('court_name', '')
                    }
                    if not insert_similar_sale(db_conn, sale_item_for_insert):
                        logger.warning(f"[{target}] SimilarSales 항목 저장 실패: {str(sale_item_for_insert)[:100]}")
                        all_similar_saved = False
                
                if all_similar_saved:
                    logger.info(f"[{target}] SimilarSales {len(similar_sales_data)}건 저장 완료.")
                else:
                    logger.warning(f"[{target}] SimilarSales 일부 항목 저장 실패.")

            logger.info(f"[{target}] DB 커밋 (자동) 완료.")
        logger.info(f"[{target}] 상세 정보 처리 성공.")
        return True

    except (DetailClickError, DetailLoadError) as e_user:
        logger.error(f"[{target}] 상세 정보 처리 중 예측된 오류 (클릭/로드): {e_user}")
        if config.DEBUG and driver:
            try:
                filename = f"error_detail_click_load_{target.replace('/','_').replace('-','_')}.html"
                filepath = os.path.join(config.DEBUG_DIR, filename)
                with open(filepath, "w", encoding="utf-8") as f_debug:
                    f_debug.write(driver.page_source)
                logger.debug(f"Saved page source to {filepath} on DetailClick/LoadError")
            except Exception as e_save:
                logger.error(f"Failed to save page source on error: {e_save}")
        return False 
    except ConnectionResetError as e_conn_reset:
        logger.error(f"[{target}] 상세 정보 처리 중 ConnectionResetError 발생: {e_conn_reset}", exc_info=True)
        raise 
    except requests.exceptions.RequestException as e_req:
        logger.error(f"[{target}] 상세 정보 처리 중 requests 예외 발생 (아마도 PDF 다운로드 중): {e_req}", exc_info=True)
        raise 
    except Exception as e_general:
        logger.error(f"[{target}] 상세 처리 중 예상치 못한 오류: {e_general}", exc_info=True)
        if config.DEBUG and driver:
            try:
                filename = f"error_unexpected_detail_processing_{target.replace('/','_').replace('-','_')}.html"
                filepath = os.path.join(config.DEBUG_DIR, filename)
                with open(filepath, "w", encoding="utf-8") as f_debug:
                    f_debug.write(driver.page_source)
                logger.debug(f"Saved page source to {filepath} on unexpected error")
            except Exception as e_save:
                logger.error(f"Failed to save page source on unexpected error: {e_save}")
        raise 
    finally:
        logger.info(f"[{target}] finally 블록 진입. 목록 페이지로 복귀 및 안정화 시도.")
        current_url = driver.current_url
        navigated_back_to_list = False

        # 1. 상세 페이지에서 벗어났는지 확인 -> 무조건 go_back_to_list_page 호출로 변경
        logger.info(f"[{target}] '이전' 버튼 클릭을 통해 목록 페이지로 복귀 시도.")
        if detail_page.go_back_to_list_page(auction_list_page, item_original_page_number):
            navigated_back_to_list = True
            logger.info(f"[{target}] '이전' 버튼 클릭 후 목록 페이지로 복귀 성공 (또는 이미 목록 페이지).")
            time.sleep(config.UI_ACTION_DELAY_SECONDS) # 페이지 전환을 위한 추가 시간
        else:
            logger.error(f"[{target}] '이전' 버튼 클릭을 통한 목록 페이지로 복귀 실패!")
        
        # 2. 목록 페이지 그리드 안정화
        if navigated_back_to_list:
            logger.info(f"[{target}] 목록 페이지 복귀 후, 페이지 {item_original_page_number} 그리드 확인 시도.")
            time.sleep(0.5) # 페이지 번호 읽기 전 짧은 대기
            current_page_after_back = auction_list_page.get_current_page_number_from_pagination()
            
            expected_page_for_grid_check = item_original_page_number
            if current_page_after_back is not None and current_page_after_back != item_original_page_number:
                logger.warning(f"[{target}] 목록 복귀 후 현재 페이지 번호({current_page_after_back})가 아이템 원래 페이지({item_original_page_number})와 다름. 감지된 현재 페이지 기준으로 그리드 확인.")
                expected_page_for_grid_check = current_page_after_back # 감지된 페이지를 우선으로 할지, 원래 페이지를 우선으로 할지 결정 필요. 여기서는 감지된 페이지 사용.
            elif current_page_after_back is None:
                logger.warning(f"[{target}] 목록 복귀 후 현재 페이지 번호를 감지할 수 없음. 아이템 원래 페이지({item_original_page_number}) 기준으로 그리드 확인 시도.")
                # expected_page_for_grid_check는 item_original_page_number로 유지

            if not auction_list_page.wait_for_grid(current_page_expected=expected_page_for_grid_check, is_retry=True):
                logger.error(f"[{target}] 목록으로 돌아온 후 페이지 {expected_page_for_grid_check} 그리드 로드/확인 최종 실패!")
            else:
                logger.info(f"[{target}] 목록 페이지 {expected_page_for_grid_check} 그리드 안정화 확인 완료.")
                if handle_unexpected_alert(driver):
                    logger.info(f"[{target}] 목록 페이지 복귀 후 예상치 못한 알림창이 발견되어 처리했습니다.")
        else:
            logger.error(f"[{target}] 최종적으로 목록 페이지로 돌아오지 못했습니다. 그리드 확인 생략.")
        
        logger.info(f"[{target}] 아이템 처리 완료 (finally 블록 종료).")


def _process_single_page(auction_list_page: AuctionListPage, db_conn, current_page_number: int, total_pages: int, actual_items_per_page: int):
    page_start_time = time.monotonic()
    logger.info(f"페이지 처리 시작: {current_page_number}/{total_pages} (페이지당 아이템 수: {actual_items_per_page})")

    if handle_unexpected_alert(auction_list_page.driver):
        logger.info(f"페이지 {current_page_number} 처리 시작 전 알림창이 있어 처리했습니다. 1초 대기 후 진행합니다.")
        time.sleep(1)

    if current_page_number > 1:
        logger.info(f"페이지 {current_page_number}로 이동 시도...")
        
        old_grid_body_element = None
        try:
            old_grid_body_element = auction_list_page.driver.find_element(By.ID, auction_list_page.results_grid_body_id)
            logger.debug(f"페이지 이동 전, 이전 그리드 바디({auction_list_page.results_grid_body_id}) 요소 저장됨.")
        except NoSuchElementException:
            logger.warning(f"페이지 이동 전, 이전 그리드 바디({auction_list_page.results_grid_body_id})를 찾을 수 없음. staleness 확인 불가.")

        try:
            # auction_list_page.driver.execute_script(f"f_goPage('{current_page_number}')") # 기존 JS 직접 호출
            if not auction_list_page.go_to_page_number(current_page_number): # 수정된 호출
                logger.error(f"페이지 {current_page_number}로 이동 실패 (go_to_page_number가 False 반환).")
                return False, 0, 1 # page_successful, items_processed_on_page, errors_on_page
            logger.info(f"페이지 {current_page_number}로 이동 시도 완료 (go_to_page_number 호출).")

            if old_grid_body_element:
                try:
                    WebDriverWait(auction_list_page.driver, config.STALENESS_CHECK_TIMEOUT_SECONDS).until(
                        EC.staleness_of(old_grid_body_element),
                        message=f"이전 페이지 그리드 바디({auction_list_page.results_grid_body_id}) staleness 대기 시간 초과"
                    )
                    logger.info(f"이전 페이지 그리드 바디 stale 확인됨. 새 페이지 로드 시작된 것으로 간주.")
                except TimeoutException as e_stale:
                    logger.warning(f"{e_stale.msg} 페이지가 예상대로 변경되지 않았을 수 있음.")
            else:
                logger.debug("이전 그리드 바디 요소 없어 staleness 확인 생략. UI_ACTION_DELAY_SECONDS 만큼 대기.")
                time.sleep(config.UI_ACTION_DELAY_SECONDS) 

        except Exception as e_nav:
            logger.error(f"페이지 {current_page_number}로 이동 중 JS 실행 오류: {e_nav}", exc_info=True)
            return False, 0, 1 # page_successful, items_processed_on_page, errors_on_page

    grid_loaded_successfully = auction_list_page.wait_for_grid(current_page_expected=current_page_number)
    if not grid_loaded_successfully:
        logger.error(f"페이지 {current_page_number}의 그리드를 기다리는 중 오류 발생. 해당 페이지 처리 중단.")
        return False, 0, 1 # page_successful, items_processed_on_page, errors_on_page
    
    logger.info(f"페이지 {current_page_number} 그리드 로드 확인됨.")

    auction_items_on_page = auction_list_page.get_current_page_items(current_page_number)
    if not auction_items_on_page:
        logger.warning(f"페이지 {current_page_number}에서 경매 아이템을 찾을 수 없습니다.")
        return True, 0, 0 # page_successful, items_processed_on_page, errors_on_page

    processed_count_on_page = 0
    for item_idx, item_base_info in enumerate(auction_items_on_page):
        item_base_info['_current_page_for_item'] = current_page_number 

        auction_no = item_base_info['auction_no']
        
        # 각 아이템 처리 직전에 DB에서 최신 정보 조회
        # db_conn은 _process_single_page 함수에 전달된 것을 사용
        existing_auction_data_for_current_item = get_auction_base_by_auction_no(db_conn, auction_no)
        should_crawl_details = True # 기본값: 크롤링 수행

        if existing_auction_data_for_current_item:
            list_sale_date_str = item_base_info.get('sale_date') # 목록에서 가져온 날짜 문자열 (item_base_info 사용)
            db_sale_datetime_obj = existing_auction_data_for_current_item.get('sale_date') # DB 값 (datetime 객체 또는 None 예상)

            # 목록에서 가져온 날짜 문자열을 datetime.date 객체로 변환
            list_sale_datetime_parsed = parse_date_string_to_datetime(list_sale_date_str)
            list_sale_date_part = list_sale_datetime_parsed.date() if list_sale_datetime_parsed else None
            
            db_sale_date_part = None
            db_sale_time_part = None

            if isinstance(db_sale_datetime_obj, datetime.datetime):
                db_sale_date_part = db_sale_datetime_obj.date()
                db_sale_time_part = db_sale_datetime_obj.time()
            elif isinstance(db_sale_datetime_obj, str): # DB에 문자열로 저장된 경우 대비
                parsed_db_dt = parse_date_string_to_datetime(db_sale_datetime_obj)
                if parsed_db_dt:
                    db_sale_date_part = parsed_db_dt.date()
                    db_sale_time_part = parsed_db_dt.time()
            
            # 조건 1: 목록의 날짜와 DB의 날짜가 일치하는지
            dates_match = (list_sale_date_part is not None and \
                           db_sale_date_part is not None and \
                           list_sale_date_part == db_sale_date_part)
            
            # 조건 2: DB의 시간이 유효한지 (자정이 아닌지)
            time_is_not_midnight = (db_sale_time_part is not None and \
                                    db_sale_time_part != datetime.time(0, 0, 0))

            if dates_match and time_is_not_midnight:
                logger.info(f"[{auction_no}] 조건 일치: 목록상 매각일({list_sale_date_str})과 DB 매각일({db_sale_datetime_obj})의 날짜 부분이 동일하고, DB 시간이 유효합니다. 상세 정보 수집을 건너뜁니다.")
                should_crawl_details = False
            else:
                reasons_for_recrawl = []
                if not dates_match:
                    reasons_for_recrawl.append(f"날짜 불일치 또는 정보 부족 (목록 날짜: {list_sale_date_part}, DB 날짜: {db_sale_date_part})")
                if not time_is_not_midnight:
                    reasons_for_recrawl.append(f"DB 시간 자정 또는 정보 부족 (DB 시간: {db_sale_time_part})")
                
                # 기존 로직에서는 DB에 데이터가 없으면 항상 크롤링하므로, 이 부분은 else 블록에서 처리됨.
                # 여기서는 DB에 데이터가 "있지만" 조건이 맞지 않아 다시 크롤링하는 경우의 로그.
                logger.info(f"[{auction_no}] DB에 데이터가 존재하지만 다음 이유로 상세 정보 수집을 진행합니다: {'; '.join(reasons_for_recrawl if reasons_for_recrawl else ['조건 불일치'])}.")
                should_crawl_details = True # 명시적으로 True (기본값이지만 명확히)
        else:
            logger.info(f"[{auction_no}] DB에 존재하지 않는 신규 건이므로 상세 정보 수집을 진행합니다.")
            should_crawl_details = True # 명시적으로 True (기본값이지만 명확히)


        if should_crawl_details:
            try:
                if process_single_auction_item(auction_list_page.driver, auction_list_page.wait, auction_list_page, item_base_info):
                    processed_count_on_page += 1
                else:
                    logger.warning(f"[{auction_no}] (페이지 {current_page_number}, 인덱스 {item_idx}) 처리 실패 또는 건너뜀.")
            except Exception as e_item_proc:
                logger.error(f"[{auction_no}] (페이지 {current_page_number}, 인덱스 {item_idx}) 처리 중 최종 예외 발생: {e_item_proc}. 이 아이템 건너뜀.", exc_info=False) 
                if isinstance(e_item_proc, (ConnectionResetError, requests.exceptions.RequestException)):
                    logger.error("네트워크 관련 예외로 인해 현재 페이지 처리 중단 후 재시도 유도.")
                    raise 
        
    page_processing_time = time.monotonic() - page_start_time
    logger.info(f"페이지 {current_page_number}/{total_pages} 처리 완료. 소요시간: {page_processing_time:.2f}초. 성공적으로 처리된 아이템 수: {processed_count_on_page}/{len(auction_items_on_page)}.")
    return True, processed_count_on_page, 0 # page_successful, items_processed_on_page, errors_on_page


def crawl_auction_list_pages(auction_list_page, db_conn, existing_ids, total_items_to_crawl, items_per_page):
    all_processed_items_count = 0 
    total_errors_accumulated = 0    

    for p in range(1, total_items_to_crawl + 1):
        page_successful, items_processed_on_page, errors_on_page = _process_single_page(
            auction_list_page, db_conn, p, total_items_to_crawl, items_per_page
        )
        
        all_processed_items_count += items_processed_on_page
        total_errors_accumulated += errors_on_page

        if not page_successful:
            logger.error(f"페이지 {p} 처리 실패. 다음 페이지로 넘어갑니다.")
            # 필요하다면 여기서 추가적인 오류 처리나 재시도 로직을 넣을 수 있음

        if p < total_items_to_crawl:
            # 오류 발생 여부와 관계없이 페이지 간 딜레이를 주는 것이 안정적일 수 있음
            delay_seconds = config.DELAY_BETWEEN_PAGES
            if errors_on_page > 0 and hasattr(config, 'DELAY_ON_ERROR'): # 오류 발생 시 더 긴 딜레이 (옵션)
                delay_seconds = max(delay_seconds, config.DELAY_ON_ERROR)
            
            logger.info(f"페이지 {p} 완료 후 {delay_seconds:.1f}초 대기...")
            time.sleep(delay_seconds)
            
    # 이 함수의 반환값은 main 함수에서 records로 받고 save_processed_auctions_to_db로 전달됨.
    # 현재 _process_single_page는 아이템 리스트를 반환하지 않으므로, 
    # 이 함수의 반환값도 실제 아이템 데이터가 아닌 처리 통계가 되어야 함.
    # 또는, _process_single_page에서 처리된 아이템들을 리스트로 모아서 반환하고 여기서 합쳐야 함.
    # 현재 main 함수의 로직은 records를 기대하므로, 이 부분의 호환성 검토 필요.
    # 우선은 총 처리된 아이템 수를 반환하도록 수정 (save_processed_auctions_to_db 함수는 DB에서 직접 읽는 방식으로 변경 필요할 수 있음)
    logger.info(f"모든 페이지 순회 완료. 총 처리된 아이템 수: {all_processed_items_count}, 총 누적 오류 (카운트된 것): {total_errors_accumulated}")
    return all_processed_items_count # 임시로 총 처리된 아이템 수 반환, main 함수와 호환성 확인 필요


def save_processed_auctions_to_db(db_conn, records):
    # 테이블 핸들러 정의
    handlers = {
        "BaseInfo": insert_auction_base_info,
        "DateHistory": insert_auction_date_history,
        "PhotoURL": insert_photo_urls,
        "DetailInfo": insert_auction_detail_info,
        "SimilarSale": insert_similar_sale,
    }

    for rec in records:
        auction_no = rec.get("auction_no")
        if not auction_no:
            logger.warning(f"Skipping record due to missing auction_no: {str(rec)[:200]}")
            continue

        for name, data in rec.items():
            # 루프 시작 시점에 처리할 필요 없는 최상위 키들을 먼저 건너뜀
            if name == "auction_no": 
                continue
            if name.startswith('summary_'): # 감정평가 요약 필드
                continue
            if name in ['appraisal_pdf_path', '_is_existing_in_db']: # 기타 메타 필드
                continue

            fn = handlers.get(name)
            if not fn:
                # 핸들러가 없는 다른 최상위 키에 대한 경고 (예상치 못한 키)
                logger.warning(f"[{auction_no}] No handler for top-level data key: {name}. Data: {str(data)[:100]}")
                continue

            ok = False
            try:
                court_name_for_handler = rec.get("BaseInfo", {}).get("court_name") 
                if not court_name_for_handler:
                    logger.warning(f"[{auction_no}] court_name missing in BaseInfo for handler {name}. Using empty string.")
                    court_name_for_handler = ""

                if name == "PhotoURL":
                    photo_list_to_insert = data.get('photo_data_list', []) 
                    if photo_list_to_insert:
                        ok = fn(db_conn, auction_no, court_name_for_handler, photo_list_to_insert)
                    else:
                        # logger.debug(f"[{auction_no}] No photos found in PhotoURL data, skipping DB insert.") # 디버그 로그
                        ok = True 
                elif name == "DateHistory":
                    if data: 
                        ok = fn(db_conn, auction_no, court_name_for_handler, data) 
                    else:
                        # logger.debug(f"[{auction_no}] No data for DateHistory, skipping DB insert.") # 디버그 로그
                        ok = True
                elif name == "SimilarSale":
                    if data and isinstance(data, list):
                        all_similar_saved = True
                        for sale_item in data:
                            if isinstance(sale_item, dict):
                                sale_item_with_identifiers = {**sale_item, "auction_no": auction_no, "court_name": court_name_for_handler}
                                if not fn(db_conn, sale_item_with_identifiers):
                                    all_similar_saved = False
                                    logger.error(f"[{auction_no}] Failed to save one SimilarSale item: {str(sale_item)[:100]}")
                            else:
                                logger.warning(f"[{auction_no}] SimilarSale list contains non-dict item: {str(sale_item)[:100]}")
                        ok = all_similar_saved
                    elif data:
                        # logger.debug(f"[{auction_no}] No data for SimilarSale, skipping DB insert.") # 디버그 로그
                        ok = True 
                    else:
                        # logger.debug(f"[{auction_no}] No data for SimilarSale, skipping DB insert.") # 디버그 로그
                        ok = True
                elif name == "BaseInfo":
                    if data: 
                        ok = fn(db_conn, data) 
                    else:
                        logger.warning(f"[{auction_no}] No data for BaseInfo.")
                        ok = False
                elif name == "DetailInfo":
                    if data and isinstance(data, dict): 
                        ok = fn(db_conn, data)
                    else:
                        logger.warning(f"[{auction_no}] No or invalid data for DetailInfo: {type(data)}")
                        ok = False
                
                if not ok:
                    logger.error(f"[{auction_no}] Failed to save {name} to DB.")

            except Exception as e_db_insert_group:
                logger.error(f"[{auction_no}] DB insert error for {name} group: {e_db_insert_group}", exc_info=config.DEBUG)
        
        summary_data_to_save = {
            'auction_no': auction_no,
            'summary_year_mileage': rec.get('summary_year_mileage'),
            'summary_color': rec.get('summary_color'),
            'summary_management_status': rec.get('summary_management_status'),
            'summary_fuel': rec.get('summary_fuel'),
            'summary_inspection_validity': rec.get('summary_inspection_validity'),
            'summary_options_etc': rec.get('summary_options_etc'),
        }
        
        if any(summary_data_to_save[key] and summary_data_to_save[key] != '정보 없음' 
               for key in summary_data_to_save if key != 'auction_no'):
            try:
                # db_manager 모듈을 직접 사용하여 함수 호출
                if hasattr(db_manager, 'insert_or_update_appraisal_summary') and callable(getattr(db_manager, 'insert_or_update_appraisal_summary')):
                    if db_manager.insert_or_update_appraisal_summary(db_conn, auction_no_pk=auction_no, summary_data=summary_data_to_save):
                        # logger.debug(f"[{auction_no}] Successfully saved AppraisalSummary to DB.") # 디버그 로그
                        pass # 성공 로그는 유지하지 않음
                    else:
                        logger.error(f"[{auction_no}] Failed to save AppraisalSummary to DB (handler returned false).")
                else:
                    logger.warning(f"[{auction_no}] db_manager.insert_or_update_appraisal_summary function not found. Skipping AppraisalSummary.")
            except Exception as e_app_summary_insert:
                logger.error(f"[{auction_no}] AppraisalSummary DB insert error: {e_app_summary_insert}", exc_info=config.DEBUG)
        else:
            # logger.debug(f"[{auction_no}] No specific data for AppraisalSummary fields, skipping DB insert.") # 디버그 로그
            pass

    logger.info("Finished saving processed auction data to DB.")


def main():
    global _current_db_connection_for_signal_handler # 전역 변수 사용 선언
    
    # 시그널 핸들러 등록
    signal.signal(signal.SIGINT, signal_handler) # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler) # Terminate 신호 (일부 시스템)

    logger.info("경매 정보 업데이트 시작")
    start = time.monotonic()

    with get_db_connection() as db_conn:
        _current_db_connection_for_signal_handler = db_conn # DB 연결 시 전역 변수 설정
        try:
            cursor = db_conn.cursor()
            cursor.execute('SELECT auction_no FROM "AuctionBaseInfo"')
            existing = {r[0] for r in cursor.fetchall()}
            cursor.close()
            with initialize_driver() as driver:
                wait = WebDriverWait(driver, config.DEFAULT_WAIT_TIME)
                list_page = AuctionListPage(driver, wait)

                if not list_page.initialize_search(): return
                if not list_page.wait_for_grid(1): return
                ok, per_page = list_page.set_items_per_page(config.ITEMS_PER_PAGE)
                total = list_page.get_total_pages_count(per_page)
                if total == 0: return

                # crawl_auction_list_pages는 이제 처리된 아이템 '개수'를 반환 (또는 다른 통계 정보)
                processed_item_count = crawl_auction_list_pages(list_page, db_conn, existing, total, per_page)
                
                # 개별 아이템은 process_single_auction_item 내에서 DB에 직접 저장되므로,
                # save_processed_auctions_to_db 함수 호출은 필요하지 않음.
                # if records: # records 대신 processed_item_count 사용
                #     save_processed_auctions_to_db(db_conn, records) # 이 부분 주석 처리 또는 삭제
                logger.info(f"크롤링 및 개별 아이템 DB 저장 작업 완료. 총 {processed_item_count} 페이지 아이템 처리 시도됨 (오류 포함).")
        finally:
            _current_db_connection_for_signal_handler = None # DB 연결 종료 시 전역 변수 초기화


    logger.info(f"완료: 총 소요 {time.monotonic()-start:.1f}s") # records 변수 제거


if __name__ == "__main__":
    main()
