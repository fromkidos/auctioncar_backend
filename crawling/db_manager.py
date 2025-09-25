import psycopg2
import psycopg2.extras # RealDictCursor 사용 위해 추가
import os
from dotenv import load_dotenv
from urllib.parse import urlparse
from decimal import Decimal, InvalidOperation # Decimal 타입 사용 위해 추가
import datetime # datetime 타입 사용 위해 추가
import time # time 모듈 추가 (로그용)
from contextlib import contextmanager # 추가
from .crawling_auction_result import car_auction_config as config # 경로 수정
import json # ADDED

# .env 파일 경로 탐색 (이제 crawling 디렉토리에만 있다고 가정)
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')

if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path=dotenv_path)
    # print(f"db_manager: Loaded .env from {dotenv_path}") # 디버깅용
else:
    # crawling 디렉토리에 .env 파일이 없는 경우에 대한 fallback 또는 로깅
    # print(f"db_manager: .env not found at {dotenv_path}. Attempting default load_dotenv().") # 디버깅용
    load_dotenv() # 기본 동작 (현재 디렉토리 등에서 찾음)

DATABASE_URL = os.getenv("DATABASE_URL")

@contextmanager
def get_db_connection():
    """PostgreSQL 데이터베이스 연결을 생성하고 컨텍스트 매니저로 관리합니다.
    성공 시 커밋, 예외 발생 시 롤백하며 항상 연결을 닫습니다.
    """
    if not DATABASE_URL:
        print("오류: DATABASE_URL 환경 변수가 설정되지 않았습니다.")
        raise ValueError("DATABASE_URL 환경 변수가 설정되지 않았습니다.")
    
    conn = None
    try:
        result = urlparse(DATABASE_URL)
        conn = psycopg2.connect(
            dbname=result.path[1:],
            user=result.username,
            password=result.password,
            host=result.hostname,
            port=result.port
        )
        yield conn # 연결 객체 반환
        conn.commit() # with 블록 성공적으로 완료 시 커밋
    except Exception as e:
        if conn:
            conn.rollback() # 예외 발생 시 롤백
        # print(f"데이터베이스 작업 중 오류: {e}") # update_ongoing_auctions.py의 main에서 이미 로깅하고 있음
        raise # 예외를 다시 발생시켜 호출자가 알 수 있도록 함
    finally:
        if conn:
            conn.close() # 항상 연결 종료

def clean_string(value):
    """문자열에서 NUL 바이트와 HTML 태그를 제거하거나, None이면 빈 문자열 반환"""
    if value is None:
        return ''
    
    # 문자열로 변환
    str_value = str(value)
    
    # NUL 바이트 제거
    str_value = str_value.replace('\x00', '').replace('\u0000', '')
    
    # HTML 태그가 포함되어 있는 경우 BeautifulSoup으로 정리
    if '<' in str_value and '>' in str_value:
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(str_value, 'html.parser')
            str_value = soup.get_text(strip=True)
        except Exception:
            # BeautifulSoup 실패 시 정규식으로 HTML 태그 제거
            import re
            str_value = re.sub(r'<[^>]+>', '', str_value)
    
    return str_value

def to_decimal_or_none(value, default_if_empty=None):
    """문자열을 Decimal로 변환, 실패 시 None 또는 기본값 반환. 쉼표 제거."""
    if isinstance(value, (int, float, Decimal)):
        return Decimal(value)
    if isinstance(value, str):
        cleaned_value = value.replace(',', '').strip()
        if not cleaned_value: # 빈 문자열인 경우
            return default_if_empty
        try:
            return Decimal(cleaned_value)
        except InvalidOperation:
            return None
    return None

def to_int_or_none(value, default_if_empty=None, field_name_for_logging="Unknown Field"):
    """문자열을 int로 변환, 실패 시 None 또는 기본값 반환. 쉼표 제거 및 '년' 등 접미사 제거."""
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        cleaned_value = value.replace(',', '').replace('년', '').replace('km', '').strip() # 예시 접미사 제거
        if not cleaned_value:
            return default_if_empty
        try:
            return int(cleaned_value)
        except ValueError:
            if config.DEBUG or True: # 항상 로그를 남기도록 True로 설정 (임시)
                print(f"{time.strftime('%H:%M:%S')} - DEBUG_INT_CONVERSION: Failed to convert '{value}' (cleaned: '{cleaned_value}') to int for field '{field_name_for_logging}'. Returning None.")
            return None
    if value is not None and not isinstance(value, (int,str)):
        if config.DEBUG or True:
            print(f"{time.strftime('%H:%M:%S')} - DEBUG_INT_CONVERSION: Received non-string/non-int type '{type(value)}' for field '{field_name_for_logging}' (value: {value}). Returning None.")
    return None

def parse_custom_date(date_str, default_if_empty=None):
    if not date_str or not isinstance(date_str, str) or date_str.strip().lower() == 'n/a':
        return default_if_empty
    
    # 입력 문자열 양 끝의 공백 제거 및 혹시 있을 수 있는 마지막 점(.) 제거
    cleaned_date_str = date_str.strip().rstrip('.') 
    
    # 시도할 날짜/시간 형식 리스트 (자주 사용되거나 예상되는 형식 우선)
    formats_to_try = [
        "%Y.%m.%d %H:%M",      # 예: '2025.06.17 10:00'
        "%Y-%m-%d %H:%M",      # 예: '2025-06-17 10:00'
        "%Y.%m.%d %H:%M:%S",   # 예: '2025.06.17 10:00:00'
        "%Y-%m-%d %H:%M:%S",   # 예: '2025-06-17 10:00:00'
        "%Y.%m.%d",            # 예: '2025.06.17' (시간 정보 없음)
        "%Y-%m-%d"             # 예: '2025-06-17' (시간 정보 없음)
    ]

    for fmt in formats_to_try:
        try:
            return datetime.datetime.strptime(cleaned_date_str, fmt)
        except ValueError:
            continue
    
    # 폴백: 기존 괄호 분리 로직 (혹시 'YYYY.MM.DD (HH:MM)' 같은 형식이 다시 사용될 경우 대비)
    try:
        date_part_fallback = cleaned_date_str.split('(')[0].strip()
        if date_part_fallback != cleaned_date_str: # 괄호가 실제로 있어서 분리가 일어났다면
            return datetime.datetime.strptime(date_part_fallback, '%Y.%m.%d')
    except ValueError:
        pass # 이마저도 실패하면 아래 로깅 후 기본값 반환

    # 모든 형식 시도 실패 시 로깅
    # config.DEBUG 조건은 유지하되, 실제 운영 시에는 로깅 레벨 조정 필요
    if config.DEBUG: 
        print(f"{time.strftime('%H:%M:%S')} - parse_custom_date: 제공된 모든 형식으로 날짜 문자열 파싱 실패: 원본='{date_str}', 정리된값='{cleaned_date_str}'")
    return default_if_empty

def insert_auction_base_info(db_conn, data: dict):
    if not db_conn:
        if config.DEBUG: print("DB 연결 실패: AuctionBaseInfo 삽입 불가")
        return False
    try:
        cur = db_conn.cursor()

        sql = """
        INSERT INTO "AuctionBaseInfo" (
            auction_no, case_year, case_number, item_no, court_name, 
            appraisal_price, min_bid_price, min_bid_price_2, sale_date, status, car_name, 
            car_model_year, car_reg_number, car_mileage, car_fuel, 
            car_transmission, car_type, manufacturer, updated_at
        ) VALUES (
            %(auction_no)s, %(case_year)s, %(case_number)s, %(item_no)s, %(court_name)s,
            %(appraisal_price)s, %(min_bid_price)s, %(min_bid_price_2)s, %(sale_date)s, %(status)s, %(car_name)s,
            %(car_model_year)s, %(car_reg_number)s, %(car_mileage)s, %(car_fuel)s,
            %(car_transmission)s, %(car_type)s, %(manufacturer)s, %(updated_at)s
        )
        ON CONFLICT (auction_no) DO UPDATE SET
            case_year = EXCLUDED.case_year,
            case_number = EXCLUDED.case_number,
            item_no = EXCLUDED.item_no,
            court_name = EXCLUDED.court_name,
            appraisal_price = EXCLUDED.appraisal_price,
            min_bid_price = EXCLUDED.min_bid_price,
            min_bid_price_2 = EXCLUDED.min_bid_price_2,
            sale_date = EXCLUDED.sale_date,
            status = EXCLUDED.status,
            car_name = EXCLUDED.car_name,
            car_model_year = EXCLUDED.car_model_year,
            car_reg_number = EXCLUDED.car_reg_number,
            car_mileage = EXCLUDED.car_mileage,
            car_fuel = EXCLUDED.car_fuel,
            car_transmission = EXCLUDED.car_transmission,
            car_type = EXCLUDED.car_type,
            manufacturer = EXCLUDED.manufacturer,
            updated_at = EXCLUDED.updated_at;
        """
        
        params = {
            'auction_no': clean_string(data.get('auction_no')),
            'case_year': to_int_or_none(data.get('case_year'), field_name_for_logging='case_year'),
            'case_number': clean_string(data.get('case_number')),
            'item_no': to_int_or_none(data.get('item_no'), field_name_for_logging='item_no'),
            'court_name': clean_string(data.get('court_name')),
            'appraisal_price': to_int_or_none(data.get('appraisal_price'), field_name_for_logging='appraisal_price'),
            'min_bid_price': to_int_or_none(data.get('min_bid_price'), field_name_for_logging='min_bid_price'),
            'min_bid_price_2': to_int_or_none(data.get('min_bid_price_2'), field_name_for_logging='min_bid_price_2'),
            'sale_date': data.get('sale_date') if isinstance(data.get('sale_date'), datetime.datetime) else parse_custom_date(data.get('sale_date')),
            'status': clean_string(data.get('status')),
            'car_name': clean_string(data.get('car_name')),
            'car_model_year': to_int_or_none(data.get('car_model_year'), field_name_for_logging='car_model_year'),
            'car_reg_number': clean_string(data.get('car_reg_number')),
            'car_mileage': to_int_or_none(data.get('car_mileage'), field_name_for_logging='car_mileage'),
            'car_fuel': clean_string(data.get('car_fuel')),
            'car_transmission': clean_string(data.get('car_transmission')),
            'car_type': clean_string(data.get('car_type')),
            'manufacturer': clean_string(data.get('manufacturer')),
            'updated_at': datetime.datetime.now()  # 현재 시간으로 updated_at 설정
        }
        
        if config.DEBUG: # 파라미터 전체 로깅 추가
            log_params_base = {k: str(v) if isinstance(v, (datetime.datetime, datetime.date)) else v for k, v in params.items()}
            print(f"{time.strftime('%H:%M:%S')} - DEBUG_DB_PARAMS (AuctionBaseInfo for {params.get('auction_no')}): {log_params_base}")

        if not params['auction_no']:
            print(f"오류: auction_no가 없어 AuctionBaseInfo 삽입/업데이트 불가: {data}")
            return False

        # psycopg2로 전달 직전 appraisal_price 값 및 타입 로깅
        appraisal_price_to_db = params.get('appraisal_price')
        print(f"{time.strftime('%H:%M:%S')} - DEBUG_APPRAISAL_PRICE_FINAL: auction_no={params.get('auction_no')}, appraisal_price for DB: {appraisal_price_to_db} (Type: {type(appraisal_price_to_db)})")

        cur.execute(sql, params)
        cur.close()
        return True
    except Exception as e:
        db_conn.rollback()
        print(f"AuctionBaseInfo 삽입/업데이트 중 오류: {e} (데이터: {data.get('auction_no')})")
        import traceback
        traceback.print_exc()
        return False

def insert_auction_date_history(db_conn, auction_no: str, court_name: str, date_history_list: list[dict]):
    if not db_conn:
        if config.DEBUG: print("DB 연결 실패: AuctionDateHistory 삽입 불가")
        return False
    try:
        cur = db_conn.cursor()
        success_count = 0
        failure_count = 0

        sql = """
        INSERT INTO "DateHistory" (
            auction_no, court_name, date_time, type, location, min_bid_price, result
        ) VALUES (
            %(auction_no)s, %(court_name)s, %(date_time)s, %(type)s, 
            %(location)s, %(min_bid_price)s, %(result)s
        )
        ON CONFLICT (auction_no, date_time, type) DO NOTHING;
        """

        for item in date_history_list:
            try:
                params = {
                    'auction_no': clean_string(auction_no),
                    'court_name': clean_string(court_name),
                    'date_time': item.get('기일'),
                    'type': clean_string(item.get('기일종류')),
                    'location': clean_string(item.get('기일장소')),
                    'min_bid_price': to_int_or_none(item.get('최저매각가격')),
                    'result': clean_string(item.get('기일결과'))
                }
                
                # 필수 값 체크 (예: date_time, type)
                if not params['date_time'] or not params['type']:
                    print(f"오류: DateHistory 필수 값 누락 (기일 또는 기일종류) for auction_no {auction_no}. 항목 건너뜀: {item}")
                    failure_count += 1
                    continue

                cur.execute(sql, params)
                if cur.rowcount > 0: # 실제로 삽입된 경우 (ON CONFLICT DO NOTHING으로 인해 0일 수 있음)
                    success_count += 1
            except Exception as item_e:
                print(f"DateHistory 항목 삽입 중 오류 (auction_no: {auction_no}, item: {item}): {item_e}")
                failure_count += 1
                # 개별 항목 오류 시 롤백하지 않고 계속 진행 (선택 사항)

        cur.close()
        return failure_count == 0

    except Exception as e:
        db_conn.rollback()
        print(f"insert_auction_date_history 중 전체 오류 (auction_no: {auction_no}): {e}")
        import traceback
        traceback.print_exc()
        return False

def insert_photo_urls(db_conn, auction_no: str, court_name: str, photo_data_list: list[dict]):
    if not db_conn:
        if config.DEBUG: print(f"DB 연결 실패: PhotoURL 삽입 불가 (auction_no: {auction_no})")
        return False
    try:
        cur = db_conn.cursor()
        success_count = 0
        failure_count = 0

        sql = """
        INSERT INTO "PhotoURL" (auction_no, court_name, photo_index, image_path_or_url) 
        VALUES (%(auction_no)s, %(court_name)s, %(photo_index)s, %(image_path_or_url)s)
        ON CONFLICT (auction_no, photo_index) DO NOTHING;
        """

        for photo_data in photo_data_list:
            try:
                image_path = photo_data.get('path')
                photo_idx = photo_data.get('index')

                if image_path is None or photo_idx is None:
                    print(f"오류: PhotoURL 데이터에 path 또는 index 누락. 항목 건너뜀: auction_no={auction_no}, data={photo_data}")
                    failure_count += 1
                    continue

                params = {
                    'auction_no': clean_string(auction_no),
                    'court_name': clean_string(court_name),
                    'photo_index': photo_idx,
                    'image_path_or_url': clean_string(image_path)
                }

                if not params['auction_no'] or not params['image_path_or_url'] or not params['court_name']:
                    print(f"오류: PhotoURL 필수 값 누락. 항목 건너뜀: {params}")
                    failure_count += 1
                    continue
                
                cur.execute(sql, params)
                if cur.rowcount > 0:
                    success_count += 1
            except Exception as item_e:
                print(f"PhotoURL 항목 삽입 중 오류 (auction_no: {auction_no}, data: {photo_data}): {item_e}")
                failure_count += 1

        cur.close()
        return failure_count == 0

    except Exception as e:
        db_conn.rollback()
        print(f"insert_photo_urls 중 전체 오류 (auction_no: {auction_no}): {e}")
        return False

def insert_auction_detail_info(db_conn, data: dict):
    if not db_conn:
        if config.DEBUG: print(f"DB 연결 실패: AuctionDetailInfo 삽입 불가 (auction_no: {data.get('auction_no')})")
        return False
    try:
        cur = db_conn.cursor()

        sql = """
        INSERT INTO "AuctionDetailInfo" (
            auction_no, court_name, location_address, sale_time, sale_location, 
            car_vin, other_details, documents, kind, bid_method, 
            case_received_date, auction_start_date, distribution_due_date, 
            claim_amount, engine_type, approval_number, displacement, 
            department_info, dividend_demand_details, dividend_storage_method, 
            appraisal_summary_text, updated_at
        ) VALUES (
            %(auction_no)s, %(court_name)s, %(location_address)s, %(sale_time)s, %(sale_location)s, 
            %(car_vin)s, %(other_details)s, %(documents)s, %(kind)s, %(bid_method)s, 
            %(case_received_date)s, %(auction_start_date)s, %(distribution_due_date)s, 
            %(claim_amount)s, %(engine_type)s, %(approval_number)s, %(displacement)s, 
            %(department_info)s, %(dividend_demand_details)s, %(dividend_storage_method)s, 
            %(appraisal_summary_text)s, %(updated_at)s
        )
        ON CONFLICT (auction_no) DO UPDATE SET
            court_name = EXCLUDED.court_name,
            location_address = EXCLUDED.location_address,
            sale_time = EXCLUDED.sale_time,
            sale_location = EXCLUDED.sale_location,
            car_vin = EXCLUDED.car_vin,
            other_details = EXCLUDED.other_details,
            documents = EXCLUDED.documents,
            kind = EXCLUDED.kind,
            bid_method = EXCLUDED.bid_method,
            case_received_date = EXCLUDED.case_received_date,
            auction_start_date = EXCLUDED.auction_start_date,
            distribution_due_date = EXCLUDED.distribution_due_date,
            claim_amount = EXCLUDED.claim_amount,
            engine_type = EXCLUDED.engine_type,
            approval_number = EXCLUDED.approval_number,
            displacement = EXCLUDED.displacement,
            department_info = EXCLUDED.department_info,
            dividend_demand_details = EXCLUDED.dividend_demand_details,
            dividend_storage_method = EXCLUDED.dividend_storage_method,
            appraisal_summary_text = EXCLUDED.appraisal_summary_text,
            updated_at = EXCLUDED.updated_at;
        """
        
        # MODIFIED: documents 처리
        documents_val = data.get('documents')
        if isinstance(documents_val, list):
            documents_for_db = json.dumps(documents_val, ensure_ascii=False)
        elif isinstance(documents_val, str):
            documents_for_db = clean_string(documents_val) # 이미 유효한 JSON 문자열이라고 가정
        else:
            documents_for_db = clean_string(documents_val) # None 등의 경우

        params = {
            'auction_no': clean_string(data.get('auction_no')),
            'court_name': clean_string(data.get('court_name')),
            'location_address': clean_string(data.get('location_address')),
            'sale_time': clean_string(data.get('sale_time')),
            'sale_location': clean_string(data.get('sale_location')),
            'car_vin': clean_string(data.get('car_vin')),
            'other_details': clean_string(data.get('other_details')),
            'documents': documents_for_db, # MODIFIED
            'kind': clean_string(data.get('kind')),
            'bid_method': clean_string(data.get('bid_method')),
            'case_received_date': parse_custom_date(data.get('case_received_date')),
            'auction_start_date': parse_custom_date(data.get('auction_start_date')),
            'distribution_due_date': parse_custom_date(data.get('distribution_due_date')),
            'claim_amount': to_int_or_none(data.get('claim_amount'), field_name_for_logging='claim_amount_detail'),
            'engine_type': clean_string(data.get('engine_type')),
            'approval_number': clean_string(data.get('approval_number')),
            'displacement': to_int_or_none(data.get('displacement'), field_name_for_logging='displacement_detail'),
            'department_info': clean_string(data.get('department_info')),
            'dividend_demand_details': clean_string(data.get('dividend_demand_details')),
            'dividend_storage_method': clean_string(data.get('dividend_storage_method')),
            'appraisal_summary_text': clean_string(data.get('appraisal_summary_text')),
            'updated_at': datetime.datetime.now() # 현재 시간으로 updated_at 설정
        }

        if config.DEBUG: # 파라미터 전체 로깅 추가
            log_params_detail = {k: str(v) if isinstance(v, (datetime.datetime, datetime.date)) else v for k, v in params.items()}
            print(f"{time.strftime('%H:%M:%S')} - DEBUG_DB_PARAMS (AuctionDetailInfo for {params.get('auction_no')}): {log_params_detail}")

        if not params['auction_no']:
            print(f"오류: auction_no가 없어 AuctionDetailInfo 삽입/업데이트 불가: {data.get('auction_no')}")
            return False

        cur.execute(sql, params)
        cur.close()
        return True
    except Exception as e:
        db_conn.rollback()
        print(f"AuctionDetailInfo 삽입/업데이트 중 오류: {e} (데이터: {data.get('auction_no')})")
        import traceback
        traceback.print_exc()
        return False

def insert_similar_sale(db_conn, data: dict):
    if not db_conn:
        if config.DEBUG: print(f"DB 연결 실패: SimilarSale 삽입 불가 (auction_no: {data.get('auction_no')})")
        return False
    try:
        cur = db_conn.cursor()

        # Helper function for parsing percentage string (e.g., "69%" -> 0.69)
        def parse_percentage_to_float(value_str):
            if isinstance(value_str, (float, int)):
                return float(value_str)
            if isinstance(value_str, str):
                cleaned_val = value_str.replace('%', '').strip()
                if not cleaned_val:
                    return None
                try:
                    return float(cleaned_val) / 100.0
                except ValueError:
                    return None
            return None

        # Helper function for parsing count string (e.g., "1.7회" -> 1.7, "41건" -> 41)
        def parse_count_string_to_float_or_int(value_str):
            if isinstance(value_str, (float, int)):
                return value_str # Already a number
            if isinstance(value_str, str):
                cleaned_val = value_str.replace('회', '').replace('건', '').strip()
                if not cleaned_val:
                    return None
                try:
                    if '.' in cleaned_val:
                        return float(cleaned_val)
                    else:
                        return int(cleaned_val)
                except ValueError:
                    return None
            return None        

        sql = """
        INSERT INTO "SimilarSale" (
            auction_no, court_name, period, sale_count, 
            avg_appraisal_price, avg_sale_price, sale_to_appraisal_ratio, 
            avg_unsold_count, updated_at
        ) VALUES (
            %(auction_no)s, %(court_name)s, %(period)s, %(sale_count)s, 
            %(avg_appraisal_price)s, %(avg_sale_price)s, %(sale_to_appraisal_ratio)s, 
            %(avg_unsold_count)s, %(updated_at)s
        )
        ON CONFLICT (auction_no, period) DO UPDATE SET
            court_name = EXCLUDED.court_name,
            sale_count = EXCLUDED.sale_count,
            avg_appraisal_price = EXCLUDED.avg_appraisal_price,
            avg_sale_price = EXCLUDED.avg_sale_price,
            sale_to_appraisal_ratio = EXCLUDED.sale_to_appraisal_ratio,
            avg_unsold_count = EXCLUDED.avg_unsold_count,
            updated_at = EXCLUDED.updated_at;
        """
        
        params = {
            'auction_no': clean_string(data.get('auction_no')),
            'court_name': clean_string(data.get('court_name')),
            'period': clean_string(data.get('기간')), 
            'sale_count': parse_count_string_to_float_or_int(data.get('매각건수')), 
            'avg_appraisal_price': to_int_or_none(data.get('평균감정가'), field_name_for_logging='avg_appraisal_price_similar'), 
            'avg_sale_price': to_int_or_none(data.get('평균매각가'), field_name_for_logging='avg_sale_price_similar'), 
            'sale_to_appraisal_ratio': parse_percentage_to_float(data.get('매각가율')), # CSV에 매각가율이 두번 있는데, 어떤걸 쓸지 확인 필요. Prisma에는 sale_to_appraisal_ratio 하나임.
            'avg_unsold_count': parse_count_string_to_float_or_int(data.get('평균유찰횟수')),
            'updated_at': datetime.datetime.now() # 현재 시간으로 updated_at 설정
        }

        # CSV 컬럼명과 data.get()의 키값이 일치해야 함.
        # 예: data.get('기간') 대신 data.get('period') 사용 (Prisma 모델 필드명 기준 or CSV 파싱 시 키 변경)
        # 여기서는 Prisma 모델 필드명과 유사하게 data 딕셔너리 키가 설정되었다고 가정.
        # 실제 CSV 파싱 로직에서 키를 어떻게 만드는지 확인 필요.
        # similar_sales.csv 헤더: auction_no,court_name,구분,감정가,최저가,최저가율,매각가,매각가율,차량명,기간,매각건수,평균감정가,평균매각가,평균유찰횟수
        # data.get 안의 키는 이 CSV 헤더를 따라야 함. (예: data.get('기간'), data.get('매각건수') 등)
        # 아래는 CSV 헤더에 맞춘 수정 예시 (단, court_name, auction_no는 이미 있다고 가정)
        params_adjusted_for_csv_header = {
            'auction_no': clean_string(data.get('auction_no')),
            'court_name': clean_string(data.get('court_name')),
            'period': clean_string(data.get('기간')), 
            'sale_count': parse_count_string_to_float_or_int(data.get('매각건수')), 
            'avg_appraisal_price': to_int_or_none(data.get('평균감정가'), field_name_for_logging='avg_appraisal_price_similar'), 
            'avg_sale_price': to_int_or_none(data.get('평균매각가'), field_name_for_logging='avg_sale_price_similar'), 
            'sale_to_appraisal_ratio': parse_percentage_to_float(data.get('매각가율')), # CSV에 매각가율이 두번 있는데, 어떤걸 쓸지 확인 필요. Prisma에는 sale_to_appraisal_ratio 하나임.
            'avg_unsold_count': parse_count_string_to_float_or_int(data.get('평균유찰횟수')),
            'updated_at': datetime.datetime.now() # 현재 시간으로 updated_at 설정
        }

        # 여기서는 params_adjusted_for_csv_header를 사용합니다.
        final_params = params_adjusted_for_csv_header

        if config.DEBUG: # 파라미터 전체 로깅 추가
            log_params_similar = {k: str(v) if isinstance(v, (datetime.datetime, datetime.date)) else v for k, v in final_params.items()}
            print(f"{time.strftime('%H:%M:%S')} - DEBUG_DB_PARAMS (SimilarSale for {final_params.get('auction_no')}, period {final_params.get('period')}): {log_params_similar}")

        if not final_params['auction_no'] or not final_params['period']:
            print(f"오류: auction_no 또는 period가 없어 SimilarSale 삽입/업데이트 불가: {data.get('auction_no')}")
            return False

        cur.execute(sql, final_params)
        cur.close()
        return True
    except Exception as e:
        db_conn.rollback()
        print(f"SimilarSale 삽입/업데이트 중 오류: {e} (데이터: {data.get('auction_no')}, 기간: {data.get('기간')})")
        import traceback
        traceback.print_exc()
        return False

def insert_or_update_appraisal_summary(db_conn, auction_no_pk: str, summary_data: dict):
    if not auction_no_pk:
        if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - 오류: auction_no_pk가 없어 AppraisalSummary 삽입/업데이트 불가.")
        return False

    if not db_conn:
        if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - DB 연결 실패: AppraisalSummary 삽입/업데이트 불가 (auction_no: {auction_no_pk})")
        return False

    cur = None
    try:
        cleaned_summary_data = {}
        if isinstance(summary_data, dict):
            for key, value in summary_data.items():
                if isinstance(value, str):
                    stripped_value = value.strip()
                    if stripped_value.lower() == 'none' or stripped_value == '정보 없음' or not stripped_value:
                        cleaned_summary_data[key] = None
                    else:
                        cleaned_summary_data[key] = stripped_value
                else:
                    cleaned_summary_data[key] = value
        else:
            if config.DEBUG:
                print(f"{time.strftime('%H:%M:%S')} - AppraisalSummary: summary_data가 dict 타입이 아닙니다 ({auction_no_pk}). 빈 데이터로 처리합니다.")
        
        if not cleaned_summary_data or all(value is None for value in cleaned_summary_data.values()):
            if config.DEBUG:
                print(f"{time.strftime('%H:%M:%S')} - AppraisalSummary: 모든 정제된 요약 데이터가 None이거나 입력 데이터가 없습니다 ({auction_no_pk}). DB 작업 건너뜀.")
            return True

        cur = db_conn.cursor()

        sql = """
        INSERT INTO "AuctionAppraisalSummary" (
            auction_no, summary_year_mileage, summary_color, summary_management_status,
            summary_fuel, summary_inspection_validity, summary_options_etc,
            created_at, updated_at
        ) VALUES (
            %(auction_no)s, %(summary_year_mileage)s, %(summary_color)s, %(summary_management_status)s,
            %(summary_fuel)s, %(summary_inspection_validity)s, %(summary_options_etc)s,
            %(current_time)s, %(current_time)s
        )
        ON CONFLICT (auction_no) DO UPDATE SET
            summary_year_mileage = EXCLUDED.summary_year_mileage,
            summary_color = EXCLUDED.summary_color,
            summary_management_status = EXCLUDED.summary_management_status,
            summary_fuel = EXCLUDED.summary_fuel,
            summary_inspection_validity = EXCLUDED.summary_inspection_validity,
            summary_options_etc = EXCLUDED.summary_options_etc,
            updated_at = EXCLUDED.updated_at;
        """
        
        current_time = datetime.datetime.now()
        params = {
            'auction_no': auction_no_pk,
            'summary_year_mileage': cleaned_summary_data.get('summary_year_mileage'),
            'summary_color': cleaned_summary_data.get('summary_color'),
            'summary_management_status': cleaned_summary_data.get('summary_management_status'),
            'summary_fuel': cleaned_summary_data.get('summary_fuel'),
            'summary_inspection_validity': cleaned_summary_data.get('summary_inspection_validity'),
            'summary_options_etc': cleaned_summary_data.get('summary_options_etc'),
            'current_time': current_time
        }

        if config.DEBUG:
            log_params_summary = {k: str(v) if isinstance(v, (datetime.datetime, datetime.date)) else v for k, v in params.items()}
            # print(f"{time.strftime('%H:%M:%S')} - DEBUG_DB_PARAMS (AppraisalSummary for {params.get('auction_no')}): {log_params_summary}")

        cur.execute(sql, params)
        return True
    except psycopg2.Error as db_err:
        if db_conn: db_conn.rollback()
        print(f"{time.strftime('%H:%M:%S')} - AppraisalSummary 삽입/업데이트 중 DB 오류 ({auction_no_pk}): {db_err}")
        return False
    except Exception as e:
        if db_conn: db_conn.rollback()
        print(f"{time.strftime('%H:%M:%S')} - AppraisalSummary 삽입/업데이트 중 일반 오류 ({auction_no_pk}): {e}")
        return False
    finally:
        if cur:
            cur.close()

def test_db_connection():
    """데이터베이스 연결을 테스트합니다."""
    conn_context = get_db_connection() # 컨텍스트 매니저 사용
    try:
        with conn_context as conn: # with 문으로 conn 가져오기
            if conn:
                print("데이터베이스 연결 성공!")
                cur = conn.cursor()
                cur.execute("SELECT version();")
                db_version = cur.fetchone()
                print(f"PostgreSQL 버전: {db_version}")
                cur.close()
            else:
                print("데이터베이스 연결 실패.") # get_db_connection이 예외 발생시키므로 이 분기는 거의 안 탐
    except Exception as e:
        print(f"데이터베이스 연결 테스트 중 오류 발생: {e}")
    # finally 블록은 get_db_connection 컨텍스트 매니저가 처리

def get_auction_base_by_auction_no(db_conn, auction_no: str) -> dict | None:
    """
    주어진 auction_no로 AuctionBaseInfo 테이블에서 경매 기본 정보를 조회합니다.
    조회 성공 시 해당 레코드를 딕셔너리로 반환하고, 없으면 None을 반환합니다.
    Prisma 스키마상 auction_no는 @id 이므로 고유하다고 가정합니다.
    """
    if not db_conn:
        if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - DB connection not available for get_auction_base_by_auction_no.")
        return None
    
    query = '''
    SELECT auction_no, case_year, case_number, item_no, court_name, 
           appraisal_price, min_bid_price, min_bid_price_2, sale_date, status, car_name,
           car_model_year, car_reg_number, car_mileage, car_fuel,
           car_transmission, car_type, manufacturer, created_at, updated_at, representative_photo_index
    FROM "AuctionBaseInfo" 
    WHERE auction_no = %s;
    '''
    # updated_at, created_at도 SELECT에 추가 (필요시)
    
    try:
        with db_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            cursor.execute(query, (auction_no,))
            result = cursor.fetchone()
            # 타입 변환 로깅은 insert 시점에 하는 것이 더 적절할 수 있음
            # if result:
            #     if config.DEBUG and result.get('sale_date') and not isinstance(result['sale_date'], datetime.datetime) \
            #        and not isinstance(result['sale_date'], datetime.date) : # date 타입도 허용
            #         print(f"{time.strftime('%H:%M:%S')} - 경고: DB에서 가져온 sale_date 타입이 datetime이 아닙니다 (타입: {type(result['sale_date'])}, 값: {result['sale_date']})")
            return result
    except Exception as e:
        print(f"{time.strftime('%H:%M:%S')} - Error in get_auction_base_by_auction_no for {auction_no}: {e}")
        # db_conn.rollback() # SELECT 작업이므로 롤백 불필요
    return None

def delete_rows_by_auction_no(db_conn, table_name: str, auction_no: str) -> bool:
    """주어진 auction_no에 해당하는 모든 행을 특정 테이블에서 삭제합니다."""
    if not db_conn:
        if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - DB 연결 없어 {table_name} 삭제 불가 ({auction_no}) ")
        return False
    
    allowed_tables = ["PhotoURL", "DateHistory", "SimilarSale", "AuctionDetailInfo", "AuctionAppraisalSummary"] 
    if table_name not in allowed_tables:
        print(f"오류: 허용되지 않은 테이블 이름입니다: {table_name}")
        return False

    sql = f'DELETE FROM "{table_name}" WHERE auction_no = %s;' 
    
    try:
        with db_conn.cursor() as cur: 
            cur.execute(sql, (auction_no,))
            if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - {table_name}에서 auction_no {auction_no} 관련 행들 삭제 시도 (영향 받은 행: {cur.rowcount}).")
            return True
    except Exception as e:
        print(f"{table_name}에서 auction_no {auction_no} 관련 행 삭제 중 오류: {e}")
        # import traceback; traceback.print_exc() # 필요시 주석 해제
        return False

# NEW FUNCTION
def delete_auction_base_info_by_auction_no(db_conn, auction_no: str) -> bool:
    """주어진 auction_no에 해당하는 행을 AuctionBaseInfo 테이블에서 삭제합니다.
    ON DELETE CASCADE 제약 조건에 의해 관련된 다른 테이블의 행들도 삭제됩니다.
    """
    if not db_conn:
        if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - DB 연결 없어 AuctionBaseInfo 삭제 불가 ({auction_no}) ")
        return False
    
    sql = 'DELETE FROM "AuctionBaseInfo" WHERE auction_no = %s;'
    
    try:
        with db_conn.cursor() as cur:
            cur.execute(sql, (auction_no,))
            if config.DEBUG: print(f"{time.strftime('%H:%M:%S')} - AuctionBaseInfo에서 auction_no {auction_no} 관련 행 삭제 시도 (영향 받은 행: {cur.rowcount}). CASCADE 규칙에 따라 다른 테이블도 영향받을 수 있음.")
            return True # 삭제 성공 여부와 관계없이 True를 반환 (rowcount로 실제 삭제 확인 가능)
    except Exception as e:
        print(f"AuctionBaseInfo에서 auction_no {auction_no} 관련 행 삭제 중 오류: {e}")
        # import traceback; traceback.print_exc() # 필요시 주석 해제
        return False

# NEW FUNCTION to check if photos exist for a given auction_no
def check_photos_exist(db_conn, auction_no: str) -> bool:
    """
    Checks if photos exist in the PhotoURL table for a given auction_no.

    Args:
        db_conn: Active database connection.
        auction_no: The auction number (auction_no) to check for.

    Returns:
        True if photos exist, False otherwise.
    """
    if not db_conn:
        if config.DEBUG: 
            print(f"{time.strftime('%H:%M:%S')} - DB connection not available for check_photos_exist (auction_no: {auction_no}). Returning False, assuming photos don't exist or cannot be checked.")
        return False # 연결 없으면 False 반환 (사진 없다고 가정 또는 확인 불가)

    query = 'SELECT 1 FROM "PhotoURL" WHERE auction_no = %s LIMIT 1;'
    
    try:
        with db_conn.cursor() as cursor:
            cursor.execute(query, (auction_no,))
            exists = cursor.fetchone() is not None
            if config.DEBUG:
                print(f"{time.strftime('%H:%M:%S')} - check_photos_exist for {auction_no}: {'Exists' if exists else 'Does not exist'}")
            return exists
    except Exception as e:
        print(f"{time.strftime('%H:%M:%S')} - Error in check_photos_exist for {auction_no}: {e}")
        # 오류 발생 시, 사진이 없다고 가정하거나 또는 호출 측에서 오류를 인지하도록 False 반환
        # 또는 특정 예외는 re-raise 할 수도 있음
        return False

if __name__ == "__main__":
    test_db_connection()