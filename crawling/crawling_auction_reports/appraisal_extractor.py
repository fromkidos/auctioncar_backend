"""
감정평가 필드 추출 관련 기능
"""
import re
from typing import List, Optional
import fitz
from .utils import split_lines, clean_text
from .models import AppraisalFields


class AppraisalExtractor:
    """감정평가 필드 추출 클래스"""
    
    def __init__(self, doc: fitz.Document, is_text_based: bool):
        self.doc = doc
        self.is_text_based = is_text_based
        self.TITLE_KEYS = {
            "appraisal": ["감정평가요항표", "감정평가 요항표", "자동차감정평가요항표", "자동차 감정평가요항표", "자동차 감정평가 요항표", "감정평가 요항 표", "선박감정평가요항표", "선박 감정평가요항표", "선박 감정평가 요항표"],
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
    
    def _page_text(self, page_index: int) -> str:
        """페이지 텍스트 추출"""
        page = self.doc.load_page(page_index)
        return page.get_text("text")
    
    def _extract_value_from_lines(self, lines: List[str], key_regex: str) -> Optional[str]:
        """라인들에서 키워드에 해당하는 값 추출"""
        for line in lines:
            match = re.search(key_regex, line, re.IGNORECASE)
            if match:
                # 키워드 이후의 텍스트 추출
                value = line[match.end():].strip()
                if value:
                    return clean_text(value)
        return None
    
    def _extract_car_appraisal(self, pages: List[int]) -> AppraisalFields:
        """자동차 감정평가 필드 추출"""
        result = AppraisalFields(type="car")
        
        # 모든 관련 페이지에서 텍스트 수집
        all_text = ""
        for page_num in pages:
            page_text = self._page_text(page_num)
            all_text += page_text + "\n"
        
        lines = split_lines(all_text)
        
        # 헤더 패턴들
        header_patterns = {
            'year_and_mileage': r'(?:년식|연식).*?(?:및|및\s*주행거리)',
            'color': r'색상',
            'condition': r'관리상태',
            'fuel': r'사용연료',
            'inspection_validity': r'(?:유효검사기간|검사유효기간|수용장소\s*및\s*검사유효기간)',
            'etc': r'기타'
        }
        
        # 각 필드별로 추출
        for field, pattern in header_patterns.items():
            content_lines = []
            in_section = False
            current_header = None
            
            for idx, line in enumerate(lines):
                line = line.strip()
                if not line:
                    continue
                
                # 헤더 매칭 확인
                header_match = re.search(pattern, line, re.IGNORECASE)
                if header_match:
                    # 여러 항목이 한 줄에 나열된 페이지 헤더 건너뛰기 (예: "(1) 년식 (2) 색상 (3) 관리상태")
                    # 괄호 안에 숫자가 3개 이상 있는 경우만 페이지 헤더로 간주
                    norm = re.sub(r'\s+', '', line)
                    number_patterns = re.findall(r'\(\s*\d+\s*\)', norm)
                    if len(number_patterns) >= 3:  # 3개 이상의 번호 패턴이 있으면 페이지 헤더로 간주
                        continue
                    
                    current_header = field
                    in_section = True
                    continue
                
                if in_section and current_header == field:
                    # 페이지 헤더나 메타데이터 제외
                    norm = re.sub(r'\s+', '', line.lower())
                    if any(keyword in norm for keyword in ['page :', 'dp', '자동차감정평가요항표', '감정평가사무소']):
                        continue
                    
                    # 다음 헤더가 나오는지 확인
                    next_header_found = False
                    for other_field, other_pattern in header_patterns.items():
                        if other_field != field and re.search(other_pattern, line, re.IGNORECASE):
                            next_header_found = True
                            break
                    
                    if next_header_found:
                        in_section = False
                        current_header = None
                        continue
                    
                    # 내용 라인 추가
                    if line and len(line) > 3:
                        content_lines.append(line)
            
            # 필드에 값 설정
            if content_lines:
                result.__dict__[field] = "\n".join(content_lines)
        
        return result
    
    def _extract_ship_appraisal(self, pages: List[int]) -> AppraisalFields:
        """선박 감정평가 필드 추출"""
        result = AppraisalFields(type="ship")
        
        # 모든 관련 페이지에서 텍스트 수집
        all_text = ""
        for page_num in pages:
            page_text = self._page_text(page_num)
            all_text += page_text + "\n"
        
        lines = split_lines(all_text)
        
        # 선박 헤더 패턴들
        header_patterns = {
            'hull_status': r'(?:선체상태|선체\s*상태)',
            'engine_status': r'(?:기관상태|기관\s*상태)',
            'equipment_status': r'(?:장비상태|장비\s*상태)',
            'operation_info': r'(?:운항정보|운항\s*정보)',
            'inspection_location': r'(?:검사장소|검사\s*장소)',
            'ship_etc': r'기타'
        }
        
        # 각 필드별로 추출
        for field, pattern in header_patterns.items():
            content_lines = []
            in_section = False
            current_header = None
            
            for idx, line in enumerate(lines):
                line = line.strip()
                if not line:
                    continue
                
                # 페이지 번호 정보 제외
                norm = re.sub(r'\s+', '', line.lower())
                if re.match(r"^page\s*:\s*\d+", norm, re.IGNORECASE):
                    continue
                if re.match(r"^\d+\s*/\s*\d+$", norm):  # "1 / 13" 형태
                    continue
                if re.match(r"^[A-Z]\d{8}$", norm):  # "F24102501" 형태의 문서 번호
                    continue
                # 페이지 헤더/푸터 정보 제외
                if norm in ["Page : 1", "Page : 2", "Page : 3", "Page : 4", "Page : 5"]:
                    continue
                
                # 헤더 매칭 확인
                header_match = re.search(pattern, line, re.IGNORECASE)
                if header_match:
                    current_header = field
                    in_section = True
                    continue
                
                if in_section and current_header == field:
                    # 페이지 헤더나 메타데이터 제외
                    if any(keyword in norm for keyword in ['page :', 'dp', '선박감정평가요항표', '감정평가사무소']):
                        continue
                    
                    # 다음 헤더가 나오는지 확인
                    next_header_found = False
                    for other_field, other_pattern in header_patterns.items():
                        if other_field != field and re.search(other_pattern, line, re.IGNORECASE):
                            next_header_found = True
                            break
                    
                    if next_header_found:
                        in_section = False
                        current_header = None
                        continue
                    
                    # 내용 라인 추가
                    if line and len(line) > 3:
                        content_lines.append(line)
            
            # 필드에 값 설정
            if content_lines:
                result.__dict__[field] = "\n".join(content_lines)
        
        return result
    
    def extract_appraisal_fields(self) -> AppraisalFields:
        """감정평가 필드 추출 메인 메서드"""
        # 감정평가 페이지 찾기
        appraisal_pages = self._find_pages_by_titles(self.TITLE_KEYS["appraisal"])
        
        if not appraisal_pages:
            return AppraisalFields(type="unknown")
        
        # 가장 적합한 페이지 선택 (키워드가 가장 많은 페이지)
        best_page = appraisal_pages[0]
        max_keywords = 0
        
        for page_num in appraisal_pages:
            page_text = self._page_text(page_num)
            keyword_count = sum(1 for keyword in ['년식', '연식', '색상', '관리상태', '사용연료', '유효검사기간', '기타'] if keyword in page_text)
            if keyword_count > max_keywords:
                max_keywords = keyword_count
                best_page = page_num
        
        # 자동차 vs 선박 구분
        page_text = self._page_text(best_page)
        
        if any(keyword in page_text for keyword in ['선박', '선체', '기관', '장비', '운항']):
            return self._extract_ship_appraisal(appraisal_pages)
        else:
            return self._extract_car_appraisal(appraisal_pages)
