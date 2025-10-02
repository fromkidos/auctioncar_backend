import json
import os
import re
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple

import fitz  # PyMuPDF
from PIL import Image, ImageChops  # Pillow for trimming borders


KOREAN_COLON_PATTERN = r"[:：]\s*"


def normalize_for_match(text: str) -> str:
    """한글 섹션/키워드 매칭을 위해 공백/줄바꿈/탭 제거 및 전각콜론 통일."""
    if text is None:
        return ""
    return re.sub(r"\s+", "", text).replace("：", ":").strip()


def split_lines(text: str) -> List[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def trim_image_whitespace(image_path: str, tolerance: int = 6) -> None:
    """흰색(또는 유사 흰색) 여백을 자동 크롭. 원본 파일을 덮어씀.

    tolerance: 배경과의 허용 오차 (0~255). 값이 클수록 더 많은 영역을 여백으로 판단.
    """
    try:
        with Image.open(image_path) as im:
            if im.mode not in ("RGB", "RGBA"):
                im = im.convert("RGB")
            # 배경색을 좌상단 픽셀로 가정 (흰색 배경 문서에 유효)
            bg_color = im.getpixel((0, 0))
            if isinstance(bg_color, tuple) and len(bg_color) == 4:
                bg_color = bg_color[:3]

            bg = Image.new("RGB", im.size, bg_color)
            diff = ImageChops.difference(im.convert("RGB"), bg)
            # tolerance 적용: diff를 확장하여 근사 흰색까지 포함
            bbox = diff.convert("L").point(lambda p: 255 if p > tolerance else 0).getbbox()
            if bbox:
                cropped = im.crop(bbox)
                cropped.save(image_path)
    except Exception:
        # 트림 실패 시 조용히 무시 (원본 유지)
        pass


def crop_image_edges(image_path: str, pixels: int = 1) -> None:
    """이미지의 가장자리 픽셀을 균일하게 잘라냄. 원본 파일을 덮어씀."""
    try:
        with Image.open(image_path) as im:
            width, height = im.size
            if width > pixels * 2 and height > pixels * 2:
                cropped = im.crop((pixels, pixels, width - pixels, height - pixels))
                cropped.save(image_path)
    except Exception:
        # 크롭 실패 시 조용히 무시
        pass


@dataclass
class AppraisalFields:
    """자동차 또는 선박 감정평가 필드. type 필드로 구분."""
    type: str = "unknown"  # "car" 또는 "ship"
    
    # 자동차 필드
    year_and_mileage: Optional[str] = None  # 년식 및 주행거리
    color: Optional[str] = None            # 색상
    condition: Optional[str] = None        # 관리상태
    fuel: Optional[str] = None             # 사용연료
    inspection_validity: Optional[str] = None  # 유효검사기간
    etc: Optional[str] = None              # 기타
    
    # 선박 필드
    hull_status: Optional[str] = None      # 선체의 현황
    engine_status: Optional[str] = None    # 기관의 현황
    equipment_status: Optional[str] = None # 의장품의 현황
    operation_info: Optional[str] = None   # 운항사항
    inspection_location: Optional[str] = None  # 실사장소
    ship_etc: Optional[str] = None         # 기타 참고사항


@dataclass
class ReportExtractionResult:
    pdf_filename: str
    appraisal: AppraisalFields
    location_address: Optional[str]
    photos_saved: List[str]


class ReportParser:
    """
    법원 경매 차량 감정평가서 PDF에서 필요한 정보를 추출하는 파서.

    - "감정평가요항표" 페이지: 년식 및 주행거리, 색상, 관리상태, 사용연료, 유효검사기간, 기타
    - "위 치 도" 페이지: 소재지
    - "사 진 용 지" 페이지: 첨부 사진 추출
    """

    TITLE_KEYS = {
        "appraisal": ["감정평가요항표", "감정평가 요항표", "자동차감정평가요항표", "자동차 감정평가요항표", "자동차 감정평가 요항표", "감정평가 요항 표", "선박감정평가요항표", "선박 감정평가요항표", "선박 감정평가 요항표"],
        "location": ["위치도", "위 치 도", "상세위치도", "상 세 위 치 도", "광역위치도", "광 역 위 치 도", "소재지", "소 재 지", "보관장소", "보관 장소", "차량보관장소", "차량 보관장소"],
        "photos": ["사진용지", "사 진 용 지"],
    }

    FIELD_PATTERNS: List[Tuple[str, str]] = [
        ("year_and_mileage", r"년식\s*및\s*주행거리"),
        ("color", r"색상"),
        ("condition", r"관리상태"),
        ("fuel", r"사용연료"),
        ("inspection_validity", r"유효검사기간"),
        ("etc", r"기타"),
    ]

    def __init__(self, pdf_path: str, output_root: Optional[str] = None) -> None:
        self.pdf_path = pdf_path
        self.doc = fitz.open(pdf_path)
        base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        default_root = os.path.join(
            os.path.dirname(os.path.abspath(pdf_path)), "extracted", base_name
        )
        self.output_root = output_root or default_root
        ensure_dir(self.output_root)
        # PDF 파일명에서 경매번호 추출 (언더스코어 앞 부분)
        # 예: "2024타경102980-1_감정평가서" -> "2024타경102980-1"
        self.auction_no = base_name.split("_")[0]
        
        # PDF 타입 판단 (텍스트 기반 vs 스캔 이미지 기반)
        self.is_text_based = self._detect_pdf_type()
    
    def _detect_pdf_type(self) -> bool:
        """PDF가 텍스트 기반인지 스캔(이미지) 기반인지 판단.
        
        Returns:
            True: 텍스트 기반 PDF (텍스트 추출 가능)
            False: 스캔/이미지 기반 PDF (OCR 필요, 텍스트 검색 불가)
        """
        # 처음 3페이지를 샘플링하여 판단
        sample_pages = min(3, len(self.doc))
        total_text_length = 0
        total_image_blocks = 0
        
        for page_num in range(sample_pages):
            page = self.doc.load_page(page_num)
            
            # 텍스트 추출
            text = page.get_text("text").strip()
            total_text_length += len(text)
            
            # 이미지 블록 수
            data = page.get_text("rawdict")
            image_blocks = [b for b in data.get("blocks", []) if b.get("type") == 1]
            total_image_blocks += len(image_blocks)
        
        # 판단 기준:
        # 텍스트가 거의 없고 (평균 100자 미만/페이지) 이미지 블록이 많으면 (10개 이상/페이지) → 스캔본
        avg_text_per_page = total_text_length / sample_pages
        avg_images_per_page = total_image_blocks / sample_pages
        
        is_scanned = avg_text_per_page < 100 and avg_images_per_page >= 10
        
        return not is_scanned

    def _page_text(self, page_index: int) -> str:
        page = self.doc.load_page(page_index)
        return page.get_text("text") or ""

    def _find_pages_by_titles(self, title_candidates: List[str]) -> List[int]:
        """타이틀 후보 중 하나라도 포함되는 페이지 인덱스 목록 반환 (공백 무시 일치)."""
        want = [normalize_for_match(t) for t in title_candidates]
        matched_pages: List[int] = []
        for i in range(self.doc.page_count):
            raw = self._page_text(i)
            norm = normalize_for_match(raw)
            if any(t in norm for t in want):
                matched_pages.append(i)
        return matched_pages

    # ---------- 좌표 기반 텍스트 추출 유틸 ----------
    def _find_keyword_span_bbox(self, page: fitz.Page, key_regex: str) -> Optional[fitz.Rect]:
        """페이지 내 키워드(정규식)에 해당하는 첫 span의 bbox 반환."""
        data = page.get_text("rawdict")
        pattern = re.compile(key_regex)
        for block in data.get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "")
                    if pattern.search(normalize_for_match(text)):
                        bbox = span.get("bbox")
                        if bbox and len(bbox) == 4:
                            return fitz.Rect(bbox)
        return None

    def _find_all_keyword_spans(self, page: fitz.Page, key_regex: str) -> List[fitz.Rect]:
        """페이지 내 키워드(정규식)에 해당하는 모든 span bbox 목록."""
        data = page.get_text("rawdict")
        pattern = re.compile(key_regex)
        rects: List[fitz.Rect] = []
        for block in data.get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "")
                    if pattern.search(normalize_for_match(text)):
                        bbox = span.get("bbox")
                        if bbox and len(bbox) == 4:
                            rects.append(fitz.Rect(bbox))
        return rects

    def _extract_right_text_of_keyword(self, page: fitz.Page, key_regex: str) -> Optional[str]:
        """키워드의 우측 직사각형 영역에서 텍스트를 추출. 없으면 None."""
        bbox = self._find_keyword_span_bbox(page, key_regex)
        if not bbox:
            return None
        # 키워드 우측 영역 (같은 행 높이에서 페이지 오른쪽까지)
        rect = fitz.Rect(bbox.x1 + 2, bbox.y0 - 1, page.rect.x1 - 2, bbox.y1 + 1)
        text = page.get_textbox(rect).strip()
        if text:
            return text
        # 같은 블록 내 다음 줄 영역(키워드 아래)까지 느슨하게 확대
        loose_rect = fitz.Rect(bbox.x1 + 2, bbox.y0 - 1, page.rect.x1 - 2, bbox.y0 + 40)
        text = page.get_textbox(loose_rect).strip()
        return text or None

    def _extract_right_text_of_keyword_below(self, page: fitz.Page, key_regex: str, min_y_ratio: float = 0.25) -> Optional[str]:
        """페이지 상단 특정 비율(min_y_ratio) 아래에서만 키워드를 찾아 우측 텍스트 추출."""
        data = page.get_text("rawdict")
        pattern = re.compile(key_regex)
        y_min = page.rect.height * min_y_ratio
        for block in data.get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "")
                    if not text:
                        continue
                    if not pattern.search(normalize_for_match(text)):
                        continue
                    bbox = span.get("bbox")
                    if not bbox or len(bbox) != 4:
                        continue
                    rect = fitz.Rect(bbox)
                    if rect.y0 <= y_min:
                        # 상단 머리글/테이블의 키워드는 무시
                        continue
                    roi = fitz.Rect(rect.x1 + 2, rect.y0 - 1, page.rect.x1 - 2, rect.y1 + 1)
                    out = page.get_textbox(roi).strip()
                    if out:
                        return out
                    loose = fitz.Rect(rect.x1 + 2, rect.y0 - 1, page.rect.x1 - 2, rect.y0 + 80)
                    out = page.get_textbox(loose).strip()
                    if out:
                        return out
        return None

    def _iter_line_texts(self, page: fitz.Page) -> List[Tuple[str, fitz.Rect]]:
        """rawdict 기반으로 각 라인의 전체 텍스트와 라인 bbox(스팬 합집합)를 반환."""
        lines_out: List[Tuple[str, fitz.Rect]] = []
        data = page.get_text("rawdict")
        for block in data.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                text_parts: List[str] = []
                bbox_union: Optional[fitz.Rect] = None
                for span in line.get("spans", []):
                    t = span.get("text", "")
                    if t:
                        text_parts.append(t)
                    bbox = span.get("bbox")
                    if bbox and len(bbox) == 4:
                        rect = fitz.Rect(bbox)
                        bbox_union = rect if bbox_union is None else bbox_union | rect
                full_text = ("".join(text_parts)).strip()
                if full_text and bbox_union is not None:
                    lines_out.append((full_text, bbox_union))
        return lines_out

    def _find_section_headers(self, page: fitz.Page) -> List[Tuple[str, fitz.Rect]]:
        """감정평가요항표 섹션 헤더 라인만 정확히 식별.

        - 라인 전체 텍스트 기준으로 매칭
        - 같은 라인에 다른 번호가 함께 있으면(예: (1)(2)(3)...) 제외
        - 라인 길이 제한으로 헤더 행만 선택
        """
        patterns: List[Tuple[str, re.Pattern]] = [
            ("year_and_mileage", re.compile(r"^\(\s*1\s*\)\s*년식\s*및\s*주행거리")),
            ("color", re.compile(r"^\(\s*2\s*\)\s*색상")),
            ("condition", re.compile(r"^\(\s*3\s*\)\s*관리상태")),
            ("fuel", re.compile(r"^\(\s*4\s*\)\s*사용연료")),
            ("inspection_validity", re.compile(r"^\(\s*5\s*\)\s*유효검사기간")),
            ("etc", re.compile(r"^\(\s*6\s*\)\s*기타(\s*\(옵션등\)\s*)?")),
        ]

        headers: List[Tuple[str, fitz.Rect]] = []
        for full_text, rect in self._iter_line_texts(page):
            norm = normalize_for_match(full_text)
            # 너무 긴 라인은 스킵 (테이블 머리글 등)
            if len(norm) > 50:  # 여유롭게
                continue
            # 한 라인에 번호가 2개 이상 등장하면 스킵
            if len(re.findall(r"\(\s*\d\s*\)", norm)) > 1:
                continue
            for key, pat in patterns:
                if pat.match(norm):
                    headers.append((key, rect))
                    break
        headers.sort(key=lambda x: x[1].y0)
        return headers

    # ---------- 사진용지 판별 ----------
    def _is_photos_page(self, page: fitz.Page) -> bool:
        """사진용지 판별: PDF 타입에 따라 다른 전략 사용."""
        
        # 텍스트 기반 PDF: "사 진 용 지" 텍스트로 판별
        if self.is_text_based:
            # get_text("text")로 간단하게 확인
            text = page.get_text("text")
            norm_text = normalize_for_match(text)
            
            # "사진용지" 키워드가 있고 "참조" 컨텍스트가 아닌 경우
            if "사진용지" in norm_text and "참조" not in norm_text:
                # 추가 검증: 실제 이미지 블록이 있는지 확인
                # 감정평가요항표 페이지에 "사진용지" 텍스트가 포함된 경우를 방지
                blocks = self._iter_image_blocks(page)
                if len(blocks) > 0:
                    return True
                # 이미지 블록이 없으면 감정평가요항표 페이지일 가능성이 높음
                if "감정평가요항표" in norm_text:
                    return False
                # "사진용지"가 타이틀로 단독으로 있으면 사진용지 페이지
                lines = [l.strip() for l in text.split('\n') if l.strip()]
                if lines and "사진용지" in lines[0] and len(lines[0]) < 30:
                    return True
                return False
            
            return False
        
        # 스캔본 PDF: 사진 페이지 감지 안 함 (모든 페이지가 이미지이므로)
        # OCR 없이는 판별 불가능
        else:
            return False

    def _extract_value_from_lines(self, lines: List[str], key_regex: str) -> Optional[str]:
        """키 정규식에 해당하는 라인에서 값 추정. 같은 줄의 콜론 뒤 또는 다음 줄 사용."""
        key_pattern = re.compile(key_regex)
        for idx, line in enumerate(lines):
            # 우선 공백 제거 후 키워드 포함 여부 확인(강건성 ↑)
            if not key_pattern.search(normalize_for_match(line)):
                continue

            # 같은 줄 콜론 뒤 값
            same_line_match = re.split(KOREAN_COLON_PATTERN, line, maxsplit=1)
            if len(same_line_match) == 2 and key_pattern.search(normalize_for_match(same_line_match[0])):
                value = same_line_match[1].strip()
                if value:
                    return value

            # 다음 줄 값
            if idx + 1 < len(lines):
                nxt = lines[idx + 1].strip()
                if nxt:
                    return nxt
        return None

    def extract_appraisal_fields(self) -> AppraisalFields:
        pages = self._find_pages_by_titles(self.TITLE_KEYS["appraisal"])
        if not pages:
            return AppraisalFields()

        # 여러 페이지가 발견되면, 실제 감정평가요항표 내용이 있는 페이지를 선택
        best_page = pages[0]
        full_text = self._page_text(best_page)
        
        # 자동차 vs 선박 구분
        is_car = any(keyword in full_text for keyword in ["년식", "연식", "주행거리", "사용연료"])
        is_ship = any(keyword in full_text for keyword in ["선체의 현황", "기관의 현황", "의장품", "운항사항"])
        
        if is_ship and not is_car:
            return self._extract_ship_appraisal(pages)
        else:
            return self._extract_car_appraisal(pages)
    
    def _extract_car_appraisal(self, pages: List[int]) -> AppraisalFields:
        """자동차 감정평가 필드 추출 (여러 페이지에 걸쳐 있을 수 있음)"""
        # 관련 페이지 수집 (감정평가요항표 관련 키워드가 있는 페이지)
        relevant_pages = set(pages)
        for page_num in range(len(self.doc)):
            text = self._page_text(page_num)
            # 자동차 감정평가 관련 키워드 확인
            keywords_found = sum([
                1 if "년식" in text or "연식" in text else 0,
                1 if "주행거리" in text else 0,
                1 if "색상" in text else 0,
                1 if "관리상태" in text else 0,
                1 if "사용연료" in text else 0,
                1 if "검사" in text and "기간" in text else 0,
            ])
            # 3개 이상 키워드가 있으면 관련 페이지로 간주
            if keywords_found >= 3:
                relevant_pages.add(page_num)
        
        # 모든 관련 페이지의 텍스트를 순서대로 합치기
        all_lines = []
        for page_idx in sorted(relevant_pages):
            text = self._page_text(page_idx)
            all_lines.extend(split_lines(text))
        
        results: Dict[str, Optional[str]] = {
            "year_and_mileage": None,
            "color": None,
            "condition": None,
            "fuel": None,
            "inspection_validity": None,
            "etc": None,
        }
        
        lines = all_lines
        
        # 각 섹션 헤더의 발생을 찾아 해당 인덱스 저장
        header_patterns = [
            ("year_and_mileage", re.compile(r"^(\(\s*1\s*\)|1\s*\.)\s*(년식|연식).*(및\s*)?(주행거리)\s*$")),
            ("color", re.compile(r"^(\(\s*2\s*\)|2\s*\.)\s*색\s*상\s*$")),
            ("condition", re.compile(r"^(\(\s*3\s*\)|3\s*\.)\s*관\s*리\s*상\s*태\s*$")),
            ("fuel", re.compile(r"^(\(\s*4\s*\)|4\s*\.)\s*사용\s*연료\s*$")),
            ("inspection_validity", re.compile(r"^(\(\s*5\s*\)|5\s*\.)\s*(유효\s*검사\s*기간|검사\s*유효\s*기간|수용\s*장소.*검사\s*유효\s*기간)\s*$")),
            ("etc", re.compile(r"^(\(\s*6\s*\)|6\s*\.)\s*기\s*타.*$")),
        ]
        
        header_indices: List[Tuple[str, int]] = []
        for key, pattern in header_patterns:
            matches = []
            for idx, line in enumerate(lines):
                norm = normalize_for_match(line)
                if pattern.match(norm):
                    # 다른 항목 번호가 같은 줄에 없는지 확인 (단독 헤더만 선택)
                    has_other_numbers = False
                    for other_num in [1, 2, 3, 4, 5, 6]:
                        # 현재 헤더의 번호는 제외
                        current_num = int(re.search(r'\d+', pattern.pattern).group())
                        if other_num == current_num:
                            continue
                        # 다른 번호가 있는지 확인
                        if re.search(rf'\(\s*{other_num}\s*\)', norm):
                            has_other_numbers = True
                            break
                    
                    if not has_other_numbers:
                        matches.append(idx)
            
            # 가장 마지막 매칭을 사용 (본문 헤더가 보통 마지막에 위치)
            if matches:
                header_indices.append((key, matches[-1]))
        
        header_indices.sort(key=lambda x: x[1])
        
        # 각 헤더 다음 줄부터 다음 헤더 전까지 추출
        for i, (key, start_idx) in enumerate(header_indices):
            content_start = start_idx + 1
            if i + 1 < len(header_indices):
                content_end = header_indices[i + 1][1]
            else:
                content_end = len(lines)
            
            # 현재 헤더의 번호 추출
            current_header_line = lines[start_idx]
            current_num_match = re.search(r'\((\d+)\)', normalize_for_match(current_header_line))
            current_num = int(current_num_match.group(1)) if current_num_match else 0
            
            content_lines = []
            for idx in range(content_start, content_end):
                if idx >= len(lines):
                    break
                ln = lines[idx].strip()
                if not ln:
                    continue
                norm = normalize_for_match(ln)
                
                # 페이지 구분선 (푸터/헤더)는 건너뛰기
                if "감정평가" in norm and "사무소" in norm:
                    continue
                if re.match(r"^page\s*:\s*\d+$", norm, re.IGNORECASE):
                    continue
                if norm.upper().startswith("DP") and re.search(r'\d{6}', norm):  # DP250103-001 같은 문서번호
                    continue
                if "자동차감정평가요항표" in norm or "선박감정평가요항표" in norm:
                    continue
                # 여러 항목이 한 줄에 나열된 페이지 헤더 건너뛰기 (예: "(1) 년식 (2) 색상 (3) 관리상태")
                # 괄호 안에 숫자가 3개 이상 있는 경우만 페이지 헤더로 간주
                number_patterns = re.findall(r'\(\s*\d+\s*\)', norm)
                if len(number_patterns) >= 3:  # 3개 이상의 번호 패턴이 있으면 페이지 헤더로 간주
                    continue
                # 페이지 헤더 패턴 확인 (여러 항목이 한 줄에 나열된 경우)
                if any(keyword in norm for keyword in ['(2) 색상', '(3) 관리상태', '(4) 사용연료', '(5) 유효검사기간', '(6) 기타']):
                    continue
                
                # 다음 섹션 헤더가 나오면 중단 (현재 번호보다 큰 번호만)
                next_header_match = re.search(r'\((\d+)\)', norm)
                if next_header_match:
                    next_num = int(next_header_match.group(1))
                    # 현재 번호보다 큰 번호가 나오면 중단
                    if next_num > current_num:
                        break
                    # 현재 번호 이하는 무시 (페이지 헤더에 여러 번호가 함께 있을 수 있음)
                    continue
                
                content_lines.append(ln)
            
            if content_lines:
                results[key] = "\n".join(content_lines)

        return AppraisalFields(
            type="car",
            year_and_mileage=results.get("year_and_mileage"),
            color=results.get("color"),
            condition=results.get("condition"),
            fuel=results.get("fuel"),
            inspection_validity=results.get("inspection_validity"),
            etc=results.get("etc"),
        )
    
    def _extract_ship_appraisal(self, pages: List[int]) -> AppraisalFields:
        """선박 감정평가 필드 추출 (여러 페이지에 걸쳐 있을 수 있음)"""
        # 관련 페이지 수집
        relevant_pages = set(pages)
        for page_num in range(len(self.doc)):
            text = self._page_text(page_num)
            if any(kw in text for kw in ["선체의 현황", "기관의 현황", "주기관의 현황", "의장품의 현황", "운항", "실사장소"]):
                relevant_pages.add(page_num)
        
        # 모든 관련 페이지의 텍스트를 순서대로 합치기
        all_lines = []
        for page_idx in sorted(relevant_pages):
            text = self._page_text(page_idx)
            all_lines.extend(split_lines(text))
        
        lines = all_lines
        
        results: Dict[str, Optional[str]] = {
            "hull_status": None,
            "engine_status": None,
            "equipment_status": None,
            "operation_info": None,
            "inspection_location": None,
            "ship_etc": None,
        }
        
        # 선박 감정평가 헤더 패턴 (숫자 헤더)
        header_patterns = [
            ("hull_status", re.compile(r"^(\(\s*1\s*\)|1\s*\.)\s*선\s*체.*현\s*황")),
            ("engine_status", re.compile(r"^(\(\s*2\s*\)|2\s*\.)\s*(주\s*기\s*관|기\s*관).*현\s*황")),
            ("equipment_status", re.compile(r"^(\(\s*3\s*\)|3\s*\.)\s*(보조\s*기\s*관\s*및\s*)?의\s*장\s*품.*현\s*황")),
            ("operation_info", re.compile(r"^(\(\s*4\s*\)|4\s*\.)\s*운\s*항(\s*상\s*황|\s*사\s*항)")),
            ("inspection_location", re.compile(r"^(\(\s*5\s*\)|5\s*\.)\s*(실\s*사\s*장\s*소|기\s*타)")),
            ("ship_etc", re.compile(r"^(\(\s*6\s*\)|6\s*\.)\s*기\s*타")),
        ]
        
        # 요약 라벨 패턴 (테이블 형식 PDF용)
        summary_patterns = [
            ("hull_status", re.compile(r"^선\s*체\s*현\s*황")),
            ("engine_status", re.compile(r"^(주\s*기\s*관|기\s*관)\s*현\s*황")),
            ("equipment_status", re.compile(r"^(보조\s*기\s*관\s*및\s*)?의\s*장\s*품.*현\s*황")),
            ("operation_info", re.compile(r"^운\s*항\s*(상\s*황|사\s*항)")),
            ("inspection_location", re.compile(r"^실\s*사\s*장\s*소")),
        ]
        
        header_indices: List[Tuple[str, int]] = []
        
        # 1) 먼저 숫자 헤더로 찾기
        for key, pattern in header_patterns:
            matches = []
            for idx, line in enumerate(lines):
                norm = normalize_for_match(line)
                if pattern.match(norm):
                    matches.append(idx)
            # 두 번째 발생이 있으면 선택, 없으면 첫 번째
            if len(matches) >= 2:
                header_indices.append((key, matches[1]))
            elif len(matches) == 1:
                header_indices.append((key, matches[0]))
        
        # 2) 숫자 헤더를 찾은 경우, 요약 라벨을 찾아서 실제 내용 시작 위치 조정
        if header_indices:
            adjusted_indices: List[Tuple[str, int]] = []
            for key, start_idx in header_indices:
                # 해당 헤더 다음에 요약 라벨이 있는지 확인
                found_summary = False
                for summary_key, summary_pattern in summary_patterns:
                    if summary_key == key:
                        # 헤더 다음 최대 20줄 내에서 요약 라벨 찾기
                        for idx in range(start_idx + 1, min(start_idx + 20, len(lines))):
                            norm = normalize_for_match(lines[idx])
                            if summary_pattern.match(norm):
                                adjusted_indices.append((key, idx))
                                found_summary = True
                                break
                        break
                
                if not found_summary:
                    adjusted_indices.append((key, start_idx))
            
            header_indices = adjusted_indices
        
        header_indices.sort(key=lambda x: x[1])
        
        # 각 헤더 다음 줄부터 다음 헤더 전까지 추출
        for i, (key, start_idx) in enumerate(header_indices):
            content_start = start_idx + 1
            if i + 1 < len(header_indices):
                content_end = header_indices[i + 1][1]
            else:
                content_end = len(lines)
            
            content_lines = []
            for idx in range(content_start, content_end):
                if idx >= len(lines):
                    break
                ln = lines[idx].strip()
                if not ln:
                    continue
                norm = normalize_for_match(ln)
                # 다음 숫자 헤더는 제외
                if re.match(r"^(\(\s*\d+\s*\)|\d+\.)", norm):
                    break
                # 페이지 하단 감정평가 사무소명 등은 제외
                if "감정평가" in norm and "사무소" in norm:
                    break
                # 페이지 번호 정보 제외
                if re.match(r"^page\s*:\s*\d+", norm, re.IGNORECASE):
                    continue
                if re.match(r"^\d+\s*/\s*\d+$", norm):  # "1 / 13" 형태
                    continue
                if re.match(r"^[A-Z]\d{8}$", norm):  # "F24102501" 형태의 문서 번호
                    continue
                # 페이지 헤더/푸터 정보 제외
                if norm in ["Page : 1", "Page : 2", "Page : 3", "Page : 4", "Page : 5"]:
                    continue
                content_lines.append(ln)
            
            if content_lines:
                results[key] = "\n".join(content_lines)

        return AppraisalFields(
            type="ship",
            hull_status=results.get("hull_status"),
            engine_status=results.get("engine_status"),
            equipment_status=results.get("equipment_status"),
            operation_info=results.get("operation_info"),
            inspection_location=results.get("inspection_location"),
            ship_etc=results.get("ship_etc"),
        )

    def extract_location_address(self) -> Optional[str]:
        """주소 추출: 1) 위치도 페이지에서 찾기, 2) 전체 파일에서 찾기"""
        
        # 1단계: 위치도 페이지 찾기
        location_pages = self._find_pages_by_titles(self.TITLE_KEYS["location"])
        
        if location_pages:
            # 위치도 페이지에서 주소 찾기
            address = self._extract_address_from_location_page(location_pages[0])
            if address:
                return address
        
        # 2단계: 전체 파일에서 주소 찾기 (위치도 페이지를 찾지 못한 경우)
        return self._extract_address_from_entire_document()
    
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
                        parts = re.split(KOREAN_COLON_PATTERN, ln, maxsplit=1)
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
                    
                        # 다음 줄들도 주소일 가능성 확인 (여러 줄에 걸친 주소 처리)
                        if len(parts) == 2 and idx + 1 < len(lines):
                            full_address = parts[1].strip()
                            
                            # 다음 줄들도 주소의 연속일 가능성 확인 (최대 3줄까지만)
                            for i in range(idx + 1, min(idx + 3, len(lines))):
                                next_line = lines[i].strip()
                                if not next_line:
                                    continue
                                # 주소 키워드가 포함되어 있지 않고, 주소의 연속일 가능성이 있는 줄
                                if not any(kw in next_line for kw in address_keywords + ['위치도', '위 치 도', '기타참고사항', '자동차', '차량', '등록', '번호']):
                                    # 괄호, 번지수, 도로명 등이 포함된 줄이면 주소의 연속으로 간주
                                    if any(kw in next_line for kw in ['번지', '도로명', '로', '길', '(', ')', ':', '-', '내에소재함']):
                                        full_address += " " + next_line
                                    elif next_line in ['(', ')', ':', '-']:  # 단일 기호도 포함
                                        full_address += next_line
                                    elif re.match(r'^\d+$', next_line):  # 숫자만 있는 줄
                                        full_address += next_line
                                    elif next_line == '.':
                                        break  # 문장 끝
                                    else:
                                        break
                                else:
                                    break
                            
                            if full_address and len(full_address) > 5:
                                address_candidates.append(full_address)
        
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
            return self._clean_location_address(address_candidates[-1])
        
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
            return self._clean_location_address(best_address)
        
        return None

    def _clean_location_address(self, text: str) -> str:
        """주소에서 불필요한 레이블 제거 및 번지수까지만 저장"""
        # 여러 패턴 제거
        patterns = [
            r"^보관장소\s*[:：]\s*",
            r"^소재지\s*[:：]\s*",
            r"^\(보관장소\)\s*",  # (보관장소)
            r"\s*\(보관장소\)$",  # 끝에 있는 (보관장소)
            r"^\(소재지\)\s*",    # (소재지)
            r"\s*\(소재지\)$",    # 끝에 있는 (소재지)
            r"^본기계기구는",      # 본기계기구는
            r"^본건은",           # 본건은
            r"^본건",             # 본건
            r"^대상물건은",        # 대상물건은
            r"^대상물건",         # 대상물건
        ]
        result = text
        for pat in patterns:
            result = re.sub(pat, "", result, flags=re.IGNORECASE).strip()
        
        # 접두사 제거 (주소 앞의 불필요한 단어들) - 먼저 적용
        result = re.sub(r'^(기계기구는|본건은|본건|대상물건은|대상물건)\s*', '', result)
        result = re.sub(r'^(본건|대상물건|기계기구|자동차|차량)\s*', '', result)
        
        # "본건은" 직접 제거
        if result.startswith('본건은 '):
            result = result[4:]  # "본건은 " 제거
        elif result.startswith('본건은'):
            result = result[3:]  # "본건은" 제거
        
        # 제어 문자 제거 후 다시 접두사 확인
        import unicodedata
        clean_result = ''.join(char if not unicodedata.category(char).startswith('C') else ' ' for char in result)
        clean_result = re.sub(r'\s+', ' ', clean_result).strip()
        
        if clean_result.startswith('본건은 '):
            clean_result = clean_result[4:]
        elif clean_result.startswith('본건은'):
            clean_result = clean_result[3:]
        
        result = clean_result
        
        # 공백 정리 및 구두점 정리
        result = re.sub(r'\s+', ' ', result)  # 여러 공백을 하나로
        result = re.sub(r'\s*\(\s*:\s*', ' (', result)  # ( : -> (
        result = re.sub(r'\s*\)', ')', result)  # ) 앞 공백 제거
        result = re.sub(r'\s*\.\s*$', '', result)  # 끝의 . 제거
        
        # "소재" 등 불필요한 단어 제거
        result = re.sub(r'\s*소재\s*$', '', result)  # 끝의 "소재" 제거
        result = re.sub(r'\s*내에소재함\s*', '', result)  # "내에소재함" 제거
        result = re.sub(r'\s*번지도로명주소\s*', '', result)  # "번지도로명주소" 제거
        result = re.sub(r'\s*내에\s*설치되어\s*있음\s*$', '', result)  # "내에 설치되어 있음" 제거
        result = re.sub(r'\s*에\s*보관중인\s*자동차.*$', '', result)  # "에 보관중인 자동차..." 제거
        
        
        # 감정평가사 이름 제거
        result = re.sub(r'\s*감정평가사사무소\s*$', '', result)
        result = re.sub(r'\s*감정평가사\s*$', '', result)
        result = re.sub(r'\s*사무소\s*$', '', result)
        
        # 괄호 이후의 불필요한 내용만 제거 (지번, 동호수는 보존)
        # 예: "경기도 양주시 광적면 효촌리 111-3(화합로 179-67) 소재" -> "경기도 양주시 광적면 효촌리 111-3(화합로 179-67)"
        # "소재", "내에소재함" 등이 괄호 뒤에 있으면 제거
        result = re.sub(r'\)\s*(소재|내에소재함|번지도로명주소).*$', ')', result)
        
        # 주소가 너무 길게 추출된 경우, 적절한 지점에서 자르기
        # "번지", "동", "호" 등이 포함된 부분까지만 유지
        if len(result) > 80:  # 너무 긴 경우
            # 번지, 동, 호 등이 포함된 부분을 찾아서 그 이후는 제거
            match = re.search(r'(.+?(?:번지|동|호|로|길).*?)(?:\s+[가-힣]+.*)?$', result)
            if match:
                result = match.group(1)
        
        # 주소가 여전히 너무 긴 경우, 더 엄격하게 자르기
        if len(result) > 60:
            # 괄호가 있으면 괄호까지만, 없으면 번지/동/호까지만
            if '(' in result and ')' in result:
                # 괄호가 완전한 경우
                if result.count('(') == result.count(')'):
                    match = re.search(r'(.+?\([^)]+\))', result)
                    if match:
                        result = match.group(1)
                else:
                    # 괄호가 불완전한 경우, 괄호 이전까지만
                    result = result.split('(')[0].strip()
            else:
                # 괄호가 없는 경우, 번지/동/호까지만
                match = re.search(r'(.+?(?:번지|동|호|로|길).*?)(?:\s+[가-힣]+.*)?$', result)
                if match:
                    result = match.group(1)
        
        # 공백 정리 (여러 공백을 하나로, 앞뒤 공백 제거)
        # 모든 종류의 공백 문자와 제어 문자를 일반 공백으로 변환
        import unicodedata
        result = ''.join(char if not (unicodedata.category(char).startswith('Z') or unicodedata.category(char).startswith('C')) else ' ' for char in result)
        result = re.sub(r'\s+', ' ', result).strip()
        
        # 주소가 너무 짧거나 의미없는 경우 제외
        if len(result) < 5 or result in ['', ' ', 'N', 'null', 'None']:
            return None
        
        # 주소 패턴 검증: 시/도, 구/군이 포함되어야 함
        address_patterns = ['특별시', '광역시', '특별자치시', '특별자치도', '도', '시', '군', '구']
        if not any(pattern in result for pattern in address_patterns):
            return None
        
        # 따옴표 안의 내용 제거 (예: " 자동차", "차량" 등)
        result = re.sub(r'\s*"[^"]*"\s*$', '', result)  # 끝에 있는 따옴표 내용 제거
        result = re.sub(r'\s*"[^"]*"', '', result)  # 중간에 있는 따옴표 내용 제거
        
        # 주소가 아닌 텍스트 제외 (자동차 관련, 법원 관련 등) - 따옴표 제거 후 다시 확인
        exclude_patterns = ['자동차', '차량', '등록', '번호', '법원', '경매', '감정평가', '사무소', '과거', '해당']
        if any(pattern in result for pattern in exclude_patterns):
            return None
            
        return result

    def _iter_image_blocks(self, page: fitz.Page, min_area: float = 10000) -> List[fitz.Rect]:
        """rawdict를 사용하여 이미지 블록의 bbox 목록을 반환.

        일부 PDF에서 block['image']가 정수가 아닌 바이트(내장 이미지 데이터)로 올 수 있으므로
        xref 변환은 하지 않고, 위치 사각형만 사용합니다.
        
        Args:
            page: PDF 페이지
            min_area: 최소 이미지 면적 (기본값: 10000). 작은 헤더/아이콘 등 제외.
        """
        results: List[fitz.Rect] = []
        data = page.get_text("rawdict")
        for block in data.get("blocks", []):
            if block.get("type") == 1:  # image block
                bbox = block.get("bbox")
                if bbox and len(bbox) == 4:
                    rect = fitz.Rect(bbox)
                    area = rect.width * rect.height
                    
                    # 최소 면적 필터
                    if area < min_area:
                        continue
                    
                    # 너무 가로로 긴 이미지(헤더, 테이블 라인) 제외
                    # 가로:세로 비율이 10:1 이상이면 제외
                    if rect.width / max(rect.height, 1) > 10:
                        continue
                    
                    # 너무 세로로 긴 이미지 제외
                    # 세로:가로 비율이 10:1 이상이면 제외
                    if rect.height / max(rect.width, 1) > 10:
                        continue
                    
                    results.append(rect)
        return results

    def extract_photos(self) -> List[str]:
        # 스캔본일 경우 경매 사이트에서 다운로드
        if not self.is_text_based:
            return self._download_photos_from_auction_site()
        
        # 텍스트 기반 PDF는 기존 로직
        saved_paths: List[str] = []
        photos_root = os.path.join(self.output_root, "photos")
        ensure_dir(photos_root)

        idx_counter = 0
        for pidx in range(self.doc.page_count):
            page = self.doc.load_page(pidx)
            # 사진용지 페이지만 저장
            if not self._is_photos_page(page):
                continue
            blocks = self._iter_image_blocks(page)
            if blocks:
                # 페이지 렌더링에서 이미지 위치 rect 별 클리핑 저장
                for rect in blocks:
                    pix = page.get_pixmap(clip=rect, matrix=fitz.Matrix(2, 2))
                    out_path = os.path.join(photos_root, f"{self.auction_no}_{idx_counter}.png")
                    pix.save(out_path)
                    trim_image_whitespace(out_path)
                    crop_image_edges(out_path, pixels=1)
                    saved_paths.append(out_path)
                    idx_counter += 1
                continue

            # 이미지 블록이 감지되지 않으면 전체 페이지 렌더 후 여백 트림
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            out_path = os.path.join(photos_root, f"{self.auction_no}_{idx_counter}.png")
            pix.save(out_path)
            trim_image_whitespace(out_path)
            crop_image_edges(out_path, pixels=1)
            saved_paths.append(out_path)
            idx_counter += 1

        # 폴백: 텍스트 기반 PDF이고 아무것도 저장되지 않았다면, 이미지 블록 존재 페이지는 사진용지로 간주
        if not saved_paths:
            for pidx in range(self.doc.page_count):
                page = self.doc.load_page(pidx)
                blocks = self._iter_image_blocks(page)
                if not blocks:
                    continue
                for rect in blocks:
                    pix = page.get_pixmap(clip=rect, matrix=fitz.Matrix(2, 2))
                    out_path = os.path.join(photos_root, f"{self.auction_no}_{idx_counter}.png")
                    pix.save(out_path)
                    trim_image_whitespace(out_path)
                    crop_image_edges(out_path, pixels=1)
                    saved_paths.append(out_path)
                    idx_counter += 1

        return saved_paths
    
    def _download_photos_from_auction_site(self) -> List[str]:
        """스캔본 PDF일 때 경매 사이트에서 사진을 다운로드합니다."""
        saved_paths: List[str] = []
        photos_root = os.path.join(self.output_root, "photos")
        ensure_dir(photos_root)
        
        try:
            # 경매번호에서 사건번호와 물건번호 분리
            # 예: "2025타경63197-1" -> case_no="2025타경63197", item_no="1"
            parts = self.auction_no.rsplit('-', 1)
            if len(parts) != 2:
                print(f"[스캔본] 경매번호 형식 오류: {self.auction_no}")
                return []
            
            case_no = parts[0]
            item_no = parts[1]
            
            print(f"[스캔본] 경매 사이트에서 사진 다운로드 시도: {case_no}-{item_no}")
            
            # 크롤러 모듈 임포트
            from selenium.webdriver.support.ui import WebDriverWait
            import sys
            
            # 상위 crawling 디렉토리를 sys.path에 추가
            crawling_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if crawling_dir not in sys.path:
                sys.path.insert(0, crawling_dir)
            
            from crawling_auction_ongoing.driver_utils import initialize_driver
            from crawling_auction_ongoing.page_objects import AuctionListPage, AuctionDetailPage
            from crawling_auction_ongoing import config as crawler_config
            
            # case_no에서 연도와 번호 추출
            import re
            match = re.match(r'(\d{4})타경(\d+)', case_no)
            if not match:
                print(f"[스캔본] 사건번호 형식 오류: {case_no}")
                return []
            
            year = match.group(1)
            number = match.group(2)
            display_case_text = f"{year}타경{number}"
            
            # 웹드라이버 초기화
            with initialize_driver() as driver:
                wait = WebDriverWait(driver, crawler_config.DEFAULT_WAIT_TIME)
                
                # 경매 사이트 접속
                list_page = AuctionListPage(driver, wait)
                detail_page = AuctionDetailPage(driver, wait)
                
                # 검색 초기화 (목록 페이지로 이동 포함)
                if not list_page.initialize_search(case_year=year):
                    print(f"[스캔본] 검색 초기화 실패")
                    return []
                
                if not list_page.wait_for_results():
                    print(f"[스캔본] 검색 결과 대기 실패")
                    return []
                
                # 상세 페이지 클릭
                if not list_page.click_item_detail_link(
                    display_case_text=display_case_text,
                    item_no_text=item_no,
                    full_auction_no_for_onclick_fallback=self.auction_no,
                    case_year_for_onclick_fallback=year,
                    case_number_part_for_onclick_fallback=number,
                    item_index_on_page_for_onclick_fallback=0
                ):
                    print(f"[스캔본] 상세 페이지 클릭 실패")
                    return []
                
                if not detail_page.wait_for_load():
                    print(f"[스캔본] 상세 페이지 로드 실패")
                    return []
                
                # 사진 수집
                photo_objects = detail_page.load_all_photos_on_page(
                    case_no_for_log=case_no,
                    item_no_for_log=item_no
                )
                
                print(f"[스캔본] 경매 사이트에서 {len(photo_objects)}개 사진 다운로드 완료")
                
                # 사진 저장
                import base64
                for idx, photo_obj in enumerate(photo_objects):
                    try:
                        # path 키가 있으면 이미 저장된 경로
                        if 'path' in photo_obj and photo_obj['path']:
                            # 기존 파일을 복사
                            src_path = photo_obj['path']
                            if os.path.exists(src_path):
                                import shutil
                                dst_path = os.path.join(photos_root, f"{self.auction_no}_{idx}.png")
                                shutil.copy2(src_path, dst_path)
                                saved_paths.append(dst_path)
                                continue
                        
                        # original_src에서 base64 디코딩
                        if 'original_src' in photo_obj:
                            src_data = photo_obj['original_src']
                            if src_data.startswith('data:image'):
                                header, encoded_data = src_data.split(',', 1)
                                mime_match = re.match(r'data:image/(?P<ext>[a-zA-Z0-9.+]+);base64', header)
                                ext = mime_match.group('ext').split('+')[0] if mime_match else 'png'
                                
                                image_data_bytes = base64.b64decode(encoded_data)
                                
                                out_path = os.path.join(photos_root, f"{self.auction_no}_{idx}.{ext}")
                                with open(out_path, 'wb') as f:
                                    f.write(image_data_bytes)
                                
                                saved_paths.append(out_path)
                    except Exception as e:
                        print(f"[스캔본] 사진 {idx} 저장 실패: {e}")
                        continue
                
        except Exception as e:
            print(f"[스캔본] 경매 사이트 접근 실패: {e}")
            import traceback
            traceback.print_exc()
            return []
        
        return saved_paths

    def run(self) -> ReportExtractionResult:
        appraisal = self.extract_appraisal_fields()
        location = self.extract_location_address()
        photos = self.extract_photos()

        return ReportExtractionResult(
            pdf_filename=os.path.basename(self.pdf_path),
            appraisal=appraisal,
            location_address=location,
            photos_saved=photos,
        )

    def save_result(self, result: ReportExtractionResult) -> str:
        out_json = os.path.join(self.output_root, "metadata.json")
        payload = {
            "pdf_filename": result.pdf_filename,
            "appraisal": asdict(result.appraisal),
            "location_address": result.location_address,
            "photos_saved": result.photos_saved,
        }
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return out_json


def parse_pdf_to_output(pdf_path: str, output_root: Optional[str] = None) -> ReportExtractionResult:
    parser = ReportParser(pdf_path, output_root=output_root)
    result = parser.run()
    parser.save_result(result)
    return result


