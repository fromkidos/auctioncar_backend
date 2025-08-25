#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Parsing functions for Court Auction website HTML content.
"""
import re
from bs4 import BeautifulSoup, Tag
from . import config # 수정: 상대 경로로 변경
import time
from typing import List, Dict, Optional # 필요한 경우 추가
import os
import datetime # 유지 (날짜 관련 유틸리티에 필요할 수 있음)
import json # 유지 (config 등에서 간접적으로 필요할 수 있음)

# NEW HELPER FUNCTION
def text_or_none(value: Optional[str]) -> Optional[str]:
    """Converts an empty string or a string literal 'None' to None, otherwise returns the string."""
    if value == "" or value == 'None': # 'None' 문자열도 None으로 처리
        return None
    return value

def safe_get_text(element: Tag | None, default: Optional[str] = None) -> Optional[str]:
    """Safely extracts stripped text from a BeautifulSoup Tag object."""
    if element:
        # 빈 문자열도 그대로 반환 (text_or_none에서 후처리)
        return element.get_text(strip=True)
    return default

def parse_ongoing_list(html: str) -> list[dict]:
    """
    Parse the ongoing auction listing grid (자동차·중기검색 results).
    Extracts key information including the unique ID.
    """
    soup = BeautifulSoup(html, 'html.parser')
    grid_body = soup.select_one(f'tbody#{config.RESULTS_GRID_BODY_ID}')
    if not grid_body:
        # print(f"Ongoing results grid body ({config.RESULTS_GRID_BODY_ID}) not found in HTML. Verify ID.")
        return []

    start_rows = grid_body.find_all('tr', attrs={'data-tr-id': 'row2'}, recursive=False)
    results = []
    # print(f"Found {len(start_rows)} potential item starting rows in ongoing list.")

    for index, row1 in enumerate(start_rows):
        tr_index_attr = row1.get('data-trindex')
        if tr_index_attr is None:
            # print(f"Warning: Could not find data-trindex for row at enumerate index {index}. Skipping.")
            continue

        row2 = row1.find_next_sibling('tr', attrs={'data-tr-id': 'row4'})
        if not row2:
            # print(f"Could not find matching second row (row4) for starting row index {tr_index_attr}. Skipping.")
            continue

        cols1 = row1.find_all('td', recursive=False)
        cols2 = row2.find_all('td', recursive=False)

        if len(cols1) < 8 or len(cols2) < 3:
             # print(f"Unexpected number of columns found (Row1: {len(cols1)}, Row2: {len(cols2)}). Skipping row index {tr_index_attr}.")
             continue

        try:
            court_raw = cols1[1].find('nobr').contents[0].strip() if cols1[1].find('nobr') and cols1[1].find('nobr').contents else None
            court = text_or_none(court_raw)
            
            case_no_text_raw = cols1[1].find('nobr').contents[2].strip() if cols1[1].find('nobr') and len(cols1[1].find('nobr').contents) > 2 else None
            case_no_text = text_or_none(case_no_text_raw)

            item_no_text_raw = cols1[2].get_text(strip=True)
            item_no_text = text_or_none(item_no_text_raw)
            
            auction_no = f"{case_no_text}-{item_no_text}" if case_no_text and item_no_text else None

            location_text_raw = None
            title_text_raw = None # title_text는 현재 사용되지 않음
            loc_div = cols1[3].find('div')
            if loc_div:
                loc_link = loc_div.find('a')
                if loc_link:
                    location_text_raw = loc_link.get_text(strip=True).replace('사용본거지 :', '').strip()
            location_text = text_or_none(location_text_raw)
            
            # remarks_text = text_or_none(cols1[5].get_text(strip=True)) # 사용 안함
            appraisal_text_raw = cols1[6].get_text(strip=True).replace(',', '').replace('원', '')
            appraisal_text = text_or_none(appraisal_text_raw)
            
            min_bid_price_text_raw = cols2[1].get_text(strip=True).replace(',', '').replace('원', '')
            min_bid_price_text = text_or_none(min_bid_price_text_raw)

            sale_date_text_raw = None
            dept_td = cols1[7] # 매각기일/담당계가 있는 <td>
            if dept_td:
                nobr_tag = dept_td.find('nobr', class_='w2grid_input_readonly')
                if nobr_tag:
                    div_tag = nobr_tag.find('div')
                    if div_tag:
                        # div 태그의 contents를 뒤에서부터 확인하여 날짜 형식의 텍스트를 찾음
                        for content_node in reversed(div_tag.contents):
                            if isinstance(content_node, str): # NavigableString도 str로 체크 가능
                                stripped_content = content_node.strip()
                                # YYYY.MM.DD 형식인지 정규식으로 확인
                                if re.fullmatch(r'\d{4}\.\d{2}\.\d{2}', stripped_content):
                                    sale_date_text_raw = stripped_content
                                    break # 날짜를 찾으면 루프 종료
                        
                        # 디버깅용: 만약 위에서 못 찾았다면, 전체 텍스트에서라도 찾아보기
                        if not sale_date_text_raw:
                            full_text_in_div = div_tag.get_text(separator=' ', strip=True)
                            date_match = re.search(r'(\d{4}\.\d{2}\.\d{2})', full_text_in_div)
                            if date_match:
                                sale_date_text_raw = date_match.group(1)
                                # logger.debug(f"Sale date found using fallback regex on full div text: {sale_date_text_raw}") 
                            # else:
                                # logger.debug(f"Sale date not found even with fallback regex on full div text: {full_text_in_div}")
            
            sale_date_text = text_or_none(sale_date_text_raw)
            # print(f"DEBUG PARSER: auction_no={auction_no}, raw_sale_date='{sale_date_text_raw}', parsed_sale_date='{sale_date_text}'")

            status_text_raw = cols2[2].get_text(strip=True)
            status_text = text_or_none(status_text_raw)

            if not auction_no:
                # print(f"Warning: Missing auction_no ({auction_no}) for row index {tr_index_attr}. Skipping.")
                continue

            # Split case_no_text into year and number
            case_year_raw = None
            case_num_part_raw = None
            if case_no_text and '타경' in case_no_text:
                parts = case_no_text.split('타경', 1)
                if len(parts) == 2:
                    case_year_raw = parts[0]
                    case_num_part_raw = parts[1]
            
            case_year = text_or_none(case_year_raw)
            case_num_part = text_or_none(case_num_part_raw)
            
            results.append({
                'auction_no': auction_no,
                'court_name': court,
                'display_case_no': case_no_text,
                'case_year': case_year,
                'case_number': case_num_part,
                'item_no': item_no_text,
                'location_address': location_text,
                'appraisal_price': appraisal_text,
                'min_bid_price': min_bid_price_text,
                'sale_date': sale_date_text,
                'status': status_text,
            })
        except Exception as e_item_parse:
            # print(f"Error parsing item at tr_index {tr_index_attr}: {e_item_parse}")
            # import traceback
            # traceback.print_exc()
            continue # 오류 발생 시 해당 아이템 건너뛰고 계속 진행

    return results

def parse_detail_page(html_content: str, case_no: str, item_no: str, pre_collected_photo_urls: list | None = None) -> dict:
    """Parses the HTML content of a detail page to extract auction item details using text labels.

    Args:
        html_content: The HTML source of the detail page.
        case_no: The case number.
        item_no: The item number.
        pre_collected_photo_urls: Optional list of photo URLs collected beforehand.
    """
    # print("Parsing detail page HTML using text labels...")
    soup = BeautifulSoup(html_content, 'html.parser')
    details = {'case_no': case_no, 'item_no': item_no}
    details_kv = {}
    docs = []
    date_history = []
    similar_sales_stats = {}

    # Parse storage location from specific span
    storage_location_span = soup.find('span', id='mf_wfm_mainFrame_gen_carGdsDts_0_spn_carStorgPlc')
    if storage_location_span:
        storage_location_text = text_or_none(safe_get_text(storage_location_span))
        if storage_location_text:
            details['location_address'] = storage_location_text
            details_kv['location_address'] = storage_location_text

    # Helper function nested inside to access soup directly
    def find_data_by_label(label_text: str, scope: Tag | None = None) -> Optional[str]:
        """Finds the sibling td/span text for a given th/label text within the scope."""
        if scope is None:
            scope = soup

        label_th = scope.find('th', string=lambda t: t and re.match(label_text, t.strip()))
        if label_th and label_th.find_next_sibling('td'):
            value_td = label_th.find_next_sibling('td')
            value_span = value_td.find('span')
            if value_span:
                 if label_text == config.LABEL_DEPARTMENT:
                     dept_span = value_span.find('span', id=lambda x: x and 'cortAuctnJdbnNm' in x)
                     if dept_span: return text_or_none(safe_get_text(dept_span))
                 if label_text == config.LABEL_ITEM_REMARKS:
                      rmk_div = value_span.find('div')
                      if rmk_div: return text_or_none(safe_get_text(rmk_div))
                 return text_or_none(safe_get_text(value_span))
            return text_or_none(safe_get_text(value_td))

        label_element = scope.find(lambda tag: tag.name in ['label', 'div', 'span', 'th'] and re.match(label_text, tag.get_text(strip=True)))
        if label_element:
            parent_row = label_element.find_parent('tr')
            if parent_row:
                value_td = parent_row.find('td')
                if value_td:
                    value_span = value_td.find('span')
                    if value_span: return text_or_none(safe_get_text(value_span))
                    return text_or_none(safe_get_text(value_td))
            next_sibling_span = label_element.find_next_sibling(['span', 'div'])
            if next_sibling_span: return text_or_none(safe_get_text(next_sibling_span))

        return None

    # --- Basic Info Extraction ---
    # print("  Extracting basic info...")
    basic_info_container = soup.find('h3', string=lambda t: t and config.HEADER_BASIC_INFO in t.strip())
    basic_scope = basic_info_container.find_parent() if basic_info_container else soup

    parsed_value_kind = find_data_by_label(config.LABEL_KIND, basic_scope)
    if parsed_value_kind is not None:
        details_kv[config.LABEL_KIND] = parsed_value_kind
    details['kind'] = parsed_value_kind

    parsed_value_bid_method = find_data_by_label(config.LABEL_BID_METHOD, basic_scope)
    if parsed_value_bid_method is not None:
        details_kv[config.LABEL_BID_METHOD] = parsed_value_bid_method
    details['bid_method'] = parsed_value_bid_method
    
    details['sale_date'] = None
    details['sale_time'] = None
    details['sale_location'] = None
    
    sale_date_time_loc_span = soup.find('span', id='mf_wfm_mainFrame_spn_gdsDtlSrchDspslDxdy')
    if sale_date_time_loc_span:
        full_text_raw = safe_get_text(sale_date_time_loc_span)
        full_text = text_or_none(full_text_raw)
        if full_text:
            match = re.match(r'(\d{4}[.-]\d{2}[.-]\d{2})\s*(\d{2}:\d{2})?\s*(.*)', full_text)
            if match:
                date_part = text_or_none(match.group(1).strip() if match.group(1) else None)
                time_part = text_or_none(match.group(2).strip() if match.group(2) else None)
                location_part = text_or_none(match.group(3).strip() if match.group(3) else None)
                
                details['sale_date'] = date_part
                if time_part:
                    details['sale_date'] = f"{date_part} {time_part}" if date_part else time_part
                    details['sale_time'] = time_part
                details['sale_location'] = location_part
            else:
                parts = full_text.split(None, 2)
                if len(parts) >= 1:
                    if re.match(r'^\d{4}[.-]\d{2}[.-]\d{2}.*$', parts[0]):
                        details['sale_date'] = parts[0].rstrip('.')
                        if len(parts) >= 2 and re.match(r'^\d{2}:\d{2}$', parts[1]):
                            details['sale_date'] = f"{details['sale_date']} {parts[1]}"
                            details['sale_time'] = parts[1]
                            if len(parts) >= 3: details['sale_location'] = parts[2]
                        elif len(parts) >= 2:
                            details['sale_location'] = ' '.join(parts[1:])
                        else:
                            details['sale_time'] = None
                            details['sale_location'] = None
                    else: 
                        details['sale_location'] = full_text
                        details['sale_date'] = None
                        details['sale_time'] = None
    else:
        sale_date_text_full_detail_fallback = find_data_by_label(config.LABEL_SALE_DATE_TIME_LOC, basic_scope)
        if sale_date_text_full_detail_fallback is not None:
            details_kv[config.LABEL_SALE_DATE_TIME_LOC] = sale_date_text_full_detail_fallback
            parts = sale_date_text_full_detail_fallback.split()
            if len(parts) >= 1 and re.match(r'^\d{4}[.-]\d{2}[.-]\d{2}.*$', parts[0]):
                details['sale_date'] = parts[0].rstrip('.')
                if len(parts) >= 2 and re.match(r'^\d{2}:\d{2}$', parts[1]):
                    details['sale_date'] = f"{details['sale_date']} {parts[1]}"
                    details['sale_time'] = parts[1]
                    if len(parts) >= 3: details['sale_location'] = ' '.join(parts[2:])
                elif len(parts) >= 2:
                    details['sale_location'] = ' '.join(parts[1:])
                else:
                    details['sale_time'] = None
                    details['sale_location'] = None
            elif len(parts) >= 1:
                details['sale_location'] = sale_date_text_full_detail_fallback
                details['sale_date'] = None
                details['sale_time'] = None

    parsed_value_other_details = find_data_by_label(config.LABEL_ITEM_REMARKS, basic_scope)
    if parsed_value_other_details is not None:
        details_kv[config.LABEL_ITEM_REMARKS] = parsed_value_other_details
    details['other_details'] = parsed_value_other_details

    # --- Case Info Extraction ---
    # print("  Extracting case info...")
    case_info_container = soup.find('h3', string=lambda t: t and config.HEADER_CASE_INFO in t.strip())
    case_scope = case_info_container.find_parent() if case_info_container else soup

    parsed_value_case_received = find_data_by_label(config.LABEL_CASE_RECEIVED, case_scope)
    if parsed_value_case_received is not None:
        details_kv[config.LABEL_CASE_RECEIVED] = parsed_value_case_received
    details['case_received_date'] = parsed_value_case_received

    parsed_value_auction_start = find_data_by_label(config.LABEL_AUCTION_START_DATE, case_scope)
    if parsed_value_auction_start is not None:
        details_kv[config.LABEL_AUCTION_START_DATE] = parsed_value_auction_start
    details['auction_start_date'] = parsed_value_auction_start

    parsed_value_dist_due = find_data_by_label(config.LABEL_DISTRIBUTION_DUE_DATE, case_scope)
    if parsed_value_dist_due is not None:
        details_kv[config.LABEL_DISTRIBUTION_DUE_DATE] = parsed_value_dist_due
    details['distribution_due_date'] = parsed_value_dist_due

    raw_claim_amount = find_data_by_label(config.LABEL_CLAIM_AMOUNT, case_scope)
    if raw_claim_amount is not None:
        details_kv[config.LABEL_CLAIM_AMOUNT] = raw_claim_amount
        details['claim_amount'] = text_or_none(raw_claim_amount.replace(',', '').replace('원', ''))
    else:
        details['claim_amount'] = None

    # --- Photo Extraction ---
    # print("  Extracting photos...")
    if pre_collected_photo_urls is not None:
        # print(f"    Using {len(pre_collected_photo_urls)} pre-collected photo URLs.")
        details['photo_urls'] = pre_collected_photo_urls
        total_photo_count = 0
        try:
            photo_count_element = soup.select_one(config.PHOTO_COUNT_ID_SELECTOR)
            if not photo_count_element:
                 photo_count_element = soup.find(lambda tag: config.PHOTO_COUNT_FALLBACK_TEXT in tag.get_text(strip=True) and re.search(r'\((\d+)\)', tag.get_text(strip=True)))
            if photo_count_element:
                 count_text = photo_count_element.get_text(strip=True)
                 match = re.search(r'\((\d+)\)', count_text)
                 if match: 
                     total_photo_count = int(match.group(1))
                 else:
                     pass
        except Exception: pass
    else:
        # print("    No pre-collected URLs provided. Parsing photos from current HTML...")
        total_photo_count = 0 
        try:
            photo_count_element = soup.select_one(config.PHOTO_COUNT_ID_SELECTOR)
            if not photo_count_element:
                 # print("    Warning: Could not find photo count element by specific ID. Using general search...")
                 photo_count_element = soup.find(lambda tag: config.PHOTO_COUNT_FALLBACK_TEXT in tag.get_text(strip=True) and re.search(r'\((\d+)\)', tag.get_text(strip=True)))
            
            if photo_count_element: 
                 count_text = photo_count_element.get_text(strip=True)
                 match = re.search(r'\((\d+)\)', count_text)
                 if match: 
                     total_photo_count = int(match.group(1))
                 else: 
                     pass 
            else: 
                 # print("    Warning: Could not find element containing photo count text.")
                 pass 
        except Exception as e: 
             # print(f"    Warning: Error extracting total photo count: {e}")
             pass 
    details['total_photo_count'] = total_photo_count

    photo_urls = []
    all_img_tags = soup.find_all('img', id=lambda x: x and 'img_reltPic' in x)
    processed_urls = set()
    for img_tag in all_img_tags:
         if img_tag and 'src' in img_tag.attrs:
             src_raw = img_tag['src']
             src = text_or_none(src_raw)
             if src and src != '#':
                 full_url = src
                 if full_url not in processed_urls:
                     photo_urls.append(full_url)
                     processed_urls.add(full_url)
    details['photo_urls'] = photo_urls

    # --- Document Links Extraction ---
    # print("  Extracting document links...")
    doc_links = soup.select(config.DETAIL_DOCS_LIST_SELECTOR)
    docs = extract_document_links(doc_links if doc_links else [])
    details['documents'] = docs

    # --- Date History (기일내역) --- 
    date_history_table_body = soup.select_one(config.DETAIL_DATE_HISTORY_TABLE_SELECTOR) 
    date_history = []
    if date_history_table_body:
        rows = date_history_table_body.select("tr[data-tr-id='row2']")
        if not rows:
            rows = date_history_table_body.find_all('tr', recursive=False)
        date_history = extract_date_history(rows)
    details['parsed_auction_date_history'] = date_history

    # --- Similar Sales Statistics (유사물건 매각통계) ---
    similar_stats_content_div = soup.select_one(f"#{config.DETAIL_SIMILAR_STATS_CONTENT_DIV_ID}")
    parsed_similar_sales_data = [] 
    if similar_stats_content_div:
        stats_table = similar_stats_content_div.find('table') 
        if stats_table:
            stats_tbody = stats_table.find('tbody')
            if stats_tbody:
                stats_rows = stats_tbody.find_all('tr', recursive=False)
                if stats_rows:
                    similar_sales_stats_list = extract_similar_stats(stats_rows) 
                    if similar_sales_stats_list:
                        parsed_similar_sales_data = similar_sales_stats_list
                # else:
                    # if config.DEBUG:
                    #     print(f"DEBUG: Similar stats tbody found, but no <tr> children. Tbody HTML: {str(stats_tbody)[:300]}")
            # else:
                # if config.DEBUG:
                #     print(f"DEBUG: Similar stats table found, but no <tbody>. Table HTML: {str(stats_table)[:300]}")
        # else:
            # if config.DEBUG:
            #     print(f"DEBUG: Similar stats content div found, but no <table> inside. Div HTML: {str(similar_stats_content_div)[:300]}")
    details['parsed_similar_sales'] = parsed_similar_sales_data

    # --- Appraisal Summary (감정평가요항표) ---
    appraisal_summary_full_text = ""
    appraisal_title_text = "1. 자동차감정평가요항표"
    title_element = soup.find(lambda tag: tag.name == 'div' and appraisal_title_text in tag.get_text(strip=True) and 'tit' in tag.get('class', []))
    
    appraisal_summary_container = None
    if title_element:
        appraisal_summary_container = title_element.find_parent('div')
    if appraisal_summary_container:       
        main_content_li = appraisal_summary_container.select_one("ul.sum_list > li")
        if main_content_li:
            current_element = main_content_li.find("div", class_="subtit")
            item_texts = [] 
            while current_element:
                label_text_raw = safe_get_text(current_element)
                label_text = text_or_none(label_text_raw)
                
                value_text_raw = "정보 없음" # Placeholder, will be overwritten
                value_ul = current_element.find_next_sibling("ul", class_="depth2")
                if value_ul:
                    value_div = value_ul.select_one("li > div.w2textbox")
                    if value_div:
                        value_text_raw = value_div.get_text(separator="\\n", strip=True)
                
                value_text = text_or_none(value_text_raw)
                if value_text_raw == "정보 없음": value_text = None # Ensure placeholder becomes None

                if label_text is not None and value_text is not None:
                    item_texts.append(f"{label_text}\\n{value_text}")
                elif label_text is not None: # Only label exists
                    item_texts.append(label_text) 
                
                next_subtit_after_ul = value_ul.find_next_sibling("div", class_="subtit") if value_ul else None
                if next_subtit_after_ul:
                    current_element = next_subtit_after_ul
                else: 
                    current_element = current_element.find_next_sibling("div", class_="subtit")
            
            appraisal_summary_full_text = text_or_none("\\n\\n".join(item_texts).strip())
        # else:
            # if config.DEBUG:
            #     print(f"DEBUG: Appraisal Summary main content <li> (ul.sum_list > li) NOT FOUND inside container.")
    
    details['summary_year_mileage'] = text_or_none(safe_get_text(soup.select_one(f"#{config.APPRAISAL_SUMMARY_IDS['year_mileage']}")))
    details['summary_color'] = text_or_none(safe_get_text(soup.select_one(f"#{config.APPRAISAL_SUMMARY_IDS['color']}")))
    details['summary_management_status'] = text_or_none(safe_get_text(soup.select_one(f"#{config.APPRAISAL_SUMMARY_IDS['management_status']}"), default=None))
    details['summary_fuel'] = text_or_none(safe_get_text(soup.select_one(f"#{config.APPRAISAL_SUMMARY_IDS['fuel']}")))
    details['summary_inspection_validity'] = text_or_none(safe_get_text(soup.select_one(f"#{config.APPRAISAL_SUMMARY_IDS['inspection_validity']}")))
    details['summary_options_etc'] = text_or_none(safe_get_text(soup.select_one(f"#{config.APPRAISAL_SUMMARY_IDS['options_etc']}"), default=None))

    # --- Item Details Extraction ---
    # print("  Extracting item details (목록내역)...")
    item_details_container = soup.find('h3', string=lambda t: t and config.HEADER_ITEM_DETAILS in t.strip())
    item_details_scope = item_details_container.find_next('div') if item_details_container else soup
    if item_details_scope:
        parsed_value = find_data_by_label(config.LABEL_CAR_NAME, item_details_scope)
        if parsed_value is not None: details_kv[config.LABEL_CAR_NAME] = parsed_value
        details['car_name'] = parsed_value

        parsed_value = find_data_by_label(config.LABEL_CAR_TYPE, item_details_scope)
        if parsed_value is not None: details_kv[config.LABEL_CAR_TYPE] = parsed_value
        details['car_type'] = parsed_value

        parsed_value = find_data_by_label(config.LABEL_REG_NUMBER, item_details_scope)
        if parsed_value is not None: details_kv[config.LABEL_REG_NUMBER] = parsed_value
        details['car_reg_number'] = parsed_value

        parsed_value = find_data_by_label(config.LABEL_MODEL_YEAR, item_details_scope)
        if parsed_value is not None: details_kv[config.LABEL_MODEL_YEAR] = parsed_value
        details['car_model_year'] = parsed_value

        parsed_value = find_data_by_label(config.LABEL_MANUFACTURER, item_details_scope)
        if parsed_value is not None: details_kv[config.LABEL_MANUFACTURER] = parsed_value
        details['manufacturer'] = parsed_value

        parsed_value = find_data_by_label(config.LABEL_FUEL_TYPE, item_details_scope)
        if parsed_value is not None: details_kv[config.LABEL_FUEL_TYPE] = parsed_value
        details['car_fuel'] = parsed_value

        parsed_value = find_data_by_label(config.LABEL_TRANSMISSION, item_details_scope)
        if parsed_value is not None: details_kv[config.LABEL_TRANSMISSION] = parsed_value
        details['car_transmission'] = parsed_value

        parsed_value = find_data_by_label(config.LABEL_ENGINE_TYPE, item_details_scope)
        if parsed_value is not None: details_kv[config.LABEL_ENGINE_TYPE] = parsed_value
        details['engine_type'] = parsed_value

        parsed_value = find_data_by_label(config.LABEL_APPROVAL_NUMBER, item_details_scope)
        if parsed_value is not None: details_kv[config.LABEL_APPROVAL_NUMBER] = parsed_value
        details['approval_number'] = parsed_value

        parsed_value = find_data_by_label(config.LABEL_VIN, item_details_scope)
        if parsed_value is not None: details_kv[config.LABEL_VIN] = parsed_value
        details['vin'] = parsed_value
        
        displacement_raw = find_data_by_label(config.LABEL_DISPLACEMENT, item_details_scope)
        details['displacement_detail'] = None
        if displacement_raw is not None:
            details_kv[config.LABEL_DISPLACEMENT] = displacement_raw
            displacement_numeric_match = re.search(r'(\d+)', displacement_raw.replace(',', ''))
            if displacement_numeric_match:
                try:
                    details['displacement_detail'] = int(displacement_numeric_match.group(1))
                except ValueError:
                    pass

        parsed_value_mileage = find_data_by_label(config.LABEL_MILEAGE, item_details_scope)
        if parsed_value_mileage is not None:
            details_kv[config.LABEL_MILEAGE] = parsed_value_mileage
        details['mileage'] = parsed_value_mileage

        parsed_value_storage_loc = find_data_by_label(config.LABEL_STORAGE_LOCATION, item_details_scope)
        if parsed_value_storage_loc is not None:
            details_kv[config.LABEL_STORAGE_LOCATION] = parsed_value_storage_loc
            details['storage_location'] = parsed_value_storage_loc
    else: 
        # print("    Warning: Item details (목록내역) container not found.")
        pass 

    # print("Finished parsing detail page.")
    details['details_kv'] = details_kv
    return details

# --- Helper Functions for Parsing Detail Sections ---
def extract_date_history(rows: list[Tag]) -> list[dict]:
    """Parses rows from the date history table."""
    history = []
    for row in rows:
        cols = row.find_all('td')
        if len(cols) >= 5:
            try:
                history_item = {
                    '기일': text_or_none(safe_get_text(cols[0].find('nobr'))),
                    '기일종류': text_or_none(safe_get_text(cols[1].find('nobr'))),
                    '기일장소': text_or_none(safe_get_text(cols[2].find('nobr'))),
                    '최저매각가격': text_or_none(safe_get_text(cols[3].find('nobr'), default='0').replace(',', '').replace('원', '')),
                    '기일결과': text_or_none(safe_get_text(cols[4].find('nobr'))),
                }
                min_bid_price_val = history_item.get('최저매각가격')
                history_item['최저매각가격'] = min_bid_price_val if min_bid_price_val and min_bid_price_val.isdigit() else None
                history.append(history_item)
            except (IndexError, AttributeError) as e:
                # print(f"Warning: Error parsing date history row: {e}. Columns: {len(cols)}")
                pass 
    return history

def extract_similar_stats(rows: list[Tag]) -> list[dict]:
    """Parses rows from the similar sales statistics table."""
    stats = []
    for row in rows:
        cols = row.find_all('td')
        if len(cols) >= 6:
            try:
                stat_item = {
                    '기간': text_or_none(safe_get_text(cols[0].find('nobr'))),
                    '매각건수': text_or_none(safe_get_text(cols[1].find('nobr'))),
                    '평균감정가': text_or_none(safe_get_text(cols[2].find('nobr'), default='0').replace(',', '').replace('원', '')),
                    '평균매각가': text_or_none(safe_get_text(cols[3].find('nobr'), default='0').replace(',', '').replace('원', '')),
                    '매각가율': text_or_none(safe_get_text(cols[4].find('nobr'))),
                    '평균유찰횟수': text_or_none(safe_get_text(cols[5].find('nobr')))
                }
                for field_name in ['평균감정가', '평균매각가']:
                    val = stat_item.get(field_name)
                    stat_item[field_name] = val if val and val.isdigit() else None
                stats.append(stat_item)
            except (IndexError, AttributeError) as e:
                # print(f"Warning: Error parsing similar stats row: {e}. Columns: {len(cols)}")
                pass 
    return stats

def extract_document_links(doc_link_elements: list[Tag]) -> list[dict]:
    """Extracts document details from link elements."""
    docs = []
    for link in doc_link_elements:
        onclick_attr_raw = link.get('onclick', '')
        onclick_attr = text_or_none(onclick_attr_raw)
        
        text_raw = safe_get_text(link)
        text = text_or_none(text_raw)
        
        docs.append({'name': text, 'view_params': onclick_attr})
        # print(f"    Found doc link: {text} - Params: {onclick_attr[:50]}...") 
    return docs

def parse_case_detail_inquiry_page(html_content, case_no, item_no):
    """
    '사건상세조회' 페이지의 HTML 내용을 파싱하여 '담당계'와 '배당요구종기내역' 정보를 추출합니다.
    HTML 분석 결과를 바탕으로 실제 파싱 로직을 구현합니다.

    Args:
        html_content (str): '사건상세조회' 페이지의 HTML 소스.
        case_no (str): 사건번호 (디버깅 또는 로깅용).
        item_no (str): 물건번호 (디버깅 또는 로깅용).

    Returns:
        dict: {config.FIELDNAME_CASE_DEPARTMENT: "값", config.FIELDNAME_DIVIDEND_INFO: "값"}
              정보를 찾지 못한 경우 값은 None 또는 빈 문자열이 될 수 있습니다.
    """
    # print(f"{time.strftime('%H:%M:%S')} - Parsing case detail inquiry page for {case_no}-{item_no}")
    soup = BeautifulSoup(html_content, 'html.parser')
    data = {
        config.FIELDNAME_CASE_DEPARTMENT: None,
        config.FIELDNAME_DIVIDEND_INFO: None,
        config.FIELDNAME_DIVIDEND_STORAGE_METHOD: None
    }

    try:
        # 담당계 정보 추출 (ID 사용)
        department_div = soup.find('div', id='mf_wfm_mainFrame_spn_csBasDtsCharg')
        if department_div:
            # div 내부의 모든 텍스트를 합치고 공백 제거
            dept_text_raw = ' '.join(department_div.get_text(separator=' ', strip=True).split())
            data[config.FIELDNAME_CASE_DEPARTMENT] = text_or_none(dept_text_raw)
            # print(f"  Found 담당계: {dept_text}")
        else:
            # print(f"  DEBUG: Could not find '담당계' div (mf_wfm_mainFrame_spn_csBasDtsCharg) for {case_no}-{item_no}")
            pass

        # 배당요구종기내역 테이블 찾기
        dividend_table = soup.find('div', id='mf_wfm_mainFrame_grd_dstrtDemnDts')
        if dividend_table:
            tbody = dividend_table.find('tbody', id='mf_wfm_mainFrame_grd_dstrtDemnDts_body_tbody')
            if tbody:
                first_row = tbody.find('tr', attrs={'data-trindex': '0'})
                if first_row:
                    cols = first_row.find_all('td') # Find all cells in the row

                    # 배당요구종기일 추출 (세 번째 셀, 인덱스 2)
                    if len(cols) > 2:
                        dividend_cell = cols[2]
                        # Use ID as fallback if index fails, or vice-versa
                        # dividend_cell = first_row.find('td', id='mf_wfm_mainFrame_grd_dstrtDemnDts_cell_0_2')
                        if dividend_cell:
                            dividend_date_raw = dividend_cell.get_text(strip=True)
                            data[config.FIELDNAME_DIVIDEND_INFO] = text_or_none(dividend_date_raw)
                            # print(f"  Found 배당요구종기일: {dividend_date}")
                        else:
                             # print(f"  DEBUG: Could not find dividend date cell (idx 2) for {case_no}-{item_no}")
                             pass 
                    else:
                         # print(f"  DEBUG: Not enough cells found in dividend row (found {len(cols)}, need 3) for {case_no}-{item_no}")
                         pass 

                    # 보관방법 추출 (두 번째 셀, 인덱스 1의 텍스트 내용에서)
                    if len(cols) > 1:
                        location_storage_cell = cols[1]
                        # Use ID as fallback if index fails, or vice-versa
                        # location_storage_cell = first_row.find('td', id='mf_wfm_mainFrame_grd_dstrtDemnDts_cell_0_1')
                        if location_storage_cell:
                            full_text_raw = location_storage_cell.get_text(separator='\n', strip=True)
                            full_text = text_or_none(full_text_raw)
                            storage_method = None
                            if full_text:
                                for line in full_text.split('\n'):
                                    if '보관방법 :' in line:
                                        raw_storage_method = line.split('보관방법 :', 1)[-1].strip()
                                        storage_method = text_or_none(raw_storage_method)
                                        if storage_method and ", 보관장소 :" in storage_method:
                                            storage_method = text_or_none(storage_method.split(", 보관장소 :", 1)[0].strip())
                                        break 
                            data[config.FIELDNAME_DIVIDEND_STORAGE_METHOD] = storage_method
                            # print(f"  Found 배당요구_보관방법: {storage_method}")
                        else:
                            # print(f"  DEBUG: Could not find location/storage cell (idx 1) for {case_no}-{item_no}")
                            pass 
                    else: 
                        # print(f"  DEBUG: Not enough cells for storage method (found {len(cols)}, need at least 2) for {case_no}-{item_no}")
                        pass
                else:
                    # print(f"  DEBUG: Could not find first data row (trindex 0) in dividend table for {case_no}-{item_no}")
                    pass 
            else:
                 # print(f"  DEBUG: Could not find tbody in dividend table for {case_no}-{item_no}")
                 pass 
        else:
            # print(f"  DEBUG: Could not find dividend table div (mf_wfm_mainFrame_grd_dstrtDemnDts) for {case_no}-{item_no}")
            pass 

        # print(f"{time.strftime('%H:%M:%S')} - Parsed case inquiry data for {case_no}-{item_no}: {data}")

    except Exception as e:
        # print(f"Error parsing case detail inquiry page for {case_no}-{item_no}: {e}")
        # import traceback 
        # traceback.print_exc()
        pass 

    return data 

# def parse_appraisal_summary(auction_no: str, item_no_context: str, appraisal_summary_text: str) -> List[Dict[str, Optional[str]]]:
#     if not appraisal_summary_text or not appraisal_summary_text.strip():
#         return []
#     text = appraisal_summary_text.strip()
#     if config.DEBUG:
#         print(f"DEBUG_APPRAISAL: Entering parse_appraisal_summary. auction_no={auction_no}, item_no={item_no_context}")
#         print(f"DEBUG_APPRAISAL: Raw text (first 100 chars): {text[:100]}")
#         print(f"DEBUG_APPRAISAL: Raw text (repr, first 100 chars): {repr(text[:100])}")

#     if "평가완료된 물건에 대해서는 본 정보를 제공하지 않습니다" in text:
#         return [{
#             "auction_no": auction_no,
#             "item_no": item_no_context,
#             "summary_year_mileage": None,
#             "summary_color": None,
#             "summary_management_status": None,
#             "summary_fuel": None,
#             "summary_inspection_validity": None,
#             "summary_options_etc": text
#         }]
    
#     def extract(pat, full_text_to_search):
#         m = re.search(pat, full_text_to_search, flags=re.IGNORECASE|re.DOTALL)
#         return m.group(1).strip() if m else None

    # 각 항목의 제목 패턴 뒤에 오는 실제 내용을 캡처하도록 수정
    # (?P<title>...) 로 제목 부분을 명시하고, 그 뒤의 내용을 캡처
    # 각 extract 호출 시 전체 텍스트(text)를 전달해야 함
    # year_mileage_pattern = r"1\\)\\s*년식(?:및|과)?\\s*주행거리\\s*\\n([\\s\\S]*?)(?=(?:\\r?\\n)2\\)|$)"
    # year_mileage_pattern = r"1\\)\\s*년식(?:및|과)?\\s*주행거리\\s*\\n+([\\s\\S]*?)(?=\\n+2\\)|$)"

    # year_mileage_pattern = r"1\\)\\s*년식(?:및|과)?\\s*주행거리\\s*\\n+([\\s\\S]*?)(?=\\n{1,2}\\s*2\\))"
    
    # color_pattern        = r"2\\)\\s*색상\\s*\\n([\\s\\S]*?)(?=(?:\\r?\\n)3\\)|$)"
    # mng_status_pattern   = r"3\\)\\s*관리상태\\s*\\n([\\s\\S]*?)(?=(?:\\r?\\n)4\\)|$)"
    # fuel_pattern         = r"4\\)\\s*사용연료\\s*\\n([\\s\\S]*?)(?=(?:\\r?\\n)5\\)|$)"
    # validity_pattern     = r"5\\)\\s*유효검사기간\\s*\\n([\\s\\S]*?)(?=(?:\\r?\\n)6\\)|$)"
    # options_etc_pattern  = r"6\\)\\s*기타(?:\\s*\\(옵션등\\))?\\s*\\n([\\s\\S]*?)$"  # 마지막 항목

    # if config.DEBUG:
    #         print(f"DEBUG_APPRAISAL: year_mileage_pattern: {year_mileage_pattern}")

    # year_mileage = extract(year_mileage_pattern, text)
    # color        = extract(color_pattern, text)
    # mng_status   = extract(mng_status_pattern, text)
    # fuel         = extract(fuel_pattern, text)
    # validity     = extract(validity_pattern, text)
    # options_etc  = extract(options_etc_pattern, text)

    # if config.DEBUG:
    #         print(f"DEBUG_APPRAISAL: year_mileage_match_result: {year_mileage}")

    # return [{
    #     "auction_no": auction_no,
    #     "item_no": item_no_context,
    #     "summary_year_mileage": year_mileage,
    #     "summary_color": color,
    #     "summary_management_status": mng_status,
    #     "summary_fuel": fuel,
    #     "summary_inspection_validity": validity,
    #     "summary_options_etc": options_etc
    # }]

# ... (기존의 다른 parse_* 함수들) ...
# 예시: def parse_ongoing_list(html: str) -> list[dict]: ...
# 예시: def parse_detail_page(html_content: str, case_no: str, item_no: str) -> dict: ...
# 이 파일의 맨 아래 또는 적절한 위치에 parse_appraisal_summary 함수가 위치하도록 합니다.
# 기존 함수들과의 import 관계나 순서에 문제가 없도록 주의합니다. 
# 기존 함수들과의 import 관계나 순서에 문제가 없도록 주의합니다. 