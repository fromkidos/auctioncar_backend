import sys
import os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'crawling', 'crawling_auction_reports'))

from report_parser import ReportParser

# 스캔본으로 추정되는 샘플들 확인
test_pdfs = [
    '2025타경63197-1',  # 사진 0개
    '2025타경72681-1',  # 사진 0개
    '2025타경32622-1',  # 사진 0개
]

print("스캔본 PDF 샘플 분석")
print("="*80)

scanned_count = 0
text_based_count = 0

for auction_no in test_pdfs:
    pdf_path = rf'c:\projects\public\uploads\appraisal_reports\{auction_no}_감정평가서.pdf'
    
    if not os.path.exists(pdf_path):
        print(f"{auction_no}: 파일 없음")
        continue
    
    parser = ReportParser(pdf_path, output_root=r'c:\projects\temp')
    
    print(f"\n{auction_no}:")
    print(f"  PDF 타입: {'텍스트 기반' if parser.is_text_based else '스캔본'}")
    print(f"  총 페이지: {len(parser.doc)}개")
    
    if not parser.is_text_based:
        scanned_count += 1
        
        # 처음 3페이지의 텍스트 길이와 이미지 블록 수 확인
        for i in range(min(3, len(parser.doc))):
            page = parser.doc.load_page(i)
            text = page.get_text("text").strip()
            data = page.get_text("rawdict")
            image_blocks = [b for b in data.get("blocks", []) if b.get("type") == 1]
            
            print(f"    페이지 {i+1}: 텍스트 {len(text)}자, 이미지 블록 {len(image_blocks)}개")
    else:
        text_based_count += 1
    
    parser.doc.close()

print("\n" + "="*80)
print(f"결과: 스캔본 {scanned_count}개, 텍스트 기반 {text_based_count}개")

