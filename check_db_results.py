#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DB 저장 결과 확인 스크립트
"""
import sys
import os

# 경로 설정
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'crawling'))

from db_manager import get_db_connection

def check_db_results():
    """DB 저장 결과 확인"""
    try:
        with get_db_connection() as conn:
            if not conn:
                print("DB 연결 실패")
                return
            
            cursor = conn.cursor()
            
            # AuctionBaseInfo 확인
            print("=== AuctionBaseInfo 확인 ===")
            cursor.execute('''
                SELECT auction_no, total_photo_count 
                FROM "AuctionBaseInfo" 
                WHERE auction_no IN ('2025타경33213-1', '2025타경32980-1', '2025타경32835-1')
                ORDER BY auction_no
            ''')
            
            for row in cursor.fetchall():
                print(f"{row[0]}: {row[1]}개 사진")
            
            # AuctionDetailInfo 확인
            print("\n=== AuctionDetailInfo 확인 ===")
            cursor.execute('''
                SELECT auction_no, location_address 
                FROM "AuctionDetailInfo" 
                WHERE auction_no IN ('2025타경33213-1', '2025타경32980-1', '2025타경32835-1')
                ORDER BY auction_no
            ''')
            
            for row in cursor.fetchall():
                address = row[1][:50] + "..." if row[1] and len(row[1]) > 50 else row[1]
                print(f"{row[0]}: {address}")
            
            # AuctionAppraisalSummary 확인
            print("\n=== AuctionAppraisalSummary 확인 ===")
            cursor.execute('''
                SELECT auction_no, summary_year_mileage, summary_color, summary_management_status
                FROM "AuctionAppraisalSummary" 
                WHERE auction_no IN ('2025타경33213-1', '2025타경32980-1', '2025타경32835-1')
                ORDER BY auction_no
            ''')
            
            for row in cursor.fetchall():
                year_mileage = row[1][:30] + "..." if row[1] and len(row[1]) > 30 else row[1]
                print(f"{row[0]}:")
                print(f"  - 연식/주행거리: {year_mileage}")
                print(f"  - 색상: {row[2]}")
                print(f"  - 관리상태: {row[3][:30] + '...' if row[3] and len(row[3]) > 30 else row[3]}")
                print()
            
            print("DB 확인 완료!")
            
    except Exception as e:
        print(f"DB 확인 실패: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_db_results()
