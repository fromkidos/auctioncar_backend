"""
PDF 감정평가서 파싱 메인 클래스 (리팩토링 버전)
"""
import os
import json
from typing import Optional
import fitz
from .models import AppraisalFields, ReportExtractionResult
from .address_extractor import AddressExtractor
from .appraisal_extractor import AppraisalExtractor
from .photo_extractor import PhotoExtractor
from .utils import ensure_dir


class ReportParser:
    """PDF 감정평가서 파싱 클래스"""
    
    def __init__(self, pdf_path: str, output_root: Optional[str] = None) -> None:
        self.pdf_path = pdf_path
        self.doc = fitz.open(pdf_path)
        
        # 출력 디렉토리 설정
        if output_root is None:
            default_root = os.path.join(
                os.path.dirname(pdf_path), 
                "extracted"
            )
            self.output_root = default_root
        else:
            self.output_root = output_root
        
        # PDF 타입 감지
        self.is_text_based = self._detect_pdf_type()
        
        # 추출기들 초기화
        self.address_extractor = AddressExtractor(self.doc)
        self.appraisal_extractor = AppraisalExtractor(self.doc, self.is_text_based)
        self.photo_extractor = PhotoExtractor(self.doc, self.output_root, self.is_text_based)
    
    def _detect_pdf_type(self) -> bool:
        """PDF가 텍스트 기반인지 스캔본인지 감지"""
        try:
            # 첫 3페이지에서 텍스트 추출 시도
            text_count = 0
            for page_num in range(min(3, len(self.doc))):
                page = self.doc.load_page(page_num)
                text = page.get_text("text").strip()
                if len(text) > 100:  # 충분한 텍스트가 있으면 텍스트 기반
                    text_count += 1
            
            # 2페이지 이상에서 텍스트가 있으면 텍스트 기반
            return text_count >= 2
        except:
            return False
    
    def extract_location_address(self) -> Optional[str]:
        """주소 추출"""
        return self.address_extractor.extract_location_address()
    
    def extract_appraisal_fields(self) -> AppraisalFields:
        """감정평가 필드 추출"""
        return self.appraisal_extractor.extract_appraisal_fields()
    
    def extract_photos(self) -> list:
        """사진 추출"""
        return self.photo_extractor.extract_photos()
    
    def run(self) -> ReportExtractionResult:
        """전체 추출 프로세스 실행"""
        pdf_filename = os.path.basename(self.pdf_path)
        
        # 각종 추출 실행
        location_address = self.extract_location_address()
        appraisal = self.extract_appraisal_fields()
        photos = self.extract_photos()
        
        # 결과 생성
        result = ReportExtractionResult(
            pdf_filename=pdf_filename,
            location_address=location_address,
            appraisal=appraisal,
            photos_saved=photos
        )
        
        return result
    
    def save_result(self, result: ReportExtractionResult) -> str:
        """결과를 JSON 파일로 저장"""
        # 출력 디렉토리 생성
        ensure_dir(self.output_root)
        
        # 결과를 딕셔너리로 변환
        result_dict = {
            'pdf_filename': result.pdf_filename,
            'location_address': result.location_address,
            'appraisal': {
                'type': result.appraisal.type,
                'year_and_mileage': result.appraisal.year_and_mileage,
                'color': result.appraisal.color,
                'condition': result.appraisal.condition,
                'fuel': result.appraisal.fuel,
                'inspection_validity': result.appraisal.inspection_validity,
                'etc': result.appraisal.etc,
                'hull_status': result.appraisal.hull_status,
                'engine_status': result.appraisal.engine_status,
                'equipment_status': result.appraisal.equipment_status,
                'operation_info': result.appraisal.operation_info,
                'inspection_location': result.appraisal.inspection_location,
                'ship_etc': result.appraisal.ship_etc,
            },
            'photos_saved': result.photos_saved
        }
        
        # JSON 파일로 저장
        output_file = os.path.join(self.output_root, 'metadata.json')
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result_dict, f, ensure_ascii=False, indent=2)
        
        return output_file
    
    def close(self):
        """리소스 정리"""
        if hasattr(self, 'doc'):
            self.doc.close()


def parse_pdf_to_output(pdf_path: str, output_root: Optional[str] = None) -> ReportExtractionResult:
    """PDF를 파싱하여 결과를 반환하는 편의 함수"""
    parser = ReportParser(pdf_path, output_root)
    try:
        result = parser.run()
        parser.save_result(result)
        return result
    finally:
        parser.close()
