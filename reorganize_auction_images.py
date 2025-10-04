#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
경매 이미지를 폴더 구조로 재정리하는 스크립트
기존: 2023타경120088-1_0.png, 2023타경120088-1_1.png
새로운: 2023타경120088-1/2023타경120088-1_0.png, 2023타경120088-1/2023타경120088-1_1.png
"""

import os
import shutil
import re
from collections import defaultdict

def reorganize_auction_images(auction_images_dir: str):
    """경매 이미지를 폴더 구조로 재정리"""
    
    # 경매별로 파일들을 그룹화
    auction_files = defaultdict(list)
    
    print(f"스캔 중: {auction_images_dir}")
    
    # 모든 파일을 스캔하여 경매별로 그룹화
    for filename in os.listdir(auction_images_dir):
        file_path = os.path.join(auction_images_dir, filename)
        
        # 디렉토리는 건너뛰기
        if os.path.isdir(file_path):
            continue
            
        # 이미지 파일만 처리
        if not filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            continue
            
        # 파일명에서 경매번호 추출 (예: 2023타경120088-1_0.png -> 2023타경120088-1)
        match = re.match(r'^(.+?)_\d+\.(png|jpg|jpeg)$', filename, re.IGNORECASE)
        if match:
            auction_no = match.group(1)
            auction_files[auction_no].append(filename)
        else:
            print(f"파일명 패턴이 맞지 않음: {filename}")
    
    print(f"총 {len(auction_files)}개의 경매를 발견했습니다.")
    
    # 각 경매별로 폴더 생성 및 파일 이동
    moved_count = 0
    error_count = 0
    
    for auction_no, files in auction_files.items():
        try:
            # 경매별 폴더 생성
            auction_dir = os.path.join(auction_images_dir, auction_no)
            os.makedirs(auction_dir, exist_ok=True)
            
            print(f"처리 중: {auction_no} ({len(files)}개 파일)")
            
            # 파일들을 해당 폴더로 이동
            for filename in files:
                src_path = os.path.join(auction_images_dir, filename)
                dst_path = os.path.join(auction_dir, filename)
                
                # 이미 존재하는 파일은 건너뛰기
                if os.path.exists(dst_path):
                    print(f"  건너뛰기 (이미 존재): {filename}")
                    continue
                
                # 파일 이동
                shutil.move(src_path, dst_path)
                moved_count += 1
                print(f"  이동 완료: {filename}")
            
            print(f"완료: {auction_no}")
            
        except Exception as e:
            print(f"오류 발생 ({auction_no}): {e}")
            error_count += 1
    
    print(f"\n=== 재정리 완료 ===")
    print(f"이동된 파일 수: {moved_count}")
    print(f"오류 발생 경매 수: {error_count}")
    print(f"처리된 경매 수: {len(auction_files)}")

def main():
    """메인 함수"""
    auction_images_dir = r"C:\projects\public\uploads\auction_images"
    
    if not os.path.exists(auction_images_dir):
        print(f"경로가 존재하지 않습니다: {auction_images_dir}")
        return
    
    # 사용자 확인
    print("경매 이미지를 폴더 구조로 재정리합니다.")
    print(f"대상 디렉토리: {auction_images_dir}")
    print("계속하시겠습니까? (y/N): ", end="")
    
    response = input().strip().lower()
    if response not in ['y', 'yes']:
        print("취소되었습니다.")
        return
    
    reorganize_auction_images(auction_images_dir)

if __name__ == "__main__":
    main()

