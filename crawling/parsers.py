#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Parsing functions for Court Auction website HTML content.
"""
import re
from bs4 import BeautifulSoup, Tag
from . import config # Import configuration for selectors and labels
import time
from typing import List, Dict, Optional # 필요한 경우 추가
import json # 추가

def safe_get_text(element: Tag | None, default: str = '정보 없음') -> str:
    """Safely extracts stripped text from a BeautifulSoup Tag object."""
    if element:
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
        # print(f"Ongoing results grid body ({config.RESULTS_GRID_BODY_ID}) not found in HTML. Verify ID.") # 정보성 로그는 유지 가능하나 일단 제거
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
            court = 'N/A'
            case_no_text = 'N/A'
            case_cell_nobr = cols1[1].find('nobr')
            if case_cell_nobr and case_cell_nobr.contents:
                if isinstance(case_cell_nobr.contents[0], str):
                    court = case_cell_nobr.contents[0].strip()
                if len(case_cell_nobr.contents) > 2 and isinstance(case_cell_nobr.contents[2], str):
                    case_no_text = case_cell_nobr.contents[2].strip()

            item_no_text = cols1[2].get_text(strip=True)
            auction_no = f"{case_no_text}-{item_no_text}" if case_no_text != 'N/A' and item_no_text else 'N/A'

            title_text = 'N/A'
            location_text = 'N/A'
            loc_div = cols1[3].find('div')
            if loc_div:
                loc_link = loc_div.find('a')
                if loc_link:
                    location_text = loc_link.get_text(strip=True).replace('사용본거지 :', '').strip()
                title_content = [c for c in loc_div.contents if isinstance(c, str) and c.strip()]
                if title_content:
                     title_text = title_content[0].strip()

            remarks_text = cols1[5].get_text(strip=True)
            appraisal_text = cols1[6].get_text(strip=True).replace(',', '').replace('원', '')
            min_bid_price_text = cols2[1].get_text(strip=True).replace(',', '').replace('원', '')

            sale_date_text = 'N/A'
            dept_date_nobr = cols1[7].find('nobr')
            if dept_date_nobr and dept_date_nobr.contents:
                 if len(dept_date_nobr.contents) > 2 and isinstance(dept_date_nobr.contents[2], str):
                      sale_date_text = dept_date_nobr.contents[2].strip()

            status_text = cols2[2].get_text(strip=True)

            if auction_no == 'N/A':
                # print(f"Warning: Missing auction_no ({auction_no}) for row index {tr_index_attr}. Skipping.")
                continue

            # Split case_no_text into year and number
            case_year = 'N/A'
            case_num_part = 'N/A'
            if case_no_text != 'N/A' and '타경' in case_no_text:
                parts = case_no_text.split('타경', 1)
                if len(parts) == 2:
                    case_year = parts[0]
                    case_num_part = parts[1]
            
            results.append({
                'auction_no': auction_no,
                'court_name': court,
                'case_year': case_year,
                'case_number': case_num_part,
                'item_no': item_no_text,
                'location_address': location_text,
                'appraisal_price': appraisal_text,
                'min_bid_price': min_bid_price_text,
                'sale_date': sale_date_text,
                'status': status_text,
            })
        except (AttributeError, IndexError, TypeError) as e:
            # 오류 발생 시 auction_no를 식별하려는 시도 (best-effort)
            error_auction_no = 'unknown'
            try:
                err_case_no = 'N/A'
                err_item_no = 'N/A'
                err_case_cell_nobr = cols1[1].find('nobr')
                if err_case_cell_nobr and err_case_cell_nobr.contents:
                    if len(err_case_cell_nobr.contents) > 2 and isinstance(err_case_cell_nobr.contents[2], str):
                        err_case_no = err_case_cell_nobr.contents[2].strip()
                err_item_no = cols1[2].get_text(strip=True)
                if err_case_no != 'N/A' and err_item_no:
                     error_auction_no = f"{err_case_no}-{err_item_no}"
            except: pass # auction_no 식별 중 오류는 무시

            # print(f"Error parsing ongoing row (trindex: {tr_index_attr}, trying auction_no: {error_auction_no}): {e}. Skipping.") # 오류 로그는 유지 고려, 하지만 일단 제거
            if config.DEBUG:
                 # print(f"Row1 HTML causing error: {row1}") # 오류 발생 행 HTML 출력
                 # print(f"Row2 HTML causing error: {row2}") # 오류 발생 행 HTML 출력
                 pass # Added pass to avoid indentation error if prints are commented
            continue

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
    docs = []
    date_history = []
    similar_sales_stats = {}

    # Helper function nested inside to access soup directly
    def find_data_by_label(label_text: str, scope: Tag | None = None) -> str:
        """Finds the sibling td/span text for a given th/label text within the scope."""
        if scope is None:
            scope = soup

        label_th = scope.find('th', string=lambda t: t and label_text in t.strip())
        if label_th and label_th.find_next_sibling('td'):
            value_td = label_th.find_next_sibling('td')
            value_span = value_td.find('span')
            if value_span:
                 if label_text == config.LABEL_DEPARTMENT:
                     dept_span = value_span.find('span', id=lambda x: x and 'cortAuctnJdbnNm' in x)
                     if dept_span: return safe_get_text(dept_span)
                 if label_text == config.LABEL_ITEM_REMARKS:
                      rmk_div = value_span.find('div')
                      if rmk_div: return safe_get_text(rmk_div)
                 return safe_get_text(value_span)
            return safe_get_text(value_td)

        label_element = scope.find(lambda tag: tag.name in ['label', 'div', 'span', 'th'] and label_text in tag.get_text(strip=True))
        if label_element:
            parent_row = label_element.find_parent('tr')
            if parent_row:
                value_td = parent_row.find('td')
                if value_td:
                    value_span = value_td.find('span')
                    if value_span: return safe_get_text(value_span)
                    return safe_get_text(value_td)
            next_sibling_span = label_element.find_next_sibling(['span', 'div'])
            if next_sibling_span: return safe_get_text(next_sibling_span)

        return '정보 없음'

    # --- Basic Info Extraction ---
    # print("  Extracting basic info...")
    basic_info_header_text = getattr(config, 'HEADER_BASIC_INFO', "물건기본정보")
    basic_info_container = soup.find('h3', string=lambda t: t and basic_info_header_text in t.strip())
    basic_scope = basic_info_container.find_parent() if basic_info_container else soup
    details['kind'] = find_data_by_label(config.LABEL_KIND, basic_scope)
    details['appraisal_price'] = find_data_by_label(config.LABEL_APPRAISAL_PRICE, basic_scope).replace(',', '').replace('원', '')
    
    details['min_bid_price'] = None
    details['min_bid_price_2'] = None 
    label_th_min_bid = basic_scope.find('th', string=lambda t: t and config.LABEL_MIN_BID_PRICE in t.strip())
    if label_th_min_bid and label_th_min_bid.find_next_sibling('td'):
        value_td = label_th_min_bid.find_next_sibling('td')
        value_span = value_td.find('span') 
        if value_span:
            raw_html_content_for_lowest_price = ''.join(str(content) for content in value_span.contents)
            
            if raw_html_content_for_lowest_price:
                text_content_without_images = re.sub(r'<img[^>]*>', '', raw_html_content_for_lowest_price)
                price_strings = []
                temp_soup = BeautifulSoup(text_content_without_images.replace('<br/>', '<br>'), 'html.parser')
                current_text_parts = []
                for content_node in temp_soup.contents:
                    if content_node.name == 'br':
                        if current_text_parts:
                            price_strings.append(" ".join(current_text_parts).strip())
                            current_text_parts = []
                    else:
                        current_text_parts.append(content_node.get_text(strip=True) if hasattr(content_node, 'get_text') else str(content_node).strip())
                if current_text_parts: 
                    price_strings.append(" ".join(current_text_parts).strip())
                
                price_strings = [p for p in price_strings if p] 

                def _clean_and_convert_price(price_str_with_currency):
                    if not price_str_with_currency:
                        return None
                    numeric_string = re.sub(r'[^\d]', '', price_str_with_currency)
                    try:
                        return int(numeric_string)
                    except ValueError:
                        return None

                if len(price_strings) > 0:
                    details['min_bid_price'] = _clean_and_convert_price(price_strings[0])
                if len(price_strings) > 1:
                    details['min_bid_price_2'] = _clean_and_convert_price(price_strings[1])
        
        elif value_td and not details['min_bid_price']:
             simple_price_text = safe_get_text(value_td).replace(',', '').replace('원', '')
             if simple_price_text:
                 details['min_bid_price'] = int(simple_price_text) if simple_price_text.isdigit() else None

    details['bid_method'] = find_data_by_label(config.LABEL_BID_METHOD, basic_scope)
    sale_date_text_full_detail = find_data_by_label(config.LABEL_SALE_DATE_TIME_LOC, basic_scope)
    details['sale_date'] = 'N/A'
    details['sale_time'] = 'N/A'
    details['sale_location'] = 'N/A'
    if sale_date_text_full_detail != '정보 없음':
        parts = sale_date_text_full_detail.split()
        if len(parts) >= 1: details['sale_date'] = parts[0]
        if len(parts) >= 2: details['sale_time'] = parts[1]
        if len(parts) >= 3: details['sale_location'] = ' '.join(parts[2:])
    details['other_details'] = find_data_by_label(config.LABEL_ITEM_REMARKS, basic_scope)

    case_info_header_text = getattr(config, 'HEADER_CASE_INFO', "사건기본내역")
    case_info_container = soup.find('h3', string=lambda t: t and case_info_header_text in t.strip())
    case_scope = case_info_container.find_parent() if case_info_container else soup
    details['case_received_date'] = find_data_by_label(config.LABEL_CASE_RECEIVED, case_scope)
    details['auction_start_date'] = find_data_by_label(config.LABEL_AUCTION_START_DATE, case_scope)
    details['distribution_due_date'] = find_data_by_label(config.LABEL_DISTRIBUTION_DUE_DATE, case_scope)
    details['claim_amount'] = find_data_by_label(config.LABEL_CLAIM_AMOUNT, case_scope).replace(',', '').replace('원', '')

    if pre_collected_photo_urls is not None:
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
        except Exception: pass
    else:
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
        except Exception as e: 
             pass 
    details['total_photo_count'] = total_photo_count

    photo_urls = []
    all_img_tags = soup.find_all('img', id=lambda x: x and 'img_reltPic' in x)
    processed_urls = set()
    for img_tag in all_img_tags:
         if img_tag and 'src' in img_tag.attrs:
             src = img_tag['src']
             if src and src != '#':
                 full_url = src 
                 if full_url not in processed_urls:
                     photo_urls.append(full_url)
                     processed_urls.add(full_url)
    details['photo_urls'] = photo_urls

    doc_links_elements = soup.select(config.DETAIL_DOCS_LIST_SELECTOR)
    if doc_links_elements: docs = extract_document_links(doc_links_elements)
    details['documents'] = docs

    # --- Date History Extraction ---
    date_history_table = soup.select_one(config.DETAIL_DATE_HISTORY_TABLE_SELECTOR)
    if date_history_table:
        date_rows = date_history_table.select('tr[data-tr-id="row2"]')
        if not date_rows: 
            tbody = date_history_table.find('tbody')
            if tbody:
                date_rows = tbody.find_all('tr', recursive=False)
        if date_rows:
            date_history_data = extract_date_history(date_rows)
            if date_history_data:
                 details['date_history'] = date_history_data
    
    if config.DEBUG:
        if 'date_history' not in details or not details['date_history']:
            print(f"DEBUG_PARSING [{case_no}-{item_no}]: DateHistory - Not found or empty. Selector: '{config.DETAIL_DATE_HISTORY_TABLE_SELECTOR}'")
            debug_table = soup.select_one(config.DETAIL_DATE_HISTORY_TABLE_SELECTOR)
            if debug_table:
                print(f"DEBUG_PARSING [{case_no}-{item_no}]: DateHistory - Table HTML (first 500 chars): {str(debug_table)[:500]}")
            else:
                print(f"DEBUG_PARSING [{case_no}-{item_no}]: DateHistory - Table NOT FOUND with the selector.")
                header_text = getattr(config, 'HEADER_DATE_HISTORY', "기일내역") 
                header_debug = soup.find(lambda tag: tag.name == 'h3' and header_text in tag.get_text(strip=True))
                if header_debug:
                    print(f"DEBUG_PARSING [{case_no}-{item_no}]: DateHistory - Header '{header_text}' FOUND. Table might be nearby or selector needs adjustment.")
                else:
                    print(f"DEBUG_PARSING [{case_no}-{item_no}]: DateHistory - Header '{header_text}' NOT FOUND.")
        else: 
             print(f"DEBUG_PARSING [{case_no}-{item_no}]: DateHistory - Parsed {len(details['date_history'])} items.")

    # --- Similar Sales Statistics Extraction ---
    similar_stats_table = soup.select_one(f'table#{config.DETAIL_SIMILAR_STATS_TABLE_ID}')
    if similar_stats_table:
        similar_stats_tbody = similar_stats_table.find('tbody')
        if similar_stats_tbody:
            stats_rows = similar_stats_tbody.find_all('tr', recursive=False) 
            if stats_rows:
                similar_sales_stats_list = extract_similar_stats(stats_rows)
                if similar_sales_stats_list:
                    details['similar_sales_stats'] = similar_sales_stats_list
            
    if config.DEBUG:
        if 'similar_sales_stats' not in details or not details['similar_sales_stats']:
            print(f"DEBUG_PARSING [{case_no}-{item_no}]: SimilarSalesStats - Not found or empty. Table ID: '{config.DETAIL_SIMILAR_STATS_TABLE_ID}'")
            debug_table = soup.select_one(f'table#{config.DETAIL_SIMILAR_STATS_TABLE_ID}')
            if debug_table:
                print(f"DEBUG_PARSING [{case_no}-{item_no}]: SimilarSalesStats - Table HTML (first 500 chars): {str(debug_table)[:500]}")
            else:
                print(f"DEBUG_PARSING [{case_no}-{item_no}]: SimilarSalesStats - Table NOT FOUND with the ID.")
                parent_div_id = getattr(config, 'DETAIL_SIMILAR_STATS_CONTENT_DIV_ID', None)
                if parent_div_id:
                    parent_div_debug = soup.select_one(f"div#{parent_div_id}")
                    if parent_div_debug:
                        print(f"DEBUG_PARSING [{case_no}-{item_no}]: SimilarSalesStats - Parent div (ID: {parent_div_id}) FOUND. Table exists within?: {parent_div_debug.find('table') is not None}")
                    else:
                        print(f"DEBUG_PARSING [{case_no}-{item_no}]: SimilarSalesStats - Parent div (ID: {parent_div_id}) NOT FOUND.")
        else:
            print(f"DEBUG_PARSING [{case_no}-{item_no}]: SimilarSalesStats - Parsed {len(details['similar_sales_stats'])} items.")

    # --- Appraisal Summary Extraction (New HTML Structure) ---
    appraisal_summary_data = {
        "summary_year_mileage": None, "summary_color": None, "summary_management_status": None,
        "summary_fuel": None, "summary_inspection_validity": None, "summary_options_etc": None
    }
    appraisal_main_container = soup.select_one(f'div#{config.DETAIL_APPRAISAL_SUMMARY_MAIN_DIV_ID}')
    if appraisal_main_container:
        message_div = appraisal_main_container.find('div', string=lambda text: text and "평가완료된 물건에 대해서는 본 정보를 제공하지 않습니다" in text)
        if message_div:
            appraisal_summary_data["summary_options_etc"] = safe_get_text(message_div)
        else:
            summary_items_list = appraisal_main_container.find('ul', id=lambda x: x and 'sum_list' in x.split() and 'w2group' in x.split())
            if summary_items_list:
                current_item_container = summary_items_list.find('li', id=lambda x: x and 'gen_aeeEvlMnpntCtt' in x) 
                if current_item_container: 
                    subtitles = current_item_container.find_all('div', class_='w2textbox subtit', recursive=False)
                    for subtitle_div in subtitles:
                        title_text = safe_get_text(subtitle_div)
                        next_ul = subtitle_div.find_next_sibling('ul', class_='depth2')
                        if next_ul:
                            value_div = next_ul.find('div', class_='w2textbox') 
                            value_text = safe_get_text(value_div)
                            if "년식 및 주행거리" in title_text: appraisal_summary_data["summary_year_mileage"] = value_text
                            elif "색상" in title_text: appraisal_summary_data["summary_color"] = value_text
                            elif "관리상태" in title_text: appraisal_summary_data["summary_management_status"] = value_text
                            elif "사용연료" in title_text: appraisal_summary_data["summary_fuel"] = value_text
                            elif "유효검사기간" in title_text: appraisal_summary_data["summary_inspection_validity"] = value_text
                            elif "기타(옵션등)" in title_text or "기타" in title_text: appraisal_summary_data["summary_options_etc"] = value_text
    
    if not all(value is None for value in appraisal_summary_data.values()):
        details['appraisal_summary'] = appraisal_summary_data

    if config.DEBUG:
        parsed_summary = details.get('appraisal_summary', {})
        is_empty_summary = not parsed_summary or all(value is None for value in parsed_summary.values())
        if is_empty_summary:
            print(f"DEBUG_PARSING [{case_no}-{item_no}]: AppraisalSummary - Not found or all fields are None. Main Div ID: '{config.DETAIL_APPRAISAL_SUMMARY_MAIN_DIV_ID}'")
            debug_container = soup.select_one(f'div#{config.DETAIL_APPRAISAL_SUMMARY_MAIN_DIV_ID}')
            if debug_container:
                print(f"DEBUG_PARSING [{case_no}-{item_no}]: AppraisalSummary - Main container HTML (first 500 chars): {str(debug_container)[:500]}")
                message_div_debug = debug_container.find('div', string=lambda text: text and "평가완료된 물건에 대해서는 본 정보를 제공하지 않습니다" in text)
                if message_div_debug:
                    print(f"DEBUG_PARSING [{case_no}-{item_no}]: AppraisalSummary - Found '정보 제공 안함' message: {safe_get_text(message_div_debug)}")
            else:
                print(f"DEBUG_PARSING [{case_no}-{item_no}]: AppraisalSummary - Main container NOT FOUND with the ID.")
                header_text = getattr(config, 'HEADER_APPRAISAL', "감정평가요항표") 
                header_debug = soup.find(lambda tag: tag.name == 'h3' and header_text in tag.get_text(strip=True))
                if header_debug:
                     print(f"DEBUG_PARSING [{case_no}-{item_no}]: AppraisalSummary - Header '{header_text}' FOUND. Main container (ID: {config.DETAIL_APPRAISAL_SUMMARY_MAIN_DIV_ID}) might be missing or selector needs adjustment.")
                else:
                    print(f"DEBUG_PARSING [{case_no}-{item_no}]: AppraisalSummary - Header '{header_text}' NOT FOUND.")
        else:
            print(f"DEBUG_PARSING [{case_no}-{item_no}]: AppraisalSummary - Parsed: {json.dumps(parsed_summary, ensure_ascii=False, indent=2)}")

    # --- Item Details Extraction ---
    item_details_header_text = getattr(config, 'HEADER_ITEM_DETAILS', "목록내역")
    item_details_container = soup.find('h3', string=lambda t: t and item_details_header_text in t.strip())
    item_details_scope = item_details_container.find_next('div') if item_details_container else soup
    if item_details_scope and item_details_scope.name != 'table':
        table_in_div = item_details_scope.find('table')
        if table_in_div: item_details_scope = table_in_div
            
    if item_details_scope:
        details['car_name'] = find_data_by_label(config.LABEL_CAR_NAME, item_details_scope)
        details['car_type'] = find_data_by_label(config.LABEL_CAR_TYPE, item_details_scope)
        details['car_reg_number'] = find_data_by_label(config.LABEL_REG_NUMBER, item_details_scope)
        details['car_model_year'] = find_data_by_label(config.LABEL_MODEL_YEAR, item_details_scope)
        details['manufacturer'] = find_data_by_label(config.LABEL_MANUFACTURER, item_details_scope)
        details['car_fuel'] = find_data_by_label(config.LABEL_FUEL_TYPE, item_details_scope)
        details['car_transmission'] = find_data_by_label(config.LABEL_TRANSMISSION, item_details_scope)
        displacement_text = find_data_by_label(config.LABEL_DISPLACEMENT, item_details_scope)
        if displacement_text and displacement_text != '정보 없음':
            cleaned_displacement = displacement_text.lower().replace('cc', '').replace(',', '').strip()
            try:
                details['displacement'] = int(cleaned_displacement)
            except ValueError:
                if config.DEBUG: print(f"DEBUG_INT_CONVERSION for {case_no}-{item_no}: Displacement '{displacement_text}' to int failed. Raw: '{cleaned_displacement}'")
                details['displacement'] = None
        else:
            details['displacement'] = None

        mileage_text = find_data_by_label(config.LABEL_MILEAGE, item_details_scope)
        if mileage_text and mileage_text != '정보 없음':
            cleaned_mileage = mileage_text.replace(',', '').strip()
            try:
                details['car_mileage'] = int(cleaned_mileage)
            except ValueError:
                if config.DEBUG: print(f"DEBUG_INT_CONVERSION for {case_no}-{item_no}: Mileage '{mileage_text}' to int failed. Raw: '{cleaned_mileage}'")
                details['car_mileage'] = None
        else:
            details['car_mileage'] = None
            
        details['engine_type'] = find_data_by_label(config.LABEL_ENGINE_TYPE, item_details_scope)
        details['approval_number'] = find_data_by_label(config.LABEL_APPROVAL_NUMBER, item_details_scope)
        details['car_vin'] = find_data_by_label(config.LABEL_VIN, item_details_scope)
        details['storage_location'] = find_data_by_label(config.LABEL_STORAGE_LOCATION, item_details_scope)
    else: 
        if config.DEBUG: print(f"DEBUG_PARSING [{case_no}-{item_no}]: ItemDetails (목록내역) - Container or scope NOT FOUND. Header: '{item_details_header_text}'")

    if config.DEBUG:
        print(f"DEBUG_FINAL_DETAILS for {case_no}-{item_no}: {json.dumps(details, ensure_ascii=False, indent=2)}")
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
                    '기일': safe_get_text(cols[0].find('nobr')),
                    '기일종류': safe_get_text(cols[1].find('nobr')),
                    '기일장소': safe_get_text(cols[2].find('nobr')),
                    '최저매각가격': safe_get_text(cols[3].find('nobr')).replace(',', '').replace('원', ''),
                    '기일결과': safe_get_text(cols[4].find('nobr')),
                }
                if any(history_item.values()):
                    history.append(history_item)
            except (IndexError, AttributeError) as e:
                if config.DEBUG: print(f"DEBUG_EXTRACT_DATE_HISTORY: Error parsing date history row: {e}. Columns: {len(cols)}, Row HTML: {str(row)[:200]}")
                pass 
    return history

def extract_similar_stats(rows: list[Tag]) -> list[dict]:
    """Parses rows from the similar sales statistics table."""
    stats_list = []
    column_mapping = {
        "dspslMonth": "period", "dspslCnt": "sale_count",
        "aeeEvlAmt": "avg_appraisal_price", "dspslAmt": "avg_sale_price",
        "dspslPrcRate": "sale_price_ratio", "flbdNcnt": "avg_bids_count"
    }
    for row in rows:
        cells = row.find_all('td', recursive=False)
        stat_item = {}
        for cell in cells:
            col_id = cell.get('data-col_id')
            nobr_tag = cell.find('nobr', class_='w2grid_input')
            text_value = safe_get_text(nobr_tag, '')
            
            if col_id in column_mapping:
                key_name = column_mapping[col_id]
                if key_name in ["avg_appraisal_price", "avg_sale_price"]: text_value = text_value.replace(',', '').replace('원', '')
                elif key_name == "sale_count": text_value = text_value.replace('건', '')
                elif key_name == "sale_price_ratio": text_value = text_value.replace('%', '')
                elif key_name == "avg_bids_count": text_value = text_value.replace('회', '')
                stat_item[key_name] = text_value
        if stat_item and any(stat_item.values()):
            stats_list.append(stat_item)
    return stats_list

def extract_document_links(doc_link_elements: list[Tag]) -> list[dict]:
    """Extracts document details from link elements."""
    docs = []
    for link in doc_link_elements:
        onclick_attr = link.get('onclick', '')
        text = safe_get_text(link)
        match = re.search(r"orpOpen\\('([^']*)'\\s*,\\s*'([^']*)'\\s*,\\s*'([^']*)'\\)", onclick_attr)
        view_params = {'raw_onclick': onclick_attr}
        if match:
            view_params['type'] = match.group(1)
            view_params['id'] = match.group(2)
            view_params['seq'] = match.group(3)

        docs.append({'name': text, 'view_params': view_params})
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
    soup = BeautifulSoup(html_content, 'html.parser')
    data = {
        config.FIELDNAME_CASE_DEPARTMENT: None,
        config.FIELDNAME_DIVIDEND_INFO: None,
        config.FIELDNAME_DIVIDEND_STORAGE_METHOD: None
    }

    try:
        department_div = soup.find('div', id='mf_wfm_mainFrame_spn_csBasDtsCharg')
        if department_div:
            dept_text = ' '.join(department_div.get_text(separator=' ', strip=True).split())
            data[config.FIELDNAME_CASE_DEPARTMENT] = dept_text

        dividend_table = soup.find('div', id='mf_wfm_mainFrame_grd_dstrtDemnDts')
        if dividend_table:
            tbody = dividend_table.find('tbody', id='mf_wfm_mainFrame_grd_dstrtDemnDts_body_tbody')
            if tbody:
                first_row = tbody.find('tr', attrs={'data-trindex': '0'})
                if first_row:
                    cols = first_row.find_all('td')
                    if len(cols) > 2:
                        dividend_cell = cols[2]
                        data[config.FIELDNAME_DIVIDEND_INFO] = dividend_cell.get_text(strip=True)
                    if len(cols) > 1:
                        location_storage_cell = cols[1]
                        full_text = location_storage_cell.get_text(separator='\\n', strip=True)
                        storage_method = '정보 없음' 
                        for line in full_text.split('\\n'):
                            if '보관방법 :' in line:
                                raw_storage_method = line.split('보관방법 :', 1)[-1].strip()
                                storage_method = raw_storage_method.split(", 보관장소 :", 1)[0].strip() if ", 보관장소 :" in raw_storage_method else raw_storage_method
                                break 
                        data[config.FIELDNAME_DIVIDEND_STORAGE_METHOD] = storage_method
    except Exception as e:
        if config.DEBUG: print(f"DEBUG_PARSE_CASE_DETAIL_INQUIRY for {case_no}-{item_no}: Error - {e}")
    return data 

# ... (기존의 다른 parse_* 함수들) ...
# 예시: def parse_ongoing_list(html: str) -> list[dict]: ...
# 예시: def parse_detail_page(html_content: str, case_no: str, item_no: str) -> dict: ...
# 이 파일의 맨 아래 또는 적절한 위치에 parse_appraisal_summary 함수가 위치하도록 합니다.
# 기존 함수들과의 import 관계나 순서에 문제가 없도록 주의합니다. 