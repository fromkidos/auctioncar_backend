#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
리포트 추출 및 DB 저장 스크립트
"""
import os
import sys
import json
import shutil
from datetime import datetime
from typing import List, Dict, Any

# 경로 설정
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from crawling.crawling_auction_reports.report_parser import parse_pdf_to_output
from crawling.db_manager import get_db_connection, get_auction_base_by_auction_no
from crawling.crawling_auction_reports.utils import extract_auction_number

def get_today_reports(reports_dir: str) -> List[str]:
    """오늘 저장된 리포트 파일들을 찾습니다"""
    today = datetime.now().date()
    today_reports = []
    
    for filename in os.listdir(reports_dir):
        if filename.endswith('.pdf') and not filename.startswith('extracted'):
            file_path = os.path.join(reports_dir, filename)
            file_date = datetime.fromtimestamp(os.path.getmtime(file_path)).date()
            
            if file_date == today:
                today_reports.append(file_path)
    
    return today_reports

def save_images_to_upload_dir(extracted_dir: str, upload_dir: str, auction_no: str) -> int:
    """추출된 이미지를 업로드 디렉토리로 복사"""
    photos_dir = os.path.join(extracted_dir, "photos")
    if not os.path.exists(photos_dir):
        return 0
    
    # 업로드 디렉토리 생성
    auction_upload_dir = os.path.join(upload_dir, auction_no)
    os.makedirs(auction_upload_dir, exist_ok=True)
    
    # 이미지 파일들 복사
    image_files = [f for f in os.listdir(photos_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    
    for i, image_file in enumerate(image_files):
        src_path = os.path.join(photos_dir, image_file)
        dst_path = os.path.join(auction_upload_dir, f"{auction_no}_{i}.png")
        shutil.copy2(src_path, dst_path)
    
    return len(image_files)

def save_to_database(metadata: Dict[str, Any], auction_no: str) -> bool:
    """추출된 데이터를 DB에 저장"""
    try:
        with get_db_connection() as db_conn:
            if not db_conn:
                print(f"DB 연결 실패: {auction_no}")
                return False
            
            # AuctionBaseInfo 업데이트
            appraisal = metadata.get('appraisal', {})
            metadata_info = metadata.get('metadata', {})
            
            # total_photo_count 업데이트
            total_photo_count = metadata_info.get('total_photo_count', 0)
            update_base_info_sql = """
                UPDATE "AuctionBaseInfo" 
                SET total_photo_count = %s, updated_at = NOW()
                WHERE auction_no = %s
            """
            
            with db_conn.cursor() as cursor:
                cursor.execute(update_base_info_sql, (total_photo_count, auction_no))
                print(f"AuctionBaseInfo.total_photo_count 업데이트: {total_photo_count}")
            
            # AuctionDetailInfo 업데이트
            location_address = metadata.get('location_address')
            if location_address:
                update_detail_info_sql = """
                    UPDATE "AuctionDetailInfo" 
                    SET location_address = %s, updated_at = NOW()
                    WHERE auction_no = %s
                """
                
                with db_conn.cursor() as cursor:
                    cursor.execute(update_detail_info_sql, (location_address, auction_no))
                    print(f"AuctionDetailInfo.location_address 업데이트: {location_address[:50]}...")
            
            # AuctionAppraisalSummary 업데이트
            appraisal_type = appraisal.get('type', 'car')
            
            # 필드 매핑 (car vs ship)
            if appraisal_type == 'car':
                field_mapping = {
                    'summary_year_mileage': appraisal.get('year_and_mileage'),
                    'summary_color': appraisal.get('color'),
                    'summary_management_status': appraisal.get('condition'),
                    'summary_fuel': appraisal.get('fuel'),
                    'summary_inspection_validity': appraisal.get('inspection_validity'),
                    'summary_options_etc': appraisal.get('etc')
                }
            else:  # ship
                field_mapping = {
                    'summary_year_mileage': appraisal.get('hull_status'),
                    'summary_color': appraisal.get('engine_status'),
                    'summary_management_status': appraisal.get('equipment_status'),
                    'summary_fuel': appraisal.get('operation_info'),
                    'summary_inspection_validity': appraisal.get('inspection_location'),
                    'summary_options_etc': appraisal.get('ship_etc')
                }
            
            # AuctionAppraisalSummary 업데이트 또는 삽입
            upsert_sql = """
                INSERT INTO "AuctionAppraisalSummary" (
                    auction_no, summary_year_mileage, summary_color, 
                    summary_management_status, summary_fuel, 
                    summary_inspection_validity, summary_options_etc,
                    created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                ON CONFLICT (auction_no) DO UPDATE SET
                    summary_year_mileage = EXCLUDED.summary_year_mileage,
                    summary_color = EXCLUDED.summary_color,
                    summary_management_status = EXCLUDED.summary_management_status,
                    summary_fuel = EXCLUDED.summary_fuel,
                    summary_inspection_validity = EXCLUDED.summary_inspection_validity,
                    summary_options_etc = EXCLUDED.summary_options_etc,
                    updated_at = NOW()
            """
            
            with db_conn.cursor() as cursor:
                cursor.execute(upsert_sql, (
                    auction_no,
                    field_mapping['summary_year_mileage'],
                    field_mapping['summary_color'],
                    field_mapping['summary_management_status'],
                    field_mapping['summary_fuel'],
                    field_mapping['summary_inspection_validity'],
                    field_mapping['summary_options_etc']
                ))
                print(f"AuctionAppraisalSummary 업데이트 완료 (타입: {appraisal_type})")
            
            db_conn.commit()
            return True
            
    except Exception as e:
        print(f"DB 저장 실패: {auction_no} - {e}")
        return False

def process_single_report(pdf_path: str, upload_dir: str) -> bool:
    """단일 리포트 처리"""
    try:
        print(f"\n처리 중: {os.path.basename(pdf_path)}")
        
        # 경매 번호 추출
        auction_no = extract_auction_number(os.path.basename(pdf_path))
        if not auction_no:
            print(f"경매 번호 추출 실패: {pdf_path}")
            return False
        
        print(f"경매 번호: {auction_no}")
        
        # DB에서 경매 정보 확인
        with get_db_connection() as db_conn:
            if not db_conn:
                print(f"DB 연결 실패")
                return False
            
            auction_info = get_auction_base_by_auction_no(db_conn, auction_no)
            if not auction_info:
                print(f"DB에서 경매 정보를 찾을 수 없음: {auction_no}")
                return False
            
            print(f"DB에서 경매 정보 확인: {auction_no}")
        
        # PDF 추출
        result = parse_pdf_to_output(pdf_path)
        
        # metadata.json 읽기
        extracted_dir = os.path.join(os.path.dirname(pdf_path), "extracted")
        metadata_file = os.path.join(extracted_dir, "metadata.json")
        
        if not os.path.exists(metadata_file):
            print(f"metadata.json 파일이 없습니다: {metadata_file}")
            return False
        
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        print(f"PDF 추출 완료: {result.pdf_filename}")
        
        # 이미지 복사
        image_count = save_images_to_upload_dir(extracted_dir, upload_dir, auction_no)
        print(f"이미지 복사 완료: {image_count}개")
        
        # DB 저장
        if save_to_database(metadata, auction_no):
            print(f"DB 저장 완료: {auction_no}")
            return True
        else:
            print(f"DB 저장 실패: {auction_no}")
            return False
            
    except Exception as e:
        print(f"리포트 처리 실패: {pdf_path} - {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """메인 함수"""
    print("리포트 추출 및 DB 저장 시작")
    
    # 설정
    reports_dir = r"C:\projects\public\uploads\appraisal_reports"
    upload_dir = r"C:\projects\public\uploads\auction_images"
    
    # 오늘 저장된 리포트 찾기
    today_reports = get_today_reports(reports_dir)
    
    if not today_reports:
        print("오늘 저장된 리포트가 없습니다. 최근 파일들을 확인합니다...")
        # 최근 파일들 확인
        all_pdfs = [os.path.join(reports_dir, f) for f in os.listdir(reports_dir) 
                   if f.endswith('.pdf') and not f.startswith('extracted')]
        if all_pdfs:
            # 최근 3개 파일 사용
            today_reports = sorted(all_pdfs, key=os.path.getmtime, reverse=True)[:3]
            print(f"최근 파일 {len(today_reports)}개를 처리합니다.")
        else:
            print("처리할 PDF 파일이 없습니다.")
            return
    
    print(f"처리할 리포트: {len(today_reports)}개")
    
    # 각 리포트 처리
    success_count = 0
    for pdf_path in today_reports:
        if process_single_report(pdf_path, upload_dir):
            success_count += 1
    
    print(f"\n처리 완료: {success_count}/{len(today_reports)}개 성공")

if __name__ == "__main__":
    main()
