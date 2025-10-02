import sys
import os
import glob
import random
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'crawling', 'crawling_auction_reports'))

from report_parser import parse_pdf_to_output

pdf_dir = r'c:\projects\public\uploads\appraisal_reports'
output_base = r'c:\projects\public\uploads\appraisal_reports\FINAL_PHOTOS'

all_pdfs = glob.glob(os.path.join(pdf_dir, '*.pdf'))

# 랜덤으로 30개 선택
random.seed(100)
sample_pdfs = random.sample(all_pdfs, min(30, len(all_pdfs)))
sample_pdfs.sort()

print("=" * 80)
print(f"📷 30개 리포트에서 차량/선박 사진 추출 중...")
print(f"출력 경로: {output_base}")
print("=" * 80)

total_photos = 0
success_count = 0
no_photo_count = 0

for idx, pdf_path in enumerate(sample_pdfs, 1):
    pdf_name = os.path.basename(pdf_path)
    auction_no = pdf_name.replace('_감정평가서.pdf', '')
    
    try:
        output_dir = os.path.join(output_base, auction_no)
        result = parse_pdf_to_output(pdf_path, output_root=output_dir)
        
        photo_count = len(result.photos_saved)
        total_photos += photo_count
        
        if photo_count > 0:
            success_count += 1
            status = "✅"
            print(f"{status} [{idx:2d}/30] {auction_no:25s} → {photo_count:2d}개 사진 | type: {result.appraisal.type}")
        else:
            no_photo_count += 1
            status = "⚠️"
            print(f"{status} [{idx:2d}/30] {auction_no:25s} → 사진 없음 | type: {result.appraisal.type}")
            
    except Exception as e:
        no_photo_count += 1
        print(f"❌ [{idx:2d}/30] {auction_no:25s} → 에러: {str(e)[:50]}")

print(f"\n{'='*80}")
print(f"📊 추출 완료!")
print("=" * 80)
print(f"  ✅ 사진 추출 성공: {success_count}개 리포트")
print(f"  ⚠️  사진 없음/실패: {no_photo_count}개 리포트")
print(f"  📷 총 사진 수: {total_photos}개")
if success_count > 0:
    print(f"  📷 평균 사진 수: {total_photos/success_count:.1f}개/리포트")
print(f"\n  📂 저장 위치: {output_base}")
print("=" * 80)
print(f"\n💡 확인 방법:")
print(f"   1. 탐색기 열기: {output_base}")
print(f"   2. 각 경매번호 폴더 → photos 폴더")
print(f"   3. 실제 차량/선박 사진만 저장되어 있는지 확인")
print(f"\n   ※ 사진용지 페이지만 추출 (지도, 로고, 페이지 이미지 제외)")

