import sys
import os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'crawling', 'crawling_auction_reports'))

import fitz

# 선박 감정평가서 샘플 분석
ship_pdfs = [
    r'c:\projects\public\uploads\appraisal_reports\2023타경31213-1_감정평가서.pdf',
    r'c:\projects\public\uploads\appraisal_reports\2024타경2302-1_감정평가서.pdf',
]

for pdf_path in ship_pdfs[:1]:  # 첫 번째만 자세히
    pdf_name = os.path.basename(pdf_path)
    print(f"\n{'='*80}")
    print(f"📄 {pdf_name}")
    print('='*80)
    
    doc = fitz.open(pdf_path)
    
    # "선박" 관련 페이지 찾기
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        text = page.get_text("text")
        
        # "선박 감정평가요항표" 또는 "선박감정평가요항표" 찾기
        if ("선박" in text and "감정평가요항표" in text) or "선박감정평가요항표" in text:
            print(f"\n✅ 페이지 {page_num+1}: 선박 감정평가요항표 발견")
            print("\n전체 텍스트:")
            print("-" * 80)
            print(text)
            print("-" * 80)
            break
    
    doc.close()

