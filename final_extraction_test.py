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

# 30개 선택
random.seed(100)
sample_pdfs = random.sample(all_pdfs, min(30, len(all_pdfs)))
sample_pdfs.sort()

print("=" * 80)
print(f"✨ 최종 개선된 사진 추출 테스트")
print(f"   ✅ PDF 타입 자동 감지 (텍스트 vs 스캔본)")
print(f"   ✅ 텍스트 PDF: '사진용지' 텍스트로 정확한 페이지 판별")
print(f"   ✅ 스캔본 PDF: 사진 추출 안 함 (OCR 없이 불가능)")
print(f"   ✅ 이미지 필터: 최소 면적 10000, 비율 필터")
print("=" * 80)

text_pdf_count = 0
scanned_pdf_count = 0
text_photo_count = 0
text_success = 0
scanned_photo_count = 0

for idx, pdf_path in enumerate(sample_pdfs, 1):
    pdf_name = os.path.basename(pdf_path)
    auction_no = pdf_name.replace('_감정평가서.pdf', '')
    
    try:
        output_dir = os.path.join(output_base, auction_no)
        result = parse_pdf_to_output(pdf_path, output_root=output_dir)
        
        pdf_type = result.appraisal.type if hasattr(result.appraisal, 'type') else "unknown"
        photo_count = len(result.photos_saved)
        
        # PDF 타입 확인 (파서 인스턴스 생성해서 확인)
        from report_parser import ReportParser
        parser = ReportParser(pdf_path)
        is_text = parser.is_text_based
        parser.doc.close()
        
        if is_text:
            text_pdf_count += 1
            text_photo_count += photo_count
            if photo_count > 0:
                text_success += 1
        else:
            scanned_pdf_count += 1
            scanned_photo_count += photo_count
        
        pdf_type_str = "텍스트" if is_text else "스캔본"
        
        if photo_count > 0:
            status = "✅"
            print(f"{status} [{idx:2d}/30] {auction_no:25s} | {pdf_type_str:6s} | {photo_count:2d}개 사진")
        else:
            status = "⚠️"
            print(f"{status} [{idx:2d}/30] {auction_no:25s} | {pdf_type_str:6s} | 사진 없음")
            
    except Exception as e:
        print(f"❌ [{idx:2d}/30] {auction_no:25s} | 에러: {str(e)[:40]}")

print(f"\n{'='*80}")
print(f"📊 최종 결과")
print("=" * 80)
print(f"  📄 PDF 타입 분류:")
print(f"     텍스트 기반: {text_pdf_count}개")
print(f"     스캔본:      {scanned_pdf_count}개")
print(f"\n  📷 사진 추출:")
print(f"     텍스트 PDF: {text_photo_count}개 사진 ({text_success}/{text_pdf_count} 리포트)")
print(f"     스캔본 PDF: {scanned_photo_count}개 사진 (기대값: 0개)")
print(f"\n  ✅ 스캔본 PDF의 사진 추출: {'성공적으로 차단됨' if scanned_photo_count == 0 else f'⚠️ {scanned_photo_count}개 추출됨 (문제 있음)'}")
print(f"\n  📂 저장 위치: {output_base}")
print("=" * 80)

