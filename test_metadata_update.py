import sys
import os
sys.stdout.reconfigure(encoding='utf-8')

# 경로 설정
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'crawling'))

def test_metadata_update():
    """수정된 metadata 구조 테스트"""
    try:
        from crawling_auction_reports.report_parser import parse_pdf_to_output
        
        print("🧪 수정된 metadata 구조 테스트")
        
        # 테스트용 PDF 파일
        test_pdf = r"C:\projects\public\uploads\appraisal_reports\2024타경88180-5_감정평가서.pdf"
        
        if not os.path.exists(test_pdf):
            print(f"❌ 테스트 PDF 파일이 없습니다: {test_pdf}")
            return False
        
        print(f"📄 PDF 분석: {os.path.basename(test_pdf)}")
        
        # PDF 파싱
        result = parse_pdf_to_output(test_pdf)
        
        print(f"  - PDF 파일명: {result.pdf_filename}")
        print(f"  - 주소: {result.location_address}")
        print(f"  - 감정평가 타입: {result.appraisal.type}")
        
        # metadata.json 파일 확인
        metadata_file = os.path.join(os.path.dirname(test_pdf), "extracted", "metadata.json")
        if os.path.exists(metadata_file):
            import json
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            print(f"  - metadata 파일 생성됨: {metadata_file}")
            print(f"  - total_photo_count: {metadata.get('metadata', {}).get('total_photo_count', 'N/A')}")
            print(f"  - is_text_based: {metadata.get('metadata', {}).get('is_text_based', 'N/A')}")
            print(f"  - total_pages: {metadata.get('metadata', {}).get('total_pages', 'N/A')}")
        else:
            print(f"  - metadata 파일이 생성되지 않았습니다: {metadata_file}")
        
        print("\n🎉 수정된 metadata 구조 테스트 완료!")
        return True
        
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_metadata_update()
    if success:
        print("✅ 수정된 metadata 구조 테스트 성공!")
    else:
        print("❌ 수정된 metadata 구조 테스트 실패!")
