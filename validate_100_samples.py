import sys
import os
import glob
import random
import traceback
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'crawling', 'crawling_auction_reports'))

from report_parser import parse_pdf_to_output

pdf_dir = r'c:\projects\public\uploads\appraisal_reports'
all_pdfs = glob.glob(os.path.join(pdf_dir, '*.pdf'))

# 무작위로 100개 선택
random.seed(42)  # 재현 가능하도록 시드 고정
sample_pdfs = random.sample(all_pdfs, min(100, len(all_pdfs)))
sample_pdfs.sort()

# 통계
car_success = 0
car_partial = 0
car_fail = 0
ship_success = 0
ship_partial = 0
ship_fail = 0
unknown_count = 0
error_count = 0

# 사진 관련 통계
total_photos = 0
no_photos_count = 0
photo_issues = []

print("=" * 80)
print(f"📊 100개 샘플 PDF 검증 시작")
print("=" * 80)

for idx, pdf_path in enumerate(sample_pdfs, 1):
    pdf_name = os.path.basename(pdf_path)
    
    try:
        output_dir = os.path.join(pdf_dir, 'test_extracted', pdf_name.replace('.pdf', ''))
        result = parse_pdf_to_output(pdf_path, output_root=output_dir)
        
        appraisal_type = result.appraisal.type
        photo_count = len(result.photos_saved)
        total_photos += photo_count
        
        # 사진 검증
        if photo_count == 0:
            no_photos_count += 1
            photo_issues.append(f"{pdf_name}: 사진 없음")
        
        # 실제 저장된 파일 확인
        if photo_count > 0:
            photos_dir = os.path.join(output_dir, 'photos')
            if os.path.exists(photos_dir):
                actual_files = [f for f in os.listdir(photos_dir) if f.endswith('.png')]
                if len(actual_files) != photo_count:
                    photo_issues.append(f"{pdf_name}: 보고된 사진 {photo_count}개 vs 실제 파일 {len(actual_files)}개")
        
        if appraisal_type == "car":
            # 자동차 필드 체크
            appraisal_ok = all([
                result.appraisal.year_and_mileage,
                result.appraisal.color,
                result.appraisal.condition,
                result.appraisal.fuel,
            ])
            
            appraisal_partial = any([
                result.appraisal.year_and_mileage,
                result.appraisal.color,
                result.appraisal.condition,
                result.appraisal.fuel,
            ])
            
            has_photos = photo_count > 0
            
            if appraisal_ok and has_photos:
                car_success += 1
                status = "✅"
            elif appraisal_partial or has_photos:
                car_partial += 1
                status = "⚠️"
            else:
                car_fail += 1
                status = "❌"
            
            if idx <= 20 or status != "✅":  # 처음 20개 또는 문제 있는 것만 출력
                print(f"{status} [{idx:3d}/100] CAR {pdf_name}")
                print(f"     📷 사진: {photo_count}개 | 📋 년식={'✓' if result.appraisal.year_and_mileage else '✗'} 색상={'✓' if result.appraisal.color else '✗'} 연료={'✓' if result.appraisal.fuel else '✗'}")
            
        elif appraisal_type == "ship":
            # 선박 필드 체크
            appraisal_ok = any([
                result.appraisal.hull_status,
                result.appraisal.engine_status,
                result.appraisal.equipment_status,
                result.appraisal.operation_info,
            ])
            
            has_photos = photo_count > 0
            
            if appraisal_ok and has_photos:
                ship_success += 1
                status = "✅"
            elif appraisal_ok or has_photos:
                ship_partial += 1
                status = "⚠️"
            else:
                ship_fail += 1
                status = "❌"
            
            if idx <= 20 or status != "✅":
                print(f"{status} [{idx:3d}/100] SHIP {pdf_name}")
                print(f"     📷 사진: {photo_count}개 | 🚢 선체={'✓' if result.appraisal.hull_status else '✗'} 기관={'✓' if result.appraisal.engine_status else '✗'} 의장품={'✓' if result.appraisal.equipment_status else '✗'}")
        
        else:
            unknown_count += 1
            if idx <= 20:
                print(f"❓ [{idx:3d}/100] UNKNOWN {pdf_name}")
                print(f"     📷 사진: {photo_count}개")
        
    except Exception as e:
        error_count += 1
        print(f"❌ [{idx:3d}/100] ERROR {pdf_name}")
        print(f"     에러: {str(e)[:100]}")
        if idx <= 20:
            print(f"     상세: {traceback.format_exc()[:200]}")

# 최종 리포트
print(f"\n{'='*80}")
print(f"📊 최종 검증 결과 ({len(sample_pdfs)}개 PDF)")
print('='*80)

total_car = car_success + car_partial + car_fail
total_ship = ship_success + ship_partial + ship_fail

print(f"\n🚗 자동차: {total_car}건")
if total_car > 0:
    print(f"  ✅ 완전 성공: {car_success:2d}건 ({car_success/total_car*100:5.1f}%)")
    print(f"  ⚠️  부분 성공: {car_partial:2d}건 ({car_partial/total_car*100:5.1f}%)")
    print(f"  ❌ 실패:     {car_fail:2d}건 ({car_fail/total_car*100:5.1f}%)")

print(f"\n🚢 선박: {total_ship}건")
if total_ship > 0:
    print(f"  ✅ 완전 성공: {ship_success:2d}건 ({ship_success/total_ship*100:5.1f}%)")
    print(f"  ⚠️  부분 성공: {ship_partial:2d}건 ({ship_partial/total_ship*100:5.1f}%)")
    print(f"  ❌ 실패:     {ship_fail:2d}건 ({ship_fail/total_ship*100:5.1f}%)")

print(f"\n❓ 미분류: {unknown_count}건")
print(f"❌ 에러:   {error_count}건")

print(f"\n📷 사진 통계:")
print(f"  총 사진 수: {total_photos}개")
print(f"  사진 없는 PDF: {no_photos_count}건")
print(f"  평균 사진 수: {total_photos/(len(sample_pdfs)-error_count):.1f}개/PDF")

if photo_issues:
    print(f"\n⚠️  사진 관련 이슈 ({len(photo_issues)}건):")
    for issue in photo_issues[:10]:  # 처음 10개만
        print(f"  - {issue}")
    if len(photo_issues) > 10:
        print(f"  ... 외 {len(photo_issues)-10}건 더")

print('='*80)

