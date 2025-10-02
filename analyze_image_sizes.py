import sys
import os
sys.stdout.reconfigure(encoding='utf-8')

import fitz

pdf_path = r'c:\projects\public\uploads\appraisal_reports\2024타경110709-1_감정평가서.pdf'
doc = fitz.open(pdf_path)

# 페이지 9-12 확인 (사진이 있는 페이지)
pages_to_check = [8, 9, 10, 11]  # 0-based (9, 10, 11, 12 페이지)

all_areas = []

for page_idx in pages_to_check:
    page = doc.load_page(page_idx)
    data = page.get_text("rawdict")
    image_blocks = [b for b in data.get("blocks", []) if b.get("type") == 1]
    
    for block in image_blocks:
        bbox = block.get("bbox", [])
        if len(bbox) == 4:
            rect = fitz.Rect(bbox)
            area = rect.width * rect.height
            all_areas.append(area)

print(f"총 이미지 블록 수: {len(all_areas)}개")
print(f"\n면적 통계:")
print(f"  최소: {min(all_areas):.0f}")
print(f"  최대: {max(all_areas):.0f}")
print(f"  평균: {sum(all_areas)/len(all_areas):.0f}")
print(f"  중간값: {sorted(all_areas)[len(all_areas)//2]:.0f}")

# 면적별 분포
ranges = [(0, 1000), (1000, 5000), (5000, 10000), (10000, 50000), (50000, float('inf'))]
print(f"\n면적별 분포:")
for min_a, max_a in ranges:
    count = sum(1 for a in all_areas if min_a <= a < max_a)
    print(f"  {min_a:6.0f} ~ {max_a:6.0f}: {count:3d}개")

doc.close()

