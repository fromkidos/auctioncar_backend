import sys
import os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'crawling', 'crawling_auction_reports'))

from report_parser import ReportParser

pdf_path = r'c:\projects\public\uploads\appraisal_reports\2023타경2315-1_감정평가서.pdf'
output_dir = r'c:\projects\public\uploads\appraisal_reports\TEST_BRACKETS\2023타경2315-1'

parser = ReportParser(pdf_path, output_root=output_dir)

print("=== 2023타경2315-1 괄호 내용 디버그 ===")

# 위치도 페이지 찾기
location_pages = parser._find_pages_by_titles(parser.TITLE_KEYS["location"])
print(f"위치도 페이지: {location_pages}")

if location_pages:
    page = parser.doc.load_page(location_pages[0])
    lines = parser._page_text(location_pages[0]).split('\n')
    
    print(f"\n페이지 {location_pages[0] + 1} 내용:")
    for i, line in enumerate(lines):
        if "경기도" in line or "양주시" in line or "광적면" in line or "효촌리" in line:
            print(f"{i:2d}: '{line}'")
            # 앞뒤 3줄도 출력
            for j in range(max(0, i-3), min(len(lines), i+4)):
                if j != i:
                    print(f"  {j}: '{lines[j]}'")

parser.doc.close()
