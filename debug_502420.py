import sys
import os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'crawling', 'crawling_auction_reports'))

from report_parser import ReportParser

pdf_path = r'c:\projects\public\uploads\appraisal_reports\2025타경502420-1_감정평가서.pdf'
parser = ReportParser(pdf_path, output_root=r'c:\projects\temp')

print("2025타경502420-1 PDF 분석")
print("="*80)

# 1. 위치도 페이지 확인
print("\n1. 위치도 페이지 검색:")
location_pages = parser._find_pages_by_titles(parser.TITLE_KEYS["location"])
print(f"   위치도 페이지: {[p+1 for p in location_pages]}")

if location_pages:
    for page_idx in location_pages[:3]:  # 처음 3개만
        text = parser._page_text(page_idx)
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        
        print(f"\n   페이지 {page_idx+1} 텍스트 ({len(lines)}줄):")
        for i, line in enumerate(lines[:15], 1):
            print(f"     {i:2d}: {line}")
        if len(lines) > 15:
            print(f"     ... (총 {len(lines)}줄)")

# 2. 실제 주소 추출 테스트
print("\n2. 주소 추출:")
location = parser.extract_location_address()
print(f"   추출된 주소: '{location if location else '(null)'}'")

# 3. 주소 추출 디버깅
if location_pages:
    print("\n3. 주소 추출 상세 과정:")
    page = parser.doc.load_page(location_pages[0])
    lines = parser._page_text(location_pages[0]).split('\n')
    
    # 주소 후보 찾기
    address_keywords = ['특별시', '광역시', '특별자치시', '특별자치도', '도', '시', '군', '구', '읍', '면', '동', '리', '로', '길']
    
    print("   주소 후보:")
    for idx, line in enumerate(lines):
        ln = line.strip()
        if not ln or len(ln) < 10:
            continue
        if any(kw in ln for kw in ['위치도', '위 치 도', '소재지', '소 재 지', '보관장소']):
            continue
        
        has_address_keyword = any(kw in ln for kw in address_keywords)
        if has_address_keyword:
            score = len(ln)
            score += ln.count('(') * 10
            score += len([m for m in __import__('re').findall(r'\d+-\d+', ln)]) * 20
            score += sum(1 for kw in address_keywords if kw in ln) * 5
            
            print(f"     라인 {idx}: (점수 {score}) '{ln}'")

parser.doc.close()

