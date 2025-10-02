import sys
import os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'crawling', 'crawling_auction_reports'))

from report_parser import parse_pdf_to_output

# 스캔본 PDF 테스트
pdf_path = r'c:\projects\public\uploads\appraisal_reports\2025타경63197-1_감정평가서.pdf'
output_dir = r'c:\projects\temp_scanned_test'

print("스캔본 PDF 경매 사이트 다운로드 테스트")
print("="*80)
print(f"PDF: 2025타경63197-1")
print()

try:
    result = parse_pdf_to_output(pdf_path, output_dir)
    
    print(f"\n추출 결과:")
    print(f"  사진: {len(result.photos_saved)}개")
    if result.photos_saved:
        for i, path in enumerate(result.photos_saved[:5]):
            print(f"    {i}: {os.path.basename(path)}")
        if len(result.photos_saved) > 5:
            print(f"    ... (총 {len(result.photos_saved)}개)")
    
    print(f"\n  주소: {result.location_address if result.location_address else '(null)'}")
    print(f"  감정평가 필드:")
    print(f"    type: {result.appraisal.type}")
    print(f"    year_and_mileage: {result.appraisal.year_and_mileage[:50] if result.appraisal.year_and_mileage else '(null)'}...")
    
except Exception as e:
    print(f"\n오류 발생: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)

