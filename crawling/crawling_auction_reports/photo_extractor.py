"""
사진 추출 관련 기능
"""
import os
import sys
from typing import List, Optional
import fitz
from image_processor import ImageProcessor
from utils import extract_auction_number


class PhotoExtractor:
    """사진 추출 클래스"""
    
    def __init__(self, doc: fitz.Document, output_root: str, is_text_based: bool):
        self.doc = doc
        self.output_root = output_root
        self.is_text_based = is_text_based
        self.image_processor = ImageProcessor(output_root)
        self.TITLE_KEYS = {
            "photos": ["사진용지", "사 진 용 지"],
        }
    
    def _find_pages_by_titles(self, title_candidates: List[str]) -> List[int]:
        """제목으로 페이지 찾기"""
        matching_pages = []
        
        for page_num in range(len(self.doc)):
            page = self.doc.load_page(page_num)
            page_text = page.get_text("text")
            
            for title in title_candidates:
                if title in page_text:
                    matching_pages.append(page_num)
                    break
        
        return matching_pages
    
    def _download_photos_from_auction_site(self) -> List[str]:
        """스캔본의 경우 경매 사이트에서 사진 다운로드"""
        try:
            # 경매 번호 추출
            pdf_filename = os.path.basename(self.doc.name)
            auction_no = extract_auction_number(pdf_filename)
            
            print(f"[스캔본] 경매 사이트에서 사진 다운로드 시도: {auction_no}")
            
            # 경매 사이트 크롤링 모듈 import
            crawling_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            sys.path.insert(0, crawling_dir)
            
            from crawling_auction_ongoing.config import crawler_config
            from crawling_auction_ongoing.page_objects import AuctionListPage
            from crawling_auction_ongoing.driver_utils import create_driver
            
            # 경매 번호에서 연도 추출
            year = auction_no.split('타경')[0]
            
            # 드라이버 생성
            driver = create_driver()
            
            try:
                # 경매 목록 페이지로 이동
                list_page = AuctionListPage(driver)
                list_page.initialize_search()
                list_page.wait_for_results()
                
                # 경매 번호로 검색
                if list_page.search_auction(auction_no):
                    # 상세 페이지로 이동
                    detail_page = list_page.go_to_detail_page(auction_no)
                    if detail_page:
                        # 사진 다운로드
                        photos = detail_page.download_photos(auction_no, self.output_root)
                        print(f"[스캔본] {len(photos)}개 사진 다운로드 완료")
                        return photos
                    else:
                        print(f"[스캔본] 상세 페이지 접근 실패: {auction_no}")
                else:
                    print(f"[스캔본] 경매 검색 실패: {auction_no}")
                    
            except Exception as e:
                print(f"[스캔본] 경매 사이트 접근 실패: {e}")
            finally:
                driver.quit()
                
        except Exception as e:
            print(f"[스캔본] 사진 다운로드 오류: {e}")
        
        return []
    
    def extract_photos(self) -> List[str]:
        """사진 추출 메인 메서드"""
        pdf_filename = os.path.basename(self.doc.name)
        auction_no = extract_auction_number(pdf_filename)
        
        # 출력 디렉토리 생성
        photos_dir = os.path.join(self.output_root, "photos")
        os.makedirs(photos_dir, exist_ok=True)
        
        saved_images = []
        
        if self.is_text_based:
            # 텍스트 기반 PDF: "사진용지" 페이지에서 이미지 추출
            photo_pages = self._find_pages_by_titles(self.TITLE_KEYS["photos"])
            
            if photo_pages:
                for page_num in photo_pages:
                    page = self.doc.load_page(page_num)
                    images = self.image_processor.extract_images_from_page(
                        page, page_num, auction_no, self.is_text_based
                    )
                    saved_images.extend(images)
            else:
                # "사진용지" 페이지가 없는 경우, 이미지가 있는 모든 페이지에서 추출
                for page_num in range(len(self.doc)):
                    page = self.doc.load_page(page_num)
                    images = self.image_processor.extract_images_from_page(
                        page, page_num, auction_no, self.is_text_based
                    )
                    saved_images.extend(images)
        else:
            # 스캔본: 경매 사이트에서 사진 다운로드
            saved_images = self._download_photos_from_auction_site()
        
        return saved_images
