import sys
import os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'crawling', 'crawling_auction_reports'))

import fitz

# 두 번째 선박 감정평가서 분석
pdf_path = r'c:\projects\public\uploads\appraisal_reports\2024타경2302-1_감정평가서.pdf'
pdf_name = os.path.basename(pdf_path)
print(f"\n{'='*80}")
print(f"📄 {pdf_name}")
print('='*80)

doc = fitz.open(pdf_path)

# "선박" 관련 페이지 찾기
for page_num in range(len(doc)):
    page = doc.load_page(page_num)
    text = page.get_text("text")
    
    # 선체/기관/의장품 키워드로 찾기
    if ("선체의 현황" in text or "기관의 현황" in text) and "구분" in text:
        print(f"\n✅ 페이지 {page_num+1}: 선박 정보 발견")
        print("\n전체 텍스트:")
        print("-" * 80)
        print(text)
        print("-" * 80)
        break

doc.close()

