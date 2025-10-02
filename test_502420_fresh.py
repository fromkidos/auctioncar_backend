import sys
import os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'crawling', 'crawling_auction_reports'))

from report_parser import parse_pdf_to_output
import json

pdf_path = r'c:\projects\public\uploads\appraisal_reports\2025타경502420-1_감정평가서.pdf'
output_dir = r'c:\projects\temp_502420_fresh'

print("2025타경502420-1 최신 코드로 재추출")
print("="*80)

result = parse_pdf_to_output(pdf_path, output_dir)

print(f"\n추출 결과:")
print(f"  주소: '{result.location_address if result.location_address else '(null)'}'")
print(f"  사진: {len(result.photos_saved)}개")

# metadata.json 확인
metadata_path = os.path.join(output_dir, 'metadata.json')
with open(metadata_path, 'r', encoding='utf-8') as f:
    metadata = json.load(f)

print(f"\nmetadata.json:")
print(f"  location_address: '{metadata.get('location_address')}'")

print("\n" + "="*80)

