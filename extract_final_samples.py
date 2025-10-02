import sys
import os
import glob
import random
import shutil
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'crawling', 'crawling_auction_reports'))

from report_parser import parse_pdf_to_output

pdf_dir = r'c:\projects\public\uploads\appraisal_reports'
output_base = r'c:\projects\public\uploads\appraisal_reports\FINAL_PHOTOS'

# 기존 폴더 삭제 후 새로 생성
if os.path.exists(output_base):
    shutil.rmtree(output_base)
os.makedirs(output_base)

all_pdfs = glob.glob(os.path.join(pdf_dir, '*.pdf'))

# 랜덤으로 30개 선택
random.seed(100)
sample_pdfs = random.sample(all_pdfs, min(30, len(all_pdfs)))
sample_pdfs.sort()

print("=" * 80)
print(f"📷 최종 검증: 30개 리포트에서 차량/선박 사진만 추출")
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
            print(f"{status} [{idx:2d}/30] {auction_no}: {photo_count:2d}개 | type={result.appraisal.type}")
        else:
            no_photo_count += 1
            status = "⚠️"
            print(f"{status} [{idx:2d}/30] {auction_no}: 사진 없음 | type={result.appraisal.type}")
            
    except Exception as e:
        no_photo_count += 1
        print(f"❌ [{idx:2d}/30] {auction_no}: 에러 - {str(e)[:60]}")

print(f"\n{'='*80}")
print(f"📊 최종 결과")
print("=" * 80)
print(f"  ✅ 사진 추출 성공: {success_count}개 리포트")
print(f"  ⚠️  사진 없음/실패: {no_photo_count}개 리포트")
print(f"  📷 총 사진 수: {total_photos}개")
if success_count > 0:
    print(f"  📷 평균 사진 수: {total_photos/success_count:.1f}개/리포트")
print(f"\n  📂 출력 폴더: {output_base}")
print("=" * 80)
print(f"\n✨ 이제 탐색기에서 다음 경로를 열어 사진을 확인하세요:")
print(f"   {output_base}")
print(f"\n   각 폴더의 photos/ 안에 실제 차량/선박 사진만 있어야 합니다.")
print(f"   (지도, 로고, 페이지 이미지 등은 제외)")

