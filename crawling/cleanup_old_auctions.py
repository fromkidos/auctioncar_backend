#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Deletes old auction images (except for the representative one) and appraisal reports
for auctions with a sale_date older than a specified period (e.g., 30 days).
"""
import os
import time
import datetime
import logging.config
from dotenv import load_dotenv

# --- 환경변수 및 설정 로드 ---
# 이 스크립트가 crawling 디렉토리 내에 있다고 가정하고 경로 설정
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if not os.path.exists(dotenv_path):
    # fallback to the parent directory if not found in the current one
    dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path=dotenv_path)

# db_manager와 config는 crawling 디렉토리 내의 다른 모듈을 참조
from .crawling_auction_ongoing import config
from . import db_manager

# --- 로거 설정 ---
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "std": {"format": "%(asctime)s - %(levelname)s - %(name)s - %(funcName)s:%(lineno)d - %(message)s"}
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "std",
            "level": "INFO",
            "stream": "ext://sys.stdout"
        },
        "file": {
            "class": "logging.FileHandler",
            "formatter": "std",
            "level": "INFO",
            "filename": os.path.join(config.DEBUG_DIR, "cleanup_old_auctions.log"),
            "encoding": "utf-8",
            "mode": "a"
        }
    },
    "root": {
        "level": "INFO",
        "handlers": ["console", "file"]
    }
}
os.makedirs(config.DEBUG_DIR, exist_ok=True)
logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)

# --- 상수 정의 ---
CLEANUP_DAYS_START = 30  # 정리 시작 시점 (예: 30일 이전 데이터부터)
CLEANUP_DAYS_END = 60    # 정리 종료 시점 (예: 60일 이전 데이터까지)

def get_auctions_to_clean(db_conn):
    """지정된 기간 사이의 오래된 경매 목록을 데이터베이스에서 가져옵니다."""
    end_date = datetime.date.today() - datetime.timedelta(days=CLEANUP_DAYS_START)
    start_date = datetime.date.today() - datetime.timedelta(days=CLEANUP_DAYS_END)
    logger.info(f"{start_date}부터 {end_date} 사이의 매각기일을 가진 경매 정보를 정리 대상으로 조회합니다.")
    
    query = """
    SELECT auction_no, representative_photo_index
    FROM "AuctionBaseInfo"
    WHERE sale_date >= %s AND sale_date < %s;
    """
    try:
        with db_conn.cursor(cursor_factory=db_manager.psycopg2.extras.RealDictCursor) as cursor:
            cursor.execute(query, (start_date, end_date))
            auctions = cursor.fetchall()
            logger.info(f"총 {len(auctions)}개의 정리 대상 경매를 찾았습니다.")
            return auctions
    except Exception as e:
        logger.error(f"정리 대상 경매 조회 중 오류 발생: {e}", exc_info=True)
        return []

def cleanup_auction_files(db_conn, auction):
    """특정 경매 건에 대한 이미지와 감정평가서 파일을 정리합니다."""
    auction_no = auction['auction_no']
    representative_photo_index = auction['representative_photo_index']
    
    files_deleted_count = 0
    db_records_deleted_count = 0

    # 1. 이미지 파일 정리
    try:
        with db_conn.cursor(cursor_factory=db_manager.psycopg2.extras.RealDictCursor) as cursor:
            cursor.execute('SELECT photo_index, image_path_or_url FROM "PhotoURL" WHERE auction_no = %s;', (auction_no,))
            photos = cursor.fetchall()

        for photo in photos:
            # 대표 이미지는 건너뛰기
            if photo['photo_index'] == representative_photo_index:
                logger.info(f"[{auction_no}] 대표 이미지 (인덱스: {photo['photo_index']})는 건너뜁니다.")
                continue

            # URL이 아닌 로컬 파일 경로인 경우에만 삭제 시도
            image_filename = os.path.basename(photo['image_path_or_url'])
            if 'http' in image_filename:
                 logger.warning(f"[{auction_no}] 이미지 경로가 URL이므로 ({photo['image_path_or_url']}) 파일 삭제를 건너뜁니다.")
                 continue

            full_image_path = os.path.join(config.IMAGE_STORAGE_PATH, image_filename)

            try:
                if os.path.exists(full_image_path):
                    os.remove(full_image_path)
                    logger.info(f"[{auction_no}] 이미지 파일 삭제 성공: {full_image_path}")
                    files_deleted_count += 1

                    # 파일 삭제 성공 후 DB 레코드 삭제
                    with db_conn.cursor() as delete_cursor:
                        delete_cursor.execute('DELETE FROM "PhotoURL" WHERE auction_no = %s AND photo_index = %s;', (auction_no, photo['photo_index']))
                    db_records_deleted_count += 1
                else:
                    logger.warning(f"[{auction_no}] 이미지 파일이 존재하지 않아 삭제를 건너뜁니다: {full_image_path}")
                    # 파일이 없어도 DB 레코드는 불일치 데이터이므로 삭제
                    with db_conn.cursor() as delete_cursor:
                        delete_cursor.execute('DELETE FROM "PhotoURL" WHERE auction_no = %s AND photo_index = %s;', (auction_no, photo['photo_index']))
                    logger.info(f"[{auction_no}] 존재하지 않는 파일에 대한 DB 레코드 삭제 (인덱스: {photo['photo_index']})")
                    db_records_deleted_count += 1
            except Exception as e:
                logger.error(f"[{auction_no}] 이미지 파일 또는 DB 레코드 처리 중 오류 (인덱스: {photo['photo_index']}): {e}", exc_info=True)

    except Exception as e:
        logger.error(f"[{auction_no}] 사진 정보 조회 중 오류 발생: {e}", exc_info=True)

    # 2. 감정평가서 파일 정리
    appraisal_report_filename = f"{auction_no}_감정평가서.pdf"
    full_report_path = os.path.join(config.APPRAISAL_REPORTS_PATH, appraisal_report_filename)
    try:
        if os.path.exists(full_report_path):
            os.remove(full_report_path)
            logger.info(f"[{auction_no}] 감정평가서 삭제 성공: {full_report_path}")
            files_deleted_count += 1
        else:
            logger.info(f"[{auction_no}] 감정평가서가 존재하지 않습니다: {full_report_path}")
    except Exception as e:
        logger.error(f"[{auction_no}] 감정평가서 삭제 중 오류: {e}", exc_info=True)
        
    return files_deleted_count, db_records_deleted_count

def main():
    """스크립트의 메인 실행 함수입니다."""
    logger.info("오래된 경매 파일 정리 작업을 시작합니다.")
    start_time = time.monotonic()
    
    total_files_deleted = 0
    total_db_records_deleted = 0
    auctions_processed_count = 0

    try:
        with db_manager.get_db_connection() as conn:
            auctions_to_process = get_auctions_to_clean(conn)
            
            for auction in auctions_to_process:
                logger.info(f"--- 경매 [{auction['auction_no']}] 정리를 시작합니다. ---")
                files_deleted, db_records_deleted = cleanup_auction_files(conn, auction)
                total_files_deleted += files_deleted
                total_db_records_deleted += db_records_deleted
                auctions_processed_count += 1
                logger.info(f"--- 경매 [{auction['auction_no']}] 정리 완료. 삭제된 파일: {files_deleted}개, 삭제된 DB 레코드: {db_records_deleted}개 ---")
                
    except Exception as e:
        logger.critical(f"정리 작업 중 심각한 오류 발생: {e}", exc_info=True)

    end_time = time.monotonic()
    logger.info("모든 정리 작업을 완료했습니다.")
    logger.info(f"총 처리된 경매 건수: {auctions_processed_count}개")
    logger.info(f"총 삭제된 파일 수: {total_files_deleted}개")
    logger.info(f"총 삭제된 DB 레코드 수: {total_db_records_deleted}개")
    logger.info(f"총 소요 시간: {end_time - start_time:.2f}초")

if __name__ == "__main__":
    main()
