import sys
import os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'crawling', 'crawling_auction_reports'))

import fitz

# 실패한 PDF 샘플 분석
failed_pdfs = [
    r'c:\projects\public\uploads\appraisal_reports\2023타경31213-1_감정평가서.pdf',
    r'c:\projects\public\uploads\appraisal_reports\2024타경2302-1_감정평가서.pdf',
    r'c:\projects\public\uploads\appraisal_reports\2025타경10560-1_감정평가서.pdf',
]

for pdf_path in failed_pdfs:
    pdf_name = os.path.basename(pdf_path)
    print(f"\n{'='*80}")
    print(f"📄 {pdf_name}")
    print('='*80)
    
    doc = fitz.open(pdf_path)
    
    # 각 페이지의 타이틀 확인
    for page_num in range(min(10, len(doc))):  # 처음 10페이지만
        page = doc.load_page(page_num)
        text = page.get_text("text")
        lines = [l.strip() for l in text.split('\n') if l.strip()][:5]  # 처음 5줄
        
        print(f"\n페이지 {page_num+1} (처음 5줄):")
        for line in lines:
            print(f"  {line}")
    
    doc.close()
    
    if failed_pdfs.index(pdf_path) < 2:  # 처음 2개만 자세히
        print(f"\n상세 분석을 위해 계속...")
    else:
        break

