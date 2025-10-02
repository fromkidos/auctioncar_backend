import sys
import os
sys.stdout.reconfigure(encoding='utf-8')

# 경로 설정
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'crawling'))

def test_report_extraction():
    """리포트 추출 테스트"""
    try:
        from crawling_auction_reports.report_parser import parse_pdf_to_output
        
        print("🧪 리포트 추출 테스트 시작")
        
        # 테스트용 PDF 파일 (인코딩 문제를 피하기 위해 다른 파일 사용)
        test_pdf = r"C:\projects\public\uploads\appraisal_reports\2023타경120088-1_감정평가서.pdf"
        
        if not os.path.exists(test_pdf):
            print(f"❌ 테스트 PDF 파일이 없습니다: {test_pdf}")
            return False
        
        print(f"📄 PDF 분석: {os.path.basename(test_pdf)}")
        
        # PDF 파싱
        result = parse_pdf_to_output(test_pdf)
        
        print(f"✅ 추출 완료!")
        print(f"  - PDF 파일명: {result.pdf_filename}")
        print(f"  - 주소: {result.location_address}")
        print(f"  - 감정평가 타입: {result.appraisal.type}")
        
        # metadata.json 파일 확인
        metadata_file = os.path.join(os.path.dirname(test_pdf), "extracted", "metadata.json")
        if os.path.exists(metadata_file):
            print(f"\n📋 metadata.json 파일 생성됨: {metadata_file}")
            
            import json
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            print("\n📊 metadata.json 내용:")
            print(json.dumps(metadata, ensure_ascii=False, indent=2))
        else:
            print(f"❌ metadata 파일이 생성되지 않았습니다: {metadata_file}")
        
        print("\n🎉 리포트 추출 테스트 완료!")
        return True
        
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_report_extraction()
    if success:
        print("✅ 리포트 추출 테스트 성공!")
    else:
        print("❌ 리포트 추출 테스트 실패!")
