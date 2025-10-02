import sys
import os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'crawling', 'crawling_auction_reports'))

import fitz

pdf_path = r'c:\projects\public\uploads\appraisal_reports\2024타경2302-1_감정평가서.pdf'
doc = fitz.open(pdf_path)

print("선박 관련 키워드가 있는 페이지 찾기:")
print("=" * 80)

for page_num in range(len(doc)):
    page = doc.load_page(page_num)
    text = page.get_text("text")
    
    # 선박 관련 키워드
    keywords = ["선체의 현황", "기관의 현황", "주기관의 현황", "의장품", "운항사항", "실사장소"]
    found_keywords = [kw for kw in keywords if kw in text]
    
    if found_keywords:
        print(f"\n페이지 {page_num+1}: {', '.join(found_keywords)}")

doc.close()

