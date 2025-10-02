"""
PDF 파싱을 위한 유틸리티 함수들
"""
import os
import re
import unicodedata
from typing import List
from PIL import Image, ImageOps


def normalize_for_match(text: str) -> str:
    """텍스트 매칭을 위한 정규화"""
    return re.sub(r'\s+', '', text.strip())


def split_lines(text: str) -> List[str]:
    """텍스트를 줄 단위로 분리"""
    return [line.strip() for line in text.split('\n') if line.strip()]


def ensure_dir(path: str) -> None:
    """디렉토리가 존재하지 않으면 생성"""
    os.makedirs(path, exist_ok=True)


def trim_image_whitespace(image_path: str, tolerance: int = 6) -> None:
    """이미지의 흰색 테두리 자동 제거"""
    try:
        with Image.open(image_path) as img:
            # RGB로 변환
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # 흰색 배경 제거
            img = ImageOps.crop(img, border=tolerance)
            
            # 원본 파일에 저장
            img.save(image_path, 'PNG')
    except Exception as e:
        print(f"이미지 크롭 오류 {image_path}: {e}")


def crop_image_edges(image_path: str, pixels: int = 1) -> None:
    """이미지 가장자리에서 지정된 픽셀 수만큼 제거"""
    try:
        with Image.open(image_path) as img:
            width, height = img.size
            
            # 가장자리에서 pixels만큼 제거
            left = pixels
            top = pixels
            right = width - pixels
            bottom = height - pixels
            
            # 유효한 크기인지 확인
            if right > left and bottom > top:
                cropped = img.crop((left, top, right, bottom))
                cropped.save(image_path, 'PNG')
    except Exception as e:
        print(f"이미지 가장자리 크롭 오류 {image_path}: {e}")


def clean_text(text: str) -> str:
    """텍스트 정리 (공백, 제어문자 등 제거)"""
    if not text:
        return ""
    
    # 유니코드 카테고리를 사용하여 제어 문자 제거
    cleaned = ''.join(char if not unicodedata.category(char).startswith('C') else ' ' for char in text)
    
    # 연속된 공백을 하나로 변환
    cleaned = re.sub(r'\s+', ' ', cleaned)
    
    return cleaned.strip()


def extract_auction_number(filename: str) -> str:
    """PDF 파일명에서 경매 번호 추출"""
    # 파일명에서 확장자 제거
    name = os.path.splitext(filename)[0]
    
    # "감정평가서" 제거
    name = name.replace('_감정평가서', '')
    
    return name


def is_valid_address(text: str) -> bool:
    """주소 유효성 검사"""
    if not text or len(text) < 5:
        return False
    
    # 의미없는 문자열 제외
    invalid_patterns = ['', ' ', 'N', 'null', 'None', 'unknown']
    if text in invalid_patterns:
        return False
    
    # 주소 패턴 확인
    address_keywords = ['특별시', '광역시', '특별자치시', '특별자치도', '도', '시', '군', '구', '읍', '면', '동', '리']
    return any(keyword in text for keyword in address_keywords)


def clean_location_address(text: str) -> str:
    """주소에서 불필요한 레이블 제거 및 정리"""
    if not text:
        return ""
    
    # 여러 패턴 제거
    patterns = [
        r"^보관장소\s*[:：]\s*",
        r"^소재지\s*[:：]\s*",
        r"^\(보관장소\)\s*",
        r"\s*\(보관장소\)$",
        r"^\(소재지\)\s*",
        r"\s*\(소재지\)$",
        r"^본기계기구는",
        r"^본건은",
        r"^본건",
        r"^대상물건은",
        r"^대상물건",
    ]
    
    result = text
    for pat in patterns:
        result = re.sub(pat, "", result, flags=re.IGNORECASE).strip()
    
    # 접두사 제거
    result = re.sub(r'^(기계기구는|본건은|본건|대상물건은|대상물건)\s*', '', result)
    result = re.sub(r'^(본건|대상물건|기계기구|자동차|차량)\s*', '', result)
    
    # "본건은" 직접 제거
    if result.startswith('본건은 '):
        result = result[4:]
    elif result.startswith('본건은'):
        result = result[3:]
    
    # 제어 문자 제거 후 다시 접두사 확인
    clean_result = ''.join(char if not unicodedata.category(char).startswith('C') else ' ' for char in result)
    clean_result = re.sub(r'\s+', ' ', clean_result).strip()
    
    if clean_result.startswith('본건은 '):
        clean_result = clean_result[4:]
    elif clean_result.startswith('본건은'):
        clean_result = clean_result[3:]
    
    # 괄호 이후 불필요한 텍스트 제거 (주소의 지번과 동호수 등의 괄호 이전까지는 전부 기록)
    clean_result = re.sub(r'\)\s*(소재|내에소재함|번지도로명주소).*$', ')', clean_result)
    
    # 따옴표 안의 내용 제거 (예: " 자동차", "차량" 등)
    clean_result = re.sub(r'\s*"[^"]*"\s*$', '', clean_result)
    clean_result = re.sub(r'\s*"[^"]*"', '', clean_result)
    
    # 최종 정리
    clean_result = clean_result.strip()
    
    # 유효성 검사
    if not is_valid_address(clean_result):
        return ""
    
    return clean_result
