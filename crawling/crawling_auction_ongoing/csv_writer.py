#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Functions for reading and writing auction data to CSV files.
"""
import os
import csv
from . import config # For field name constants
import base64
import re # For parsing data URL mime type

# Define image output directory relative to CSV output dir
IMAGES_OUTPUT_DIR = os.path.join(config.CSV_OUTPUT_DIR, 'images')

def load_existing_auction_ids(filename: str) -> set[str]:
    """Loads existing auction IDs (auction_no) from the CSV file."""
    existing_ids = set()
    if not os.path.exists(filename):
        # print(f"Existing CSV file '{{filename}}' not found. Assuming no existing records.")
        return existing_ids
    try:
        with open(filename, 'r', newline='', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            # Check if 'auction_no' is in fieldnames, if not, try to read from basic_info_csv
            # This part might need adjustment if auction_no is guaranteed in a specific file
            # For now, we assume it could be in the main file being checked.
            if reader.fieldnames and 'auction_no' not in reader.fieldnames:
                # print(f"Warning: Column 'auction_no' not found in {{filename}}. This might be okay if checking against a detail file.")
                # If this is a new setup, auction_no might be in basic_info_filename
                # However, load_existing_auction_ids is usually called on the main combined file if it existed.
                # For a split setup, it should ideally check against config.AUCTION_BASIC_INFO_CSV
                pass # 경고 로그는 유지할 수 있으나, 일단 pass
            
            for row in reader:
                if 'auction_no' in row and row['auction_no']:
                    existing_ids.add(row['auction_no'])
        # print(f"Loaded {{len(existing_ids)}} existing auction IDs from {{filename}}.")
    except Exception as e:
        # print(f"Error loading existing auction IDs from {{filename}}: {{e}}")
        pass # 오류는 일단 조용히
    return existing_ids

def write_new_auctions_to_csv(records, basic_info_filename, detail_info_filename):
    """
    Writes new auction records to two separate CSV files:
    1. Basic Info: Contains fields defined in config.BASIC_INFO_FIELDNAMES.
    2. Detail Info: Contains all other fields, plus 'auction_no' for linking.
    """
    if not records:
        # print("No new records to write.")
        return

    # --- 기본 정보 저장 ---
    basic_fieldnames = config.BASIC_INFO_FIELDNAMES
    # Ensure auction_no is the first field if not already
    if 'auction_no' in basic_fieldnames:
        basic_fieldnames.remove('auction_no')
    basic_fieldnames.insert(0, 'auction_no')

    # print(f"Writing {{len(records)}} basic info records to {{basic_info_filename}} using fieldnames: {{basic_fieldnames}}")
    
    file_exists_basic = os.path.isfile(basic_info_filename)
    try:
        with open(basic_info_filename, 'a' if file_exists_basic else 'w', newline='', encoding='utf-8-sig') as csvfile_basic:
            writer_basic = csv.DictWriter(csvfile_basic, fieldnames=basic_fieldnames, extrasaction='ignore')
            if not file_exists_basic:
                writer_basic.writeheader()
            
            for record in records:
                row_to_write = {{fn: record.get(fn, '') for fn in basic_fieldnames}}
                writer_basic.writerow(row_to_write)
        # print(f"Successfully wrote {{len(records)}} basic info records to {{basic_info_filename}}")
    except IOError as e:
        # print(f"Error writing basic info to CSV file {{basic_info_filename}}: {{e}}")
        pass
    except Exception as e:
        # print(f"An unexpected error occurred during basic info CSV writing: {{e}}")
        pass

    # --- 세부 정보 저장 ---
    all_record_keys = set()
    if records:
        for r in records:
            all_record_keys.update(r.keys())
    
    # 세부 정보 필드: 전체 키에서 (기본 정보 필드 키 - {'auction_no'}) 를 뺀 것
    detail_fieldnames_set = (all_record_keys - (set(config.BASIC_INFO_FIELDNAMES) - {'auction_no'}))
    
    # 사용자가 명시적으로 제외 요청한 필드들 (이전에 추가했던 court_name은 세부 정보의 키가 될 수 있으므로 일단 유지)
    fields_to_exclude_explicitly = {
        'case_no', 
        'date_history', 
        'photo_urls', 
        'similar_stats', 
        'storage_location', 
        'total_photo_count'
    }
    detail_fieldnames_set -= fields_to_exclude_explicitly
    
    # 'auction_no'는 항상 포함되어야 함 (위의 set 연산에서 빠졌을 수 있으므로 다시 추가)
    # 또한, court_name도 세부 정보의 키로 사용하기로 했으므로 포함 (이전에 논의됨)
    key_fields_for_detail = {'auction_no', 'court_name'}
    detail_fieldnames_set.update(key_fields_for_detail) 

    # 순서 정의: key_fields_for_detail을 맨 앞에, 나머지는 config.FIELDNAMES_ALL 순서 기반 + 나머지 키들 정렬
    ordered_detail_fieldnames = list(key_fields_for_detail) # 순서 보장을 위해 list로 시작
    for fn_key in key_fields_for_detail: # 이미 추가된 키는 set에서 임시 제거 (정렬 대상에서 제외)
        detail_fieldnames_set.discard(fn_key)
    
    temp_detail_fieldnames = []
    # config.FIELDNAMES_ALL에 있는 세부 필드들 추가
    for fn in config.FIELDNAMES_ALL:
        if fn in detail_fieldnames_set:
            temp_detail_fieldnames.append(fn)
            detail_fieldnames_set.remove(fn) # 추가된 필드는 set에서 제거
            
    # config.FIELDNAMES_ALL에 없지만 detail_fieldnames_set에 남아있는 나머지 필드들 추가 (정렬)
    temp_detail_fieldnames.extend(sorted(list(detail_fieldnames_set)))
    
    ordered_detail_fieldnames.extend(temp_detail_fieldnames)
            
    # print(f"Writing {{len(records)}} detail info records to {{detail_info_filename}} using fieldnames: {{ordered_detail_fieldnames}}")

    file_exists_detail = os.path.isfile(detail_info_filename)
    try:
        with open(detail_info_filename, 'a' if file_exists_detail else 'w', newline='', encoding='utf-8-sig') as csvfile_detail:
            writer_detail = csv.DictWriter(csvfile_detail, fieldnames=ordered_detail_fieldnames, extrasaction='ignore')
            if not file_exists_detail:
                writer_detail.writeheader()
            
            for record in records:
                row_to_write = {{fn: record.get(fn, '') for fn in ordered_detail_fieldnames}}
                writer_detail.writerow(row_to_write)
        # print(f"Successfully wrote {{len(records)}} detail info records to {{detail_info_filename}}")
    except IOError as e:
        # print(f"Error writing detail info to CSV file {{detail_info_filename}}: {{e}}")
        pass
    except Exception as e:
        # print(f"An unexpected error occurred during detail info CSV writing: {{e}}")
        pass

def write_history_or_stats_to_csv(all_records: list[dict], data_key: str, filename: str, fieldnames: list[str]):
    """Writes specific history or stats data to a separate CSV file."""
    flattened_data = []
    if not all_records:
        # print(f"No records provided to extract {{data_key}} from.")
        return

    # Ensure mandatory identifier fields are first
    base_identifiers = ['auction_no', 'court_name']
    # Remove any existing identifiers from fieldnames to avoid duplication before inserting
    fieldnames = [f for f in fieldnames if f not in base_identifiers]
    # Prepend identifiers
    final_fieldnames = base_identifiers + fieldnames

    for record in all_records:
        data_to_write = record.get(data_key)
        identifiers = {bid: record.get(bid, 'N/A') for bid in base_identifiers}

        if data_to_write:
            if isinstance(data_to_write, list):
                for item in data_to_write:
                    if isinstance(item, dict):
                        item_copy = {**identifiers, **item} # Combine identifiers and item data
                        flattened_data.append(item_copy)
            elif isinstance(data_to_write, dict):
                item_copy = {**identifiers, **data_to_write}
                flattened_data.append(item_copy)
            else:
                 # print(f"Warning: Data for key '{{data_key}}' in record {{identifiers.get('auction_no')}} is not list/dict, skipping.")
                 pass

    if not flattened_data:
        # print(f"No valid '{{data_key}}' data found to write to {{filename}}.")
        return

    # print(f"Writing {{len(flattened_data)}} '{{data_key}}' items to {{filename}}.")
    try:
        with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
            # Dynamically adjust fieldnames based on the first item if it has extra keys
            if flattened_data:
                first_item_keys = list(flattened_data[0].keys())
                # Add any keys from the first item that aren't already in final_fieldnames
                for key in first_item_keys:
                    if key not in final_fieldnames:
                        final_fieldnames.append(key)

            writer = csv.DictWriter(f, fieldnames=final_fieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(flattened_data)
        # print(f"Successfully wrote {{data_key}} data to {{filename}}")
    except IOError as e:
        # print(f"Error writing {{data_key}} data to CSV file {{filename}}: {{e}}")
        pass
    except Exception as e:
        # print(f"An unexpected error occurred during {{data_key}} CSV write: {{e}}")
        pass

def write_photo_data_to_csv(all_records: list[dict], filename: str):
    """Writes photo data (file path or URL) to a separate CSV file.
       Decodes and saves Base64 data URLs as image files.
    """
    flattened_photos = []
    if not all_records:
        # print("No records provided to extract photo data.")
        return

    # Ensure image directory exists
    try:
        os.makedirs(IMAGES_OUTPUT_DIR, exist_ok=True)
    except OSError as e:
        # print(f"Error creating image directory {{IMAGES_OUTPUT_DIR}}: {{e}}")
        # Decide if we should stop or just continue without saving images
        # For now, let's stop if we can't create the directory
        return

    # Changed column name for clarity
    fieldnames = ['auction_no', 'court_name', 'photo_index', 'image_path_or_url']

    # print(f"Processing photo data for {{len(all_records)}} records...")
    saved_image_count = 0
    skipped_count = 0

    for record in all_records:
        photo_urls = record.get('photo_urls')
        auction_no = record.get('auction_no', 'N/A')
        court_name = record.get('court_name', 'N/A')
        identifiers = {
            'auction_no': auction_no,
            'court_name': court_name,
        }

        if isinstance(photo_urls, list):
            for index, url_or_data in enumerate(photo_urls):
                image_path_or_url = url_or_data # Default to original value
                is_data_url = False

                if isinstance(url_or_data, str) and url_or_data.startswith('data:image'):
                    is_data_url = True
                    try:
                        # Extract mime type and base64 data
                        header, encoded_data = url_or_data.split(',', 1)
                        mime_match = re.match(r'data:image/(?P<ext>\w+);base64', header)
                        if mime_match:
                            ext = mime_match.group('ext')
                        else:
                            ext = 'png' # Default extension if pattern fails

                        # Decode base64
                        image_data = base64.b64decode(encoded_data)

                        # Create filename
                        # Sanitize auction_no/court_name if they contain invalid path characters
                        safe_auction_no = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in str(auction_no))
                        safe_court_name = "".join(c if c.isalnum() or c in ('-', '_', ' ') else '_' for c in str(court_name))
                        image_filename = f"{safe_auction_no}_{safe_court_name}_{index}.{ext}"
                        image_filepath = os.path.join(IMAGES_OUTPUT_DIR, image_filename)

                        # Save image file
                        with open(image_filepath, 'wb') as img_file:
                            img_file.write(image_data)
                        image_path_or_url = image_filepath # Use the file path instead of the data URL
                        saved_image_count += 1

                    except (ValueError, TypeError, base64.binascii.Error, OSError, IndexError) as e:
                        # print(f"Error processing data URL for {{auction_no}} index {{index}}: {{e}}. Skipping.")
                        skipped_count += 1
                        continue # Skip this photo entry
                    except Exception as e:
                        # print(f"Unexpected error processing data URL for {{auction_no}} index {{index}}: {{e}}. Skipping.")
                        skipped_count += 1
                        continue # Skip this photo entry

                elif not isinstance(url_or_data, str):
                    # print(f"Warning: Non-string found in photo_urls for {{auction_no}} at index {{index}}. Skipping.")
                    skipped_count += 1
                    continue # Skip this photo entry

                # Append data (either original URL or new file path)
                photo_item = {**identifiers, 'photo_index': index, 'image_path_or_url': image_path_or_url}
                flattened_photos.append(photo_item)

        elif photo_urls:
             # print(f"Warning: photo_urls for {{auction_no}} is not a list. Type: {{type(photo_urls)}}. Skipping.")
             skipped_count += 1

    if not flattened_photos:
        # print(f"No valid photo data found to write (Saved: {{saved_image_count}}, Skipped: {{skipped_count}}).")
        return

    # print(f"Writing {{len(flattened_photos)}} photo data entries to {{filename}} (Saved: {{saved_image_count}}, Skipped: {{skipped_count}}).")
    try:
        with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(flattened_photos)
        # print(f"Successfully wrote photo data to {{filename}}")
    except IOError as e:
        # print(f"Error writing photo data to CSV file {{filename}}: {{e}}")
        pass
    except Exception as e:
        # print(f"An unexpected error occurred during photo data CSV write: {{e}}")
        pass 