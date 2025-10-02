"""
사진 추출 관련 기능
"""
import os
from typing import List
import fitz
from .image_processor import ImageProcessor
from .utils import extract_auction_number


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
    
    
    def extract_photos(self) -> List[str]:
        """사진 추출 메인 메서드 (텍스트 기반 PDF만 처리)"""
        pdf_filename = os.path.basename(self.doc.name)
        auction_no = extract_auction_number(pdf_filename)
        
        # 출력 디렉토리 생성
        photos_dir = os.path.join(self.output_root, "photos")
        os.makedirs(photos_dir, exist_ok=True)
        
        saved_images = []
        
        # 텍스트 기반 PDF만 처리 (스캔본은 update_ongoing_auctions.py에서 처리됨)
        if self.is_text_based:
            # "사진용지" 페이지에서 이미지 추출
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
            # 스캔본 PDF는 update_ongoing_auctions.py에서 이미 처리됨
            print(f"[사진 추출] 스캔본 PDF이므로 사진 추출을 건너뜁니다: {pdf_filename}")
        
        return saved_images
