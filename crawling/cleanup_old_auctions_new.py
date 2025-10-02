#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Deletes old auction images (except for the representative one) and appraisal reports
for auctions with a sale_date older than a specified period (e.g., 30 days).
Updated for new schema without PhotoURL table.
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
    SELECT auction_no, total_photo_count
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
    total_photo_count = auction['total_photo_count']
    
    files_deleted_count = 0
    
    # 1. 이미지 파일 정리 - total_photo_count를 사용하여 파일 삭제
    try:
        for i in range(total_photo_count):
            # 대표 이미지(첫 번째 이미지)는 건너뛰기
            if i == 0:
                logger.info(f"[{auction_no}] 대표 이미지 (인덱스: {i})는 건너뜁니다.")
                continue

            # 이미지 파일명 생성: {auction_no}_{index}.png
            image_filename = f"{auction_no}_{i}.png"
            full_image_path = os.path.join(config.IMAGE_STORAGE_PATH, image_filename)

            try:
                if os.path.exists(full_image_path):
                    os.remove(full_image_path)
                    logger.info(f"[{auction_no}] 이미지 파일 삭제 성공: {full_image_path}")
                    files_deleted_count += 1
                else:
                    logger.warning(f"[{auction_no}] 이미지 파일이 존재하지 않습니다: {full_image_path}")
            except Exception as e:
                logger.error(f"[{auction_no}] 이미지 파일 삭제 중 오류 발생: {e}")

    except Exception as e:
        logger.error(f"[{auction_no}] 이미지 파일 정리 중 오류 발생: {e}")

    # 2. 감정평가서 PDF 파일 정리
    try:
        pdf_filename = f"{auction_no}_감정평가서.pdf"
        full_pdf_path = os.path.join(config.APPRAISAL_REPORTS_PATH, pdf_filename)
        
        if os.path.exists(full_pdf_path):
            os.remove(full_pdf_path)
            logger.info(f"[{auction_no}] 감정평가서 PDF 삭제 성공: {full_pdf_path}")
            files_deleted_count += 1
        else:
            logger.warning(f"[{auction_no}] 감정평가서 PDF가 존재하지 않습니다: {full_pdf_path}")
    except Exception as e:
        logger.error(f"[{auction_no}] 감정평가서 PDF 삭제 중 오류 발생: {e}")

    # 3. 추출된 데이터 폴더 정리
    try:
        extracted_dir = os.path.join(config.APPRAISAL_REPORTS_PATH, "extracted")
        if os.path.exists(extracted_dir):
            # extracted 폴더 내의 모든 파일 삭제
            for filename in os.listdir(extracted_dir):
                file_path = os.path.join(extracted_dir, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    logger.info(f"[{auction_no}] 추출 데이터 파일 삭제: {file_path}")
                    files_deleted_count += 1
    except Exception as e:
        logger.error(f"[{auction_no}] 추출 데이터 폴더 정리 중 오류 발생: {e}")

    return files_deleted_count

def main():
    """메인 함수"""
    logger.info("오래된 경매 파일 정리 작업을 시작합니다.")
    
    start_time = time.time()
    total_auctions_processed = 0
    total_files_deleted = 0
    total_db_records_deleted = 0
    
    try:
        with db_manager.get_db_connection() as db_conn:
            if not db_conn:
                logger.error("데이터베이스 연결에 실패했습니다.")
                return
            
            # 정리 대상 경매 목록 조회
            auctions_to_clean = get_auctions_to_clean(db_conn)
            
            if not auctions_to_clean:
                logger.info("정리할 경매가 없습니다.")
                return
            
            # 각 경매에 대해 파일 정리 수행
            for auction in auctions_to_clean:
                try:
                    files_deleted = cleanup_auction_files(db_conn, auction)
                    total_files_deleted += files_deleted
                    total_auctions_processed += 1
                    
                    logger.info(f"[{auction['auction_no']}] 정리 완료 - 삭제된 파일: {files_deleted}개")
                    
                except Exception as e:
                    logger.error(f"[{auction['auction_no']}] 정리 중 오류 발생: {e}", exc_info=True)
                    continue
            
            # DB에서 경매 정보 삭제 (선택사항)
            # 주의: 이 부분은 실제 운영에서는 신중하게 고려해야 함
            # for auction in auctions_to_clean:
            #     try:
            #         with db_conn.cursor() as cursor:
            #             cursor.execute('DELETE FROM "AuctionBaseInfo" WHERE auction_no = %s;', (auction['auction_no'],))
            #         total_db_records_deleted += 1
            #         logger.info(f"[{auction['auction_no']}] DB 레코드 삭제 완료")
            #     except Exception as e:
            #         logger.error(f"[{auction['auction_no']}] DB 레코드 삭제 중 오류: {e}")
    
    except Exception as e:
        logger.error(f"정리 작업 중 전체 오류 발생: {e}", exc_info=True)
    
    # 작업 완료 로그
    elapsed_time = time.time() - start_time
    logger.info("모든 정리 작업이 완료되었습니다.")
    logger.info(f"처리된 경매 건수: {total_auctions_processed}개")
    logger.info(f"삭제된 파일 수: {total_files_deleted}개")
    logger.info(f"삭제된 DB 레코드 수: {total_db_records_deleted}개")
    logger.info(f"소요 시간: {elapsed_time:.2f}초")

if __name__ == "__main__":
    main()
