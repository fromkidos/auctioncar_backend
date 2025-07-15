import re
import logging
from decimal import Decimal, InvalidOperation
from bs4 import BeautifulSoup, Tag
import os

from . import car_auction_config as config

logger = logging.getLogger(__name__)

def parse_list(html: str) -> list[dict]:
    """Parse the listing grid and extract auction info based on a structural row pattern.
    Assumes a fixed number of rows per item block in the grid.
    Extracts: auction_no, car_name, car_model_year, car_type, appraisal_value, min_bid_price, sale_date, sale_price, bid_rate.
    """
    soup = BeautifulSoup(html, 'html.parser')
    grid_body = soup.select_one(f'tbody#{config.RESULTS_GRID_BODY_ID}')
    if not grid_body:
        logger.warning("Results grid body not found in HTML.")
        return []

    all_trs = grid_body.find_all('tr', recursive=False)
    results = []
    logger.debug(f"Found {len(all_trs)} total TRs in the grid body for structural parsing.")

    ITEM_BLOCK_SIZE = 5
    DATA_ROW1_OFFSET_IN_BLOCK = 0
    DATA_ROW2_OFFSET_IN_BLOCK = 3

    i = 0
    while i + DATA_ROW2_OFFSET_IN_BLOCK < len(all_trs):
        row1 = all_trs[i + DATA_ROW1_OFFSET_IN_BLOCK]
        row2 = all_trs[i + DATA_ROW2_OFFSET_IN_BLOCK]

        cols1 = row1.select('td')
        cols2 = row2.select('td')

        if len(cols1) < 7 or len(cols2) < 3:
             logger.warning(f"Unexpected number of columns found in row pair (Row1: {len(cols1)}, Row2: {len(cols2)}) based on structural parsing at TR index {i}. Skipping.")
             if config.DEBUG:
                os.makedirs(config.DEBUG_DIR, exist_ok=True)
                filename = f"parser_unexpected_cols_tr_index_{i}_row1_{len(cols1)}_row2_{len(cols2)}.html"
                full_path = os.path.join(config.DEBUG_DIR, filename)
                try:
                    with open(full_path, "w", encoding="utf-8") as f_debug:
                        f_debug.write(html)
                    logger.info(f"Saved HTML due to unexpected columns warning to: {full_path}")
                except Exception as e_save:
                    logger.error(f"Failed to save debug HTML to {full_path}: {e_save}")
             i += ITEM_BLOCK_SIZE
             continue

        auction_no = "UNKNOWN_AUCTION_NO" # Default in case of early error
        try:
            case_info_tag = cols1[1].select_one('text')
            case_no_text = case_info_tag.get_text(strip=True) if case_info_tag else 'N/A'
            item_no_text = cols1[2].get_text(strip=True)
            auction_no = f"{case_no_text}-{item_no_text}" if case_no_text != 'N/A' else f"N/A-{item_no_text}"

            raw_title_text = 'N/A'
            location_desc_div = cols1[3].select_one('div')
            if location_desc_div:
                loc_tag = location_desc_div.select_one('text')
                if loc_tag:
                    br_tag = loc_tag.find_next_sibling('br')
                    if br_tag:
                        title_node = br_tag.next_sibling
                        if title_node and isinstance(title_node, str):
                            raw_title_text = title_node.strip()
                        elif br_tag.find_next_sibling('text'):
                            raw_title_text = br_tag.find_next_sibling('text').get_text(strip=True)
                    elif loc_tag.find_next_sibling('text'):
                        raw_title_text = loc_tag.find_next_sibling('text').get_text(strip=True)
                    else:
                        potential_title_from_loc = loc_tag.get_text(strip=True)
                        if '[' in potential_title_from_loc and ']' in potential_title_from_loc:
                            raw_title_text = potential_title_from_loc
            
            car_name = None
            car_model_year = None
            car_type = None
            if raw_title_text and raw_title_text != 'N/A':
                match_name_year = re.search(r"(?P<name_year_group>\[?(?P<name>.*?)\s+(?P<year>\d{4})\s*년식\s*)", raw_title_text)
                if match_name_year:
                    car_name = match_name_year.group('name').strip()
                    car_name = re.sub(r'\s*\(.*?\)\s*', '', car_name).strip()
                    try:
                        car_model_year = int(match_name_year.group('year'))
                    except ValueError:
                        car_model_year = None
                    name_year_end_pos = match_name_year.end('name_year_group')
                    potential_car_type = raw_title_text[name_year_end_pos:].strip()
                    if potential_car_type:
                        if potential_car_type.endswith(']'):
                            car_type = potential_car_type[:-1].strip()
                        else:
                            car_type = potential_car_type
                        if not car_type: car_type = None
                    else:
                        car_type = None
                else:
                    car_name = re.sub(r'\s*\(.*?\)\s*', '', raw_title_text.strip("[] ")).strip()

            appraisal_value_str = cols1[5].get_text(strip=True).replace(',', '')
            sale_date_text = 'N/A'
            dept_div = cols1[6].select_one('div')
            if dept_div:
                 br_tag = dept_div.select_one('br')
                 if br_tag and br_tag.next_sibling and isinstance(br_tag.next_sibling, str):
                      sale_date_text = br_tag.next_sibling.strip()
                 elif dept_div.select_one('text'):
                     first_text_in_dept_div = dept_div.select_one('text').get_text(strip=True)
                     if '.' in first_text_in_dept_div and first_text_in_dept_div.count('.') >= 2:
                         sale_date_text = first_text_in_dept_div

            usage_text = cols2[0].get_text(strip=True)
            if car_type is None:
                if usage_text and usage_text != 'N/A':
                    if "승용차" in usage_text: car_type = "승용차"
                    elif "화물차" in usage_text: car_type = "화물차"
                    elif "승합차" in usage_text: car_type = "승합차"
                    elif "버스" in usage_text : car_type = "버스"
                    elif "중기" in usage_text or "건설기계" in usage_text : car_type = "건설기계"
                    elif "특수차" in usage_text : car_type = "특수차"
                    elif "기타차량" in usage_text : car_type = "기타차량"
                    elif usage_text == '자동차': 
                        if car_name and any(kw in car_name.lower() for kw in ['트럭', '포터', '봉고', '카고', '탑차']):
                            car_type = "화물차"
                        else: car_type = "승용차"
                    elif len(usage_text) > 1 : car_type = usage_text 
                    else: car_type = "기타" 
            if car_type is None: car_type = "기타"

            min_bid_price_str = cols2[1].get_text(strip=True).replace(',', '')
            result_cell_nobr = cols2[2].select_one('nobr')
            result_status_text = 'N/A' 
            sale_price_str = '' 
            if result_cell_nobr:
                contents = result_cell_nobr.contents
                if contents:
                    if isinstance(contents[0], str):
                         result_status_text = contents[0].strip()
                    else:
                         result_status_text = result_cell_nobr.get_text(strip=True).split()[0] if result_cell_nobr.get_text(strip=True) else 'N/A'
                    if len(contents) > 2 and isinstance(contents[1], Tag) and contents[1].name == 'br' and isinstance(contents[2], str):
                        sale_price_str = contents[2].strip().replace(',', '')
                    elif result_status_text != '유찰': 
                        full_text = result_cell_nobr.get_text(strip=False)
                        potential_price = full_text.replace(result_status_text, '', 1).strip().replace(',', '')
                        if potential_price.isdigit(): sale_price_str = potential_price
            else:
                 fallback_text = cols2[2].get_text(strip=True)
                 parts = fallback_text.split()
                 if len(parts) > 0: result_status_text = parts[0]
                 if len(parts) > 1 and parts[1].replace(',', '').isdigit(): sale_price_str = parts[1].replace(',', '')
            
            bid_rate = None
            try:
                app_val = Decimal(appraisal_value_str) if appraisal_value_str else Decimal('0')
                s_price = Decimal(sale_price_str) if sale_price_str else None
                if s_price is not None and app_val > 0:
                    bid_rate = round((s_price / app_val) * 100, 2)
                elif result_status_text == '매각' and s_price is None and config.DEBUG:
                    logger.debug(f"DEBUG_BID_RATE: Auction No: {auction_no}, Marked '매각' but no sale price. Bid rate None.")
            except InvalidOperation:
                if config.DEBUG: logger.debug(f"DEBUG_BID_RATE: Auction No: {auction_no}, Decimal conversion error for bid_rate. Bid rate None.")
            except Exception as e_br:
                if config.DEBUG: logger.debug(f"DEBUG_BID_RATE: Auction No: {auction_no}, Error calculating bid rate: {e_br}. Bid rate None.")

            results.append({
                'auction_no': auction_no,
                'car_name': car_name,
                'car_model_year': car_model_year,
                'car_type': car_type,
                'appraisal_value': appraisal_value_str, 
                'min_bid_price': min_bid_price_str,    
                'sale_date': sale_date_text,
                'sale_price': sale_price_str if sale_price_str else None, 
                'bid_rate': float(bid_rate) if bid_rate is not None else None, 
                'auction_outcome': result_status_text
            })
        except (AttributeError, IndexError, TypeError) as e:
            logger.error(f"Error parsing a row for auction {auction_no}: {e}. Skipping.", exc_info=True)
            if config.DEBUG:
                 logger.debug(f"Problematic Row1 (TR index {i + DATA_ROW1_OFFSET_IN_BLOCK}): {row1}")
                 logger.debug(f"Problematic Row2 (TR index {i + DATA_ROW2_OFFSET_IN_BLOCK}): {row2}")
                 os.makedirs(config.DEBUG_DIR, exist_ok=True)
                 filename_err = f"parser_error_tr_index_{i}_auction_no_{auction_no.replace('/', '_').replace(':', '_')}.html"
                 full_path_err = os.path.join(config.DEBUG_DIR, filename_err)
                 try:
                     with open(full_path_err, "w", encoding="utf-8") as f_debug_err:
                         f_debug_err.write(html)
                     logger.info(f"Saved HTML due to parsing error to: {full_path_err}")
                 except Exception as e_save_err:
                     logger.error(f"Failed to save debug HTML (on error) to {full_path_err}: {e_save_err}")
            i += ITEM_BLOCK_SIZE
            continue
        
        i += ITEM_BLOCK_SIZE
    return results 