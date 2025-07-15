#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
One-time script to parse appraisal_summary_text from AuctionDetailInfo,
and migrate the structured data to the AuctionAppraisalSummary table.
"""
import os
import sys
import time
import traceback

# Ensure crawling package can be found for imports
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR) # Assumes crawling is a subdir of project root
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from crawling.db_manager import get_db_connection, insert_or_update_appraisal_summary
from crawling.crawling_auction_ongoing.parsers import parse_appraisal_summary
import crawling.crawling_auction_ongoing.config as config # For DEBUG flag

def main():
    db_conn = None
    processed_count = 0
    successfully_migrated_count = 0
    skipped_count = 0
    error_count = 0
    already_exists_skipped_count = 0
    debug_log_count = 0  # 디버그 로그 카운터
    MAX_DEBUG_LOGS = 10  # 최대 디버그 로그 수

    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Starting appraisal summary migration script.")

    try:
        db_conn = get_db_connection()
        if not db_conn:
            print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Database connection failed. Exiting.")
            return

        cursor = db_conn.cursor()

        # Select auction_no (unique auction identifier), item_no (context for parsing), 
        # and appraisal_summary_text.
        # auction_no from AuctionDetailInfo is the primary key for AuctionAppraisalSummary.
        # item_no from AuctionBaseInfo provides context for which part of the summary to extract.
        select_query = """
            SELECT adi.auction_no, abi.item_no, adi.appraisal_summary_text
            FROM "AuctionDetailInfo" adi
            JOIN "AuctionBaseInfo" abi ON adi.auction_no = abi.auction_no
            WHERE adi.appraisal_summary_text IS NOT NULL AND adi.appraisal_summary_text != '';
        """
        # This query assumes:
        # 1. AuctionDetailInfo.auction_no is the unique ID like "사건번호-물건번호" (e.g., "2023본123-1").
        # 2. AuctionBaseInfo.auction_no matches AuctionDetailInfo.auction_no and is unique in AuctionBaseInfo.
        # 3. AuctionBaseInfo.item_no is the specific "기호" for that auction_id (now auction_no).

        cursor.execute(select_query)
        records = cursor.fetchall()

        if not records:
            print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - No records found in AuctionDetailInfo with non-empty appraisal_summary_text. Nothing to migrate.")
            return

        print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Found {len(records)} records to process. Starting migration...")

        for auction_no_pk, item_no_context, summary_text in records:
            processed_count += 1
            if config.DEBUG:
                print(f"\n{time.strftime('%Y-%m-%d %H:%M:%S')} - Processing: AuctionNo='{auction_no_pk}', ItemNoContext='{item_no_context}'")

            # Check if data already exists in AuctionAppraisalSummary
            try:
                check_exists_query = 'SELECT 1 FROM "AuctionAppraisalSummary" WHERE auction_no = %s LIMIT 1;'
                cursor.execute(check_exists_query, (auction_no_pk,))
                if cursor.fetchone():
                    if config.DEBUG:
                        print(f"DEBUG: Data for AuctionNo='{auction_no_pk}' already exists in AuctionAppraisalSummary. Skipping.")
                    already_exists_skipped_count += 1
                    continue
            except Exception as e_check:
                error_count += 1
                print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - ERROR checking existence for AuctionNo='{auction_no_pk}': {e_check}")
                if config.DEBUG:
                    traceback.print_exc()
                continue

            # summary_text is already checked by the SQL query for NOT NULL and not empty.
            
            try:
                parsed_summary_items = parse_appraisal_summary(auction_no_pk, item_no_context, summary_text)

                if not parsed_summary_items:
                    if config.DEBUG: print(f"DEBUG: No summary items parsed for AuctionNo='{auction_no_pk}', ItemNoContext='{item_no_context}'. Skipping.")
                    skipped_count += 1
                    continue

                summary_to_save_from_parser = None
                for parsed_item in parsed_summary_items:
                    if parsed_item.get('item_no') == item_no_context:
                        summary_to_save_from_parser = parsed_item
                        break
                
                if summary_to_save_from_parser:
                    data_for_db = {
                        k: v for k, v in summary_to_save_from_parser.items()
                        if k in [
                            "summary_year_mileage", "summary_color", "summary_management_status",
                            "summary_fuel", "summary_inspection_validity", "summary_options_etc"
                        ]
                    }
                    
                    # === 상세 디버그 로깅 추가 시작 ===
                    if config.DEBUG and debug_log_count < MAX_DEBUG_LOGS:
                        print(f"\n--- DEBUG LOG #{debug_log_count + 1} (AuctionNo: {auction_no_pk}, ItemNoContext: {item_no_context}) ---")
                        print(">>> Original Appraisal Summary Text:")
                        print(summary_text)
                        print("\n>>> All Parsed Summary Items (from parse_appraisal_summary):")
                        # parsed_summary_items 리스트의 각 딕셔너리를 예쁘게 출력
                        if parsed_summary_items:
                            for i, item_dict in enumerate(parsed_summary_items):
                                print(f"  Item [{i}]:")
                                for key, val in item_dict.items():
                                    print(f"    {key}: {val}")
                        else:
                            print("  (No items were parsed)")
                        
                        print("\n>>> Selected Summary Item for DB (summary_to_save_from_parser):")
                        if summary_to_save_from_parser:
                            for key, val in summary_to_save_from_parser.items():
                                print(f"  {key}: {val}")
                        else:
                             print("  (No specific item was selected for this context)")
                        
                        print("\n>>> Data for DB (data_for_db - filtered):")
                        if data_for_db:
                            for key, val in data_for_db.items():
                                print(f"  {key}: {val}")
                        else:
                            print("  (No data to be saved to DB after filtering)")
                        print("--- END DEBUG LOG ---")
                        debug_log_count += 1
                    # === 상세 디버그 로깅 추가 끝 ===
                    
                    if not any(data_for_db.values()): # Check if all parsed fields are None or empty
                        if config.DEBUG: print(f"DEBUG: All parsed fields are empty for AuctionNo='{auction_no_pk}', ItemNoContext='{item_no_context}'. Skipping DB insert.")
                        skipped_count += 1
                        continue
                    
                    # The insert_or_update_appraisal_summary function handles the upsert logic.
                    # It expects the db_connection, the primary key (auction_no_pk), 
                    # and a dictionary of the summary fields.
                    success = insert_or_update_appraisal_summary(db_conn, auction_no_pk, data_for_db)
                    
                    if success:
                        if config.DEBUG: print(f"DEBUG: Successfully prepared/updated summary for AuctionNo='{auction_no_pk}', ItemNoContext='{item_no_context}'")
                        successfully_migrated_count += 1
                    else:
                        # DB 작업 실패 시 error_count를 증가시키고 루프를 중단하여 전체 롤백 유도
                        error_count += 1
                        print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - CRITICAL: DB operation failed for AuctionNo='{auction_no_pk}'. Aborting further processing to ensure rollback.")
                        break # 루프 중단
                else:
                    if config.DEBUG: print(f"DEBUG: No matching summary found for ItemNoContext='{item_no_context}' within parsed items for AuctionNo='{auction_no_pk}'. Skipping DB insert.")
                    skipped_count += 1

            except Exception as e_inner:
                error_count += 1
                print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - ERROR processing AuctionNo='{auction_no_pk}', ItemNoContext='{item_no_context}': {e_inner}")
                if config.DEBUG:
                    traceback.print_exc()
                # 내부 예외 발생 시에도 루프를 중단하여 전체 롤백 유도
                print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - CRITICAL: Exception during processing for AuctionNo='{auction_no_pk}'. Aborting further processing to ensure rollback.")
                break # 루프 중단
        
        # Transaction control: commit if no errors, otherwise rollback.
        if error_count > 0:
            print(f"\n{time.strftime('%Y-%m-%d %H:%M:%S')} - Encountered {error_count} errors during processing. Rolling back all changes.")
            db_conn.rollback()
        elif successfully_migrated_count > 0:
            print(f"\n{time.strftime('%Y-%m-%d %H:%M:%S')} - Committing {successfully_migrated_count} successful migrations to the database.")
            db_conn.commit()
        else:
            print(f"\n{time.strftime('%Y-%m-%d %H:%M:%S')} - No data was successfully migrated or no changes requiring commit were made.")

    except Exception as e_outer:
        print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - An unexpected error occurred during the migration script: {e_outer}")
        traceback.print_exc()
        if db_conn:
            db_conn.rollback() # Rollback in case of a global error
    finally:
        if db_conn:
            db_conn.close()
            print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Database connection closed.")
        
        print(f"\n{time.strftime('%Y-%m-%d %H:%M:%S')} --- Migration Summary ---")
        print(f"Total records fetched from AuctionDetailInfo: {processed_count if 'records' in locals() and records else 0} (queried: {len(records) if 'records' in locals() and records else 'N/A'})")
        print(f"Records processed in loop: {processed_count}")
        print(f"Successfully migrated/updated in AuctionAppraisalSummary: {successfully_migrated_count}")
        print(f"Skipped (already exists in target table): {already_exists_skipped_count}")
        print(f"Skipped (e.g., no parse result, no matching item_no, or all fields empty): {skipped_count}")
        print(f"Errors encountered during item processing: {error_count}")
        
        if 'e_outer' in locals() and e_outer:
             print("The script terminated due to an unexpected error.")
        if error_count > 0:
            print("Due to item processing errors, all potential changes were rolled back.")
        elif successfully_migrated_count > 0:
            print("Changes have been committed to the database.")
        elif processed_count > 0 : # Processed records but nothing committed (e.g. all skipped)
             print("No records resulted in changes to be committed to the database.")
        else: # No records processed or fetched initially
            print("No records were processed or no changes were made to the database.")

if __name__ == "__main__":
    # If your project uses .env files, you might need to load them here,
    # especially if config.py or db_manager.py rely on environment variables
    # that are not set globally.
    # Example:
    # from dotenv import load_dotenv
    # # Adjust path to .env file as needed, e.g., os.path.join(PROJECT_ROOT, '.env')
    # dotenv_path = os.path.join(PROJECT_ROOT, '.env') 
    # if os.path.exists(dotenv_path):
    #     load_dotenv(dotenv_path=dotenv_path)
    #     if config.DEBUG: print(f"DEBUG: Loaded .env from {dotenv_path}")
    # else:
    #     if config.DEBUG: print(f"DEBUG: .env file not found at {dotenv_path}")
    # load_dotenv() # Or use default behavior if preferred

    main()
