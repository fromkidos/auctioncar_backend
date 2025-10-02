import sys
import os
sys.stdout.reconfigure(encoding='utf-8')

# 경로 설정
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'crawling'))

def test_scan_processing():
    """스캔본 처리 테스트"""
    try:
        from crawling_auction_reports.scan_processor import ScanProcessor
        import fitz
        
        print("🧪 스캔본 처리 테스트 시작")
        
        # 테스트용 PDF 파일 (실제 스캔본 PDF 경로로 변경)
        test_pdf_path = r"C:\projects\public\uploads\appraisal_reports\2024타경88180-5_감정평가서.pdf"
        
        if not os.path.exists(test_pdf_path):
            print(f"❌ 테스트 PDF 파일이 없습니다: {test_pdf_path}")
            return False
        
        # PDF 열기
        doc = fitz.open(test_pdf_path)
        output_root = r"C:\projects\public\uploads\appraisal_reports\TEST_SCAN_OUTPUT"
        
        # ScanProcessor 생성
        scan_processor = ScanProcessor(doc, output_root)
        
        try:
            # 스캔본 처리 실행
            pdf_filename = os.path.basename(test_pdf_path)
            photos = scan_processor.process_scan_pdf(pdf_filename)
            
            print(f"✅ 스캔본 처리 완료: {len(photos)}개 사진 다운로드")
            for i, photo in enumerate(photos):
                print(f"  {i+1}. {photo}")
            
            return True
            
        finally:
            scan_processor.close()
            doc.close()
            
    except Exception as e:
        print(f"❌ 스캔본 처리 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_scan_processing()
    if success:
        print("✅ 스캔본 처리 테스트 성공!")
    else:
        print("❌ 스캔본 처리 테스트 실패!")
