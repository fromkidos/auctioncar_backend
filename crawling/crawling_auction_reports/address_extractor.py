"""
주소 추출 관련 기능
"""
import re
from typing import List, Optional
import fitz
from utils import split_lines, clean_location_address, is_valid_address


class AddressExtractor:
    """주소 추출 클래스"""
    
    def __init__(self, doc: fitz.Document):
        self.doc = doc
        self.TITLE_KEYS = {
            "location": ["위치도", "위 치 도", "상세위치도", "상 세 위 치 도", "광역위치도", "광 역 위 치 도", "소재지", "소 재 지", "보관장소", "보관 장소", "차량보관장소", "차량 보관장소"],
        }
        self.KOREAN_COLON_PATTERN = re.compile(r'[:：]')
    
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
    
    def _extract_address_from_location_page(self, page_num: int) -> Optional[str]:
        """위치도 페이지에서 주소 추출"""
        # 모든 위치도 페이지 확인 (더 정확한 주소를 찾기 위해)
        location_pages = self._find_pages_by_titles(self.TITLE_KEYS["location"])
        
        address_candidates = []  # 모든 주소 후보를 저장
        
        for page_idx in location_pages:
            page = self.doc.load_page(page_idx)
            lines = split_lines(self._page_text(page_idx))
            
            # 1단계: "소재지", "보관장소" 키워드로 주소 찾기
            address_keywords = ['소재지', '소 재 지', '보관장소', '보관 장소', '차량보관장소', '차량 보관장소']
            
            for idx, line in enumerate(lines):
                ln = line.strip()
                if not ln:
                    continue
                    
                # 주소 키워드가 포함된 줄 찾기
                for keyword in address_keywords:
                    if keyword in ln:
                        # 콜론(:)으로 분리하여 주소 부분 추출
                        parts = re.split(self.KOREAN_COLON_PATTERN, ln, maxsplit=1)
                        if len(parts) == 2 and keyword in parts[0]:
                            address = parts[1].strip()
                            if address and len(address) > 5:
                                address_candidates.append(address)
                                continue
                        
                        # 콜론이 없는 경우, 다음 줄이 주소일 가능성 확인
                        if len(parts) == 1 and idx + 1 < len(lines):
                            next_line = lines[idx + 1].strip()
                            if next_line and len(next_line) > 5:
                                # 주소 패턴이 포함된 줄인지 확인
                                address_patterns = ['특별시', '광역시', '특별자치시', '특별자치도', '도', '시', '군', '구']
                                if any(pattern in next_line for pattern in address_patterns):
                                    address_candidates.append(next_line)
                                    continue
            
            # 2단계: 라벨 없이 직접 주소만 있는 경우 찾기
            address_patterns = ['특별시', '광역시', '특별자치시', '특별자치도', '도', '시', '군', '구']
            
            for idx, line in enumerate(lines):
                ln = line.strip()
                if not ln or len(ln) < 10:
                    continue
                
                # 주소 패턴이 포함된 줄 찾기
                if any(pattern in ln for pattern in address_patterns):
                    # 주소가 아닌 텍스트 제외 (더 강화된 필터링)
                    if not any(kw in ln for kw in ['자동차', '차량', '등록', '번호', '법원', '경매', '감정평가', '사무소', '과거', '해당', '위치도', '위 치 도', '원 내외로', '게시되어', '시세', '매매', '사이트']):
                        # 주소일 가능성 높은 줄 (더 엄격한 조건)
                        if any(kw in ln for kw in ['읍', '면', '동', '리', '로', '길', '번지']) and len(ln) > 10:
                            # "원"으로만 시작하는 줄은 제외
                            if not ln.strip().startswith('원'):
                                # 주소가 여러 줄에 걸쳐 있을 수 있으므로 다음 줄들도 확인
                                full_address = ln
                                
                                # 다음 줄들도 주소일 가능성 확인 (최대 3줄까지만)
                                for i in range(idx + 1, min(idx + 3, len(lines))):
                                    next_line = lines[i].strip()
                                    if not next_line:
                                        continue
                                    # 주소의 연속일 가능성이 있는 줄
                                    if not any(kw in next_line for kw in ['자동차', '차량', '등록', '번호', '법원', '경매', '감정평가', '사무소', '과거', '해당', '위치도', '위 치 도', '원 내외로', '게시되어', '시세', '매매', '사이트']):
                                        # 주소 키워드가 포함된 줄이면 주소의 연속으로 간주
                                        if any(kw in next_line for kw in ['읍', '면', '동', '리', '로', '길', '번지', '주차장', '빌딩', '센터', '타워']):
                                            full_address += " " + next_line
                                        elif re.match(r'^\d+', next_line):  # 숫자로 시작하는 줄 (번지수 등)
                                            full_address += " " + next_line
                                        elif next_line in ['(', ')', '-']:  # 단일 기호도 포함
                                            full_address += next_line
                                        else:
                                            break
                                    else:
                                        break
                                
                                address_candidates.append(full_address)
        
        # 가장 적합한 주소를 선택
        if address_candidates:
            # 페이지 번호가 가장 뒤에 있는 위치도 페이지의 주소를 우선 선택
            # (위치도 페이지는 본문 내용이 끝난 후에 나오므로 더 정확한 주소 정보를 담고 있음)
            return clean_location_address(address_candidates[-1])
        
        return None
    
    def _extract_address_from_entire_document(self) -> Optional[str]:
        """전체 문서에서 주소 추출 (위치도 페이지를 찾지 못한 경우)"""
        address_candidates = []
        address_keywords = ['특별시', '광역시', '특별자치시', '특별자치도', '도', '시', '군', '구', '읍', '면', '동', '리', '로', '길']
        location_keywords = ['보관장소', '소재지', '위치', '장소']
        
        # 모든 페이지에서 주소 후보 찾기
        for page_num in range(len(self.doc)):
            page = self.doc.load_page(page_num)
            lines = split_lines(self._page_text(page_num))
            
            for idx, line in enumerate(lines):
                ln = line.strip()
                if not ln or len(ln) < 10:
                    continue
                
                # 1) 위치 키워드가 포함된 경우 (보관장소, 소재지 등)
                has_location_keyword = any(kw in ln for kw in location_keywords)
                if has_location_keyword:
                    # 콜론으로 분리하여 주소 부분 추출
                    parts = re.split(r'[:：]', ln, maxsplit=1)
                    if len(parts) == 2:
                        address = parts[1].strip()
                        if address and len(address) > 5:
                            address_candidates.append((100, page_num, idx, address))  # 높은 점수
                    else:
                        # 콜론이 없는 경우, 괄호 안의 주소 추출 시도
                        bracket_match = re.search(r'\(([^)]*[가-힣][^)]*)\)', ln)
                        if bracket_match:
                            address = bracket_match.group(1).strip()
                            if address and len(address) > 5 and any(pattern in address for pattern in address_keywords):
                                address_candidates.append((95, page_num, idx, address))  # 높은 점수
                        else:
                            # 다음 줄이 주소일 가능성 확인
                            if idx + 1 < len(lines):
                                next_line = lines[idx + 1].strip()
                                if next_line and len(next_line) > 5:
                                    # 주소 패턴이 포함된 줄인지 확인
                                    if any(pattern in next_line for pattern in address_keywords):
                                        address_candidates.append((90, page_num, idx, next_line))  # 높은 점수
                
                # 2) 주소 키워드가 포함되어 있는 경우
                has_address_keyword = any(kw in ln for kw in address_keywords)
                if has_address_keyword and not has_location_keyword:
                    # 주소일 가능성 점수 계산
                    score = 0
                    score += len(ln)  # 길이
                    score += ln.count('(') * 10  # 괄호
                    score += len(re.findall(r'\d+-\d+', ln)) * 20  # 번지수 패턴
                    score += sum(1 for kw in address_keywords if kw in ln) * 5  # 주소 키워드 개수
                    
                    # 주소가 아닌 텍스트 제외
                    exclude_patterns = ['자동차', '차량', '등록', '번호', '법원', '경매', '감정평가', '사무소', '과거', '해당']
                    if not any(pattern in ln for pattern in exclude_patterns):
                        address_candidates.append((score, page_num, idx, ln))
        
        # 점수가 가장 높은 주소 선택
        if address_candidates:
            address_candidates.sort(key=lambda x: x[0], reverse=True)
            best_address = address_candidates[0][3]
            return clean_location_address(best_address)
        
        return None
    
    def extract_location_address(self) -> Optional[str]:
        """주소 추출 메인 메서드"""
        # 1단계: 위치도 페이지에서 주소 찾기
        location_pages = self._find_pages_by_titles(self.TITLE_KEYS["location"])
        
        if location_pages:
            address = self._extract_address_from_location_page(location_pages[0])
            if address:
                return address
        
        # 2단계: 전체 파일에서 주소 찾기 (위치도 페이지를 찾지 못한 경우)
        return self._extract_address_from_entire_document()
