import sys
import os
import random
import json
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'crawling', 'crawling_auction_reports'))

from report_parser import parse_pdf_to_output

# 모든 PDF 찾기
appraisal_dir = r'c:\projects\public\uploads\appraisal_reports'
all_pdfs = []
for root, dirs, files in os.walk(appraisal_dir):
    for f in files:
        if f.endswith('.pdf'):
            all_pdfs.append(os.path.join(root, f))

print(f"총 PDF 개수: {len(all_pdfs)}개")

# 랜덤 20개 선택
random.seed(99)  # 다른 시드로 변경
selected_pdfs = random.sample(all_pdfs, min(20, len(all_pdfs)))

output_base = r'c:\projects\public\uploads\appraisal_reports\TEST_20_FINAL'
os.makedirs(output_base, exist_ok=True)

print(f"\n20개 샘플 최종 테스트 시작...")
print("="*80)

results = []
for idx, pdf_path in enumerate(selected_pdfs, 1):
    filename = os.path.basename(pdf_path)
    auction_no = filename.replace('_감정평가서.pdf', '')
    
    output_dir = os.path.join(output_base, auction_no)
    
    try:
        result = parse_pdf_to_output(pdf_path, output_dir)
        
        photo_count = len(result.photos_saved)
        has_location = result.location_address is not None
        has_year = result.appraisal.year_and_mileage is not None
        has_condition = result.appraisal.condition is not None
        has_fuel = result.appraisal.fuel is not None
        
        print(f"{idx:2d}. {auction_no}: 사진 {photo_count:2d}개 | 주소 {'✓' if has_location else '✗'} | 년식 {'✓' if has_year else '✗'} | 관리 {'✓' if has_condition else '✗'} | 연료 {'✓' if has_fuel else '✗'}")
        
        results.append({
            'auction_no': auction_no,
            'photo_count': photo_count,
            'has_location': has_location,
            'has_year': has_year,
            'has_condition': has_condition,
            'has_fuel': has_fuel
        })
        
    except Exception as e:
        print(f"{idx:2d}. {auction_no}: 오류 - {str(e)[:50]}")
        results.append({
            'auction_no': auction_no,
            'error': str(e)
        })

print("\n" + "="*80)
print(f"완료! 결과는 {output_base} 폴더에 저장되었습니다.")

# 통계
success_count = len([r for r in results if 'error' not in r])
total_photos = sum([r.get('photo_count', 0) for r in results if 'error' not in r])
has_year_count = len([r for r in results if r.get('has_year')])
has_condition_count = len([r for r in results if r.get('has_condition')])
has_fuel_count = len([r for r in results if r.get('has_fuel')])

print(f"\n통계:")
print(f"  성공: {success_count}/20")
print(f"  총 사진: {total_photos}개")
print(f"  년식 추출: {has_year_count}/{success_count}")
print(f"  관리상태 추출: {has_condition_count}/{success_count}")
print(f"  사용연료 추출: {has_fuel_count}/{success_count}")

