"""
데이터 모델 정의
"""
from dataclasses import dataclass
from typing import Optional, List


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
    hull_status: Optional[str] = None      # 선체상태
    engine_status: Optional[str] = None    # 기관상태
    equipment_status: Optional[str] = None # 장비상태
    operation_info: Optional[str] = None   # 운항정보
    inspection_location: Optional[str] = None  # 검사장소
    ship_etc: Optional[str] = None         # 기타


@dataclass
class ReportExtractionResult:
    """PDF 추출 결과"""
    pdf_filename: str
    location_address: Optional[str]
    appraisal: AppraisalFields
    # photos_saved 제거 - DB에 total_photo_count로 저장됨
