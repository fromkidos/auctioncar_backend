"""
이미지 처리 관련 기능
"""
import os
import fitz
from typing import List, Tuple
from PIL import Image, ImageOps
from .utils import trim_image_whitespace, crop_image_edges


class ImageProcessor:
    """이미지 처리 클래스"""
    
    def __init__(self, output_root: str):
        self.output_root = output_root
    
    def _iter_image_blocks(self, page: fitz.Page, min_area: float = 10000) -> List[fitz.Rect]:
        """페이지에서 이미지 블록들을 찾아 반환"""
        image_blocks = []
        
        # 이미지 블록 찾기
        for block in page.get_text("dict")["blocks"]:
            if "image" in block:
                bbox = fitz.Rect(block["bbox"])
                area = bbox.width * bbox.height
                
                # 최소 면적 필터
                if area < min_area:
                    continue
                
                # 가로세로 비율 필터 (너무 긴 선이나 헤더 제외)
                aspect_ratio = bbox.width / bbox.height
                if aspect_ratio > 10 or aspect_ratio < 0.1:
                    continue
                
                image_blocks.append(bbox)
        
        return image_blocks
    
    def _is_photos_page(self, page: fitz.Page, is_text_based: bool = True) -> bool:
        """사진용지 페이지인지 판단"""
        if not is_text_based:
            # 스캔본의 경우 텍스트 기반 제목 검색 불가
            return False
        
        # 페이지 텍스트에서 "사진용지" 관련 키워드 검색
        page_text = page.get_text("text")
        photo_keywords = ["사진용지", "사 진 용 지"]
        
        for keyword in photo_keywords:
            if keyword in page_text:
                # "감정평가요항표"가 포함된 경우 제외
                if "감정평가요항표" in page_text:
                    return False
                
                # 이미지 블록이 있는지 확인
                blocks = self._iter_image_blocks(page)
                if len(blocks) > 0:
                    return True
        
        return False
    
    def extract_images_from_page(self, page: fitz.Page, page_num: int, auction_no: str, 
                                is_text_based: bool = True) -> List[str]:
        """페이지에서 이미지 추출"""
        saved_images = []
        
        # 사진용지 페이지인지 확인
        if not self._is_photos_page(page, is_text_based):
            return saved_images
        
        # 이미지 블록들 찾기
        image_blocks = self._iter_image_blocks(page)
        
        if not image_blocks:
            return saved_images
        
        # 출력 디렉토리 생성
        photos_dir = os.path.join(self.output_root, "photos")
        os.makedirs(photos_dir, exist_ok=True)
        
        # 각 이미지 블록을 파일로 저장
        for idx, bbox in enumerate(image_blocks):
            try:
                # 이미지 렌더링
                mat = fitz.Matrix(2.0, 2.0)  # 2배 확대
                pix = page.get_pixmap(matrix=mat, clip=bbox)
                
                # 파일명 생성
                filename = f"{auction_no}_{idx}.png"
                image_path = os.path.join(photos_dir, filename)
                
                # 이미지 저장
                pix.save(image_path)
                
                # 이미지 후처리
                trim_image_whitespace(image_path, tolerance=6)
                crop_image_edges(image_path, pixels=1)
                
                saved_images.append(image_path)
                
            except Exception as e:
                print(f"이미지 저장 오류 (페이지 {page_num}, 이미지 {idx}): {e}")
                continue
        
        return saved_images
    
    def process_image(self, image_path: str) -> None:
        """이미지 후처리 (화이트스페이스 제거 + 가장자리 크롭)"""
        try:
            trim_image_whitespace(image_path, tolerance=6)
            crop_image_edges(image_path, pixels=1)
        except Exception as e:
            print(f"이미지 처리 오류 {image_path}: {e}")
