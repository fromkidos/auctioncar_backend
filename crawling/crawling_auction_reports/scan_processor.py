"""
스캔본 PDF 처리 관련 기능
"""
import os
import sys
import time
from typing import Optional, List, Dict, Any
import fitz
from .utils import extract_auction_number
from .image_processor import ImageProcessor

# 상위 디렉토리의 모듈들 import
crawling_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, crawling_dir)

# DB 관련 import
from db_manager import get_db_connection, get_auction_base_by_auction_no

# Selenium 관련 import
from crawling_auction_ongoing.driver_utils import initialize_driver
from crawling_auction_ongoing.page_objects import AuctionListPage, AuctionDetailPage
from crawling_auction_ongoing import config as crawler_config
from selenium.webdriver.support.ui import WebDriverWait


class ScanProcessor:
    """스캔본 PDF 처리 클래스"""
    
    def __init__(self, doc: fitz.Document, output_root: str):
        self.doc = doc
        self.output_root = output_root
        self.image_processor = ImageProcessor(output_root)
        self.db_conn = None
        
    def _get_auction_base_info(self, auction_no: str) -> Optional[Dict[str, Any]]:
        """DB에서 경매 기본 정보 조회"""
        try:
            print(f"[스캔본] DB에서 기본정보 조회 시도: {auction_no}")
            
            # DB 연결 및 조회
            with get_db_connection() as db_conn:
                if not db_conn:
                    print(f"[스캔본] DB 연결 실패: {auction_no}")
                    return self._get_mock_data(auction_no)
                
                base_info = get_auction_base_by_auction_no(db_conn, auction_no)
                if base_info:
                    print(f"[스캔본] DB에서 기본정보 조회 성공: {auction_no}")
                    print(f"[스캔본] 조회된 정보: 법원={base_info.get('court_name')}, 연도={base_info.get('case_year')}, 사건번호={base_info.get('case_number')}, 물건번호={base_info.get('item_no')}")
                    return base_info
                else:
                    print(f"[스캔본] DB에서 기본정보를 찾을 수 없음: {auction_no}")
                    return self._get_mock_data(auction_no)
                
        except Exception as e:
            print(f"[스캔본] DB 조회 오류: {e}")
            return self._get_mock_data(auction_no)
    
    def _get_mock_data(self, auction_no: str) -> Dict[str, Any]:
        """모의 데이터 반환"""
        print(f"[스캔본] 모의 데이터 사용: {auction_no}")
        return {
            'auction_no': auction_no,
            'court_name': '서울중앙지방법원',
            'case_year': '2024',
            'case_number': '51128',
            'item_no': '1'
        }
    
    def _search_auction_on_website(self, base_info: Dict[str, Any]) -> Optional[List[str]]:
        """법원 사이트에서 경매 검색 및 사진 다운로드"""
        try:
            print(f"[스캔본] 경매 사이트 접근 시작")
            
            # 드라이버 생성 및 사용
            with initialize_driver() as driver:
                # WebDriverWait 생성
                wait = WebDriverWait(driver, crawler_config.DEFAULT_WAIT_TIME)
                
                # 경매 목록 페이지로 이동
                list_page = AuctionListPage(driver, wait)
                if not list_page.initialize_search():
                    print(f"[스캔본] 경매 목록 페이지 초기화 실패")
                    return []
                
                if not list_page.wait_for_grid():
                    print(f"[스캔본] 경매 목록 그리드 로드 실패")
                    return []
                
                # 검색 조건 설정
                court_name = base_info.get('court_name', '')
                case_year = base_info.get('case_year', '')
                case_number = base_info.get('case_number', '')
                item_no = base_info.get('item_no', '')
                
                print(f"[스캔본] 검색 조건: 법원={court_name}, 연도={case_year}, 사건번호={case_number}, 물건번호={item_no}")
                
                # 특정 경매 번호로 검색 수행
                target_auction_no = base_info['auction_no']
                print(f"[스캔본] 특정 경매 검색 시작: {target_auction_no}")
                
                # 1. 검색 폼 활성화 (숨겨진 검색 버튼 표시)
                try:
                    search_button = driver.find_element("id", "mf_wfm_mainFrame_btn_search")
                    driver.execute_script("arguments[0].style.display = 'block';", search_button)
                    print(f"[스캔본] 검색 버튼 활성화 완료")
                except Exception as e:
                    print(f"[스캔본] 검색 버튼 활성화 실패: {e}")
                
                # 2. 검색 폼 동적 생성 및 조건 설정
                try:
                    print(f"[스캔본] 검색 폼 동적 생성 및 조건 설정: 법원={court_name}, 연도={case_year}, 사건번호={case_number}")
                    
                    # 1단계: 검색 버튼 클릭하여 검색 폼 동적 생성
                    search_button = driver.find_element("id", "mf_wfm_mainFrame_btn_search")
                    search_button.click()
                    print(f"[스캔본] 검색 버튼 클릭 완료 - 검색 폼 동적 생성 대기")
                    
                    # 검색 폼 생성 대기
                    time.sleep(3)
                    
                    # 2단계: 검색 조건 설정
                    from selenium.webdriver.support.ui import Select
                    from selenium.webdriver.common.by import By
                    from selenium.webdriver.support import expected_conditions as EC
                    
                    # 법원 선택
                    if court_name and court_name != "전체":
                        court_elem = wait.until(EC.element_to_be_clickable((By.ID, "mf_wfm_mainFrame_sbx_carTmidCortOfc")))
                        select_obj = Select(court_elem)
                        
                        # 사용 가능한 옵션들 확인
                        available_options = [option.text for option in select_obj.options]
                        print(f"[스캔본] 사용 가능한 법원 옵션들: {available_options}")
                        
                        # 정확한 매칭 시도
                        try:
                            select_obj.select_by_visible_text(court_name)
                            print(f"[스캔본] 법원 선택 성공: {court_name}")
                        except:
                            # 부분 매칭 시도
                            for option in select_obj.options:
                                if court_name in option.text or option.text in court_name:
                                    select_obj.select_by_visible_text(option.text)
                                    print(f"[스캔본] 법원 선택 (부분 매칭): {option.text}")
                                    break
                            else:
                                print(f"[스캔본] 법원 '{court_name}'을 찾을 수 없음")
                                return []
                    
                    # 연도 선택
                    if case_year:
                        year_elem = wait.until(EC.element_to_be_clickable((By.ID, "mf_wfm_mainFrame_sbx_carTmidCsNo")))
                        Select(year_elem).select_by_visible_text(case_year)
                        print(f"[스캔본] 연도 선택: {case_year}")
                    
                    # 사건번호 입력
                    if case_number:
                        case_elem = wait.until(EC.element_to_be_clickable((By.ID, "mf_wfm_mainFrame_ibx_csNo")))
                        case_elem.clear()
                        case_elem.send_keys(case_number)
                        print(f"[스캔본] 사건번호 입력: {case_number}")
                    
                    # 검색 실행
                    search_button.click()
                    print(f"[스캔본] 검색 실행")
                    
                    # 검색 결과 로드 대기
                    time.sleep(8)
                    
                except Exception as e:
                    print(f"[스캔본] 검색 실행 실패: {e}")
                    return []
                
                # 3. 검색 결과에서 해당 경매 찾기
                auction_items = list_page.get_current_page_items(1)
                if not auction_items:
                    print(f"[스캔본] 검색 결과가 없음")
                    return []
                
                target_item_no = base_info.get('item_no', '1')
                target_item = None
                
                print(f"[스캔본] 검색 결과에서 경매 찾기: 물건번호={target_item_no}")
                print(f"[스캔본] 검색된 경매들: {[item.get('auction_no') for item in auction_items[:5]]}")
                
                for item in auction_items:
                    # 물건번호로 매칭 (item_no가 일치하는지 확인)
                    if str(item.get('item_no', '')) == str(target_item_no):
                        target_item = item
                        break
                
                if not target_item:
                    print(f"[스캔본] 검색 결과에서 해당 물건번호를 찾을 수 없음: {target_item_no}")
                    print(f"[스캔본] 검색된 물건번호들: {[item.get('item_no') for item in auction_items[:5]]}")
                    return []
                
                print(f"[스캔본] 대상 경매 아이템 발견: {target_item.get('auction_no')}-{target_item.get('item_no')}")
                
                # 4. 상세 페이지로 이동 (update_ongoing_auctions.py 로직 사용)
                detail_page = AuctionDetailPage(driver, wait)
                
                if list_page.click_item_detail_link(
                    display_case_text=target_item.get('display_case_no', ''),
                    item_no_text=target_item.get('item_no', ''),
                    full_auction_no_for_onclick_fallback=target_auction_no,
                    case_year_for_onclick_fallback=base_info.get('case_year', ''),
                    case_number_part_for_onclick_fallback=base_info.get('case_number', '')
                ):
                    print(f"[스캔본] 상세 페이지 클릭 성공")
                    
                    if detail_page.wait_for_load():
                        print(f"[스캔본] 상세 페이지 로드 성공")
                        # 사진 다운로드
                        photos = self._download_photos_from_detail_page(detail_page, target_auction_no)
                        print(f"[스캔본] {len(photos)}개 사진 다운로드 완료")
                        return photos
                    else:
                        print(f"[스캔본] 상세 페이지 로드 실패")
                else:
                    print(f"[스캔본] 상세 페이지 클릭 실패")
                        
        except Exception as e:
            print(f"[스캔본] 경매 사이트 접근 실패: {e}")
            import traceback
            traceback.print_exc()
                       
        return []
    
    def _download_photos_from_detail_page(self, detail_page: 'AuctionDetailPage', auction_no: str) -> List[str]:
        """상세 페이지에서 사진 다운로드"""
        try:
            # 사진 컨테이너에서 모든 사진 로드
            photo_objects = detail_page.load_all_photos_on_page(
                case_no_for_log=auction_no, 
                item_no_for_log="1"
            )
            
            if not photo_objects:
                print(f"[스캔본] 사진을 찾을 수 없음: {auction_no}")
                return []
            
            # 출력 디렉토리 생성
            photos_dir = os.path.join(self.output_root, "photos")
            os.makedirs(photos_dir, exist_ok=True)
            
            saved_photos = []
            
            for idx, photo_obj in enumerate(photo_objects):
                try:
                    # 사진 처리 및 저장
                    processed_photos = detail_page._process_collected_image_sources(
                        [photo_obj], 
                        auction_no, 
                        "1", 
                        photos_dir
                    )
                    
                    for photo_info in processed_photos:
                        if photo_info.get('path'):
                            # 이미지 후처리
                            self.image_processor.process_image(photo_info['path'])
                            saved_photos.append(photo_info['path'])
                            
                except Exception as e:
                    print(f"[스캔본] 사진 {idx} 처리 오류: {e}")
                    continue
            
            return saved_photos
            
        except Exception as e:
            print(f"[스캔본] 사진 다운로드 처리 오류: {e}")
            return []
    
    def process_scan_pdf(self, pdf_filename: str) -> List[str]:
        """스캔본 PDF 처리 메인 메서드"""
        # 경매 번호 추출
        auction_no = extract_auction_number(pdf_filename)
        print(f"[스캔본] 처리 시작: {auction_no}")
        
        # 1. DB에서 기본 정보 조회
        base_info = self._get_auction_base_info(auction_no)
        if not base_info:
            print(f"[스캔본] 기본 정보 없음으로 처리 중단: {auction_no}")
            return []
        
        # 2. 법원 사이트에서 사진 다운로드
        photos = self._search_auction_on_website(base_info)
        
        return photos
    
    def close(self):
        """리소스 정리"""
        if self.db_conn:
            self.db_conn.close()
