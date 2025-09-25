#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HTML parsing functions for car auction results from the Korean Court Auction system.
Parses the listing pages to extract auction result data.
"""
import re
import logging
from bs4 import BeautifulSoup, Tag
from typing import List, Dict, Optional
from . import car_auction_config as config

logger = logging.getLogger(__name__)

def safe_get_text(element: Tag | None, default: str = 'N/A') -> str:
    """Safely extracts stripped text from a BeautifulSoup Tag object."""
    if element:
        text = element.get_text(strip=True)
        return text if text else default
    return default

def safe_get_multiline_text(element: Tag | None, default: str = 'N/A') -> List[str]:
    """Safely extracts text from a BeautifulSoup Tag object, preserving line breaks."""
    if element:
        text = element.get_text(separator='\n', strip=True)
        if text:
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            return lines if lines else [default]
        return [default]
    return [default]

def clean_number_text(text: str) -> str:
    """Remove commas and other formatting from number strings."""
    if not text or text == 'N/A':
        return text
    return re.sub(r'[,\s]', '', text)

def extract_sale_price_from_multiline(lines: List[str]) -> Optional[str]:
    """Extract sale price from multiline text format like ['매각', '26,580,000']."""
    if not lines:
        return None
    
    # First line should contain the result (매각/유찰)
    result = lines[0] if len(lines) > 0 else ''
    
    # If it's '유찰' (no sale), return None
    if '유찰' in result:
        return None
    
    # Second line should contain the price
    if len(lines) > 1:
        price_text = lines[1]
        # Remove commas and extract numbers
        number_match = re.search(r'([\d,]+)', price_text)
        if number_match:
            return number_match.group(1).replace(',', '')
    
    return None

def extract_sale_price(text: str) -> Optional[str]:
    """Extract numeric sale price from text like '매각41388000' or '유찰' or multiline format."""
    if not text or text == 'N/A':
        return None
    
    # Check if text contains line breaks (multiline format)
    if '\n' in text or ('매각' in text and any(char.isdigit() for char in text)):
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        return extract_sale_price_from_multiline(lines)
    
    # If it's '유찰' (no sale), return None
    if '유찰' in text:
        return None
    
    # Extract numbers from text like '매각41388000'
    number_match = re.search(r'(\d+)', text)
    if number_match:
        return number_match.group(1)
    
    return None

def parse_bid_rate(text: str) -> Optional[str]:
    """Parse bid rate percentage to decimal string."""
    if not text or text == 'N/A':
        return None

    # Remove % symbol and whitespace
    cleaned = re.sub(r'[%\s]', '', text.strip())
    
    # Try to extract numeric value
    number_match = re.search(r'(\d+(?:\.\d+)?)', cleaned)
    if number_match:
        # Convert percentage to decimal (e.g., "100%" -> "1.0")
        percentage = float(number_match.group(1))
        decimal = percentage / 100.0
        return str(decimal)
    
    return None

def parse_date_from_multiline(lines: List[str]) -> Optional[str]:
    """Parse date from multiline text format like ['경매7계', '2025.09.18']."""
    if not lines or len(lines) < 2:
        return None
    
    # Second line should contain the date
    date_text = lines[1] if len(lines) > 1 else lines[0]
    
    # Look for date pattern in format like "2025.09.18"
    date_match = re.search(r'(\d{4}\.\d{1,2}\.\d{1,2})', date_text)
    if date_match:
        date_str = date_match.group(1)
        try:
            # Convert to ISO 8601 format with time (YYYY-MM-DDTHH:mm:ss.sssZ)
            parts = date_str.split('.')
            if len(parts) == 3:
                year, month, day = parts
                # Add default time (10:00:00 AM KST as it's typical auction time)
                return f"{year}-{int(month):02d}-{int(day):02d}T10:00:00.000Z"
        except Exception:
            pass
    
    return None

def parse_date_text(text: str) -> Optional[str]:
    """Parse and normalize date text, extracting date from auction result format."""
    if not text or text == 'N/A':
        return None
    
    # Check if text contains line breaks (multiline format)
    if '\n' in text:
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        return parse_date_from_multiline(lines)
    
    # Look for date pattern in format like "경매13계2025.09.24" or just "2025.09.24"
    date_match = re.search(r'(\d{4}\.\d{1,2}\.\d{1,2})', text)
    if date_match:
        date_str = date_match.group(1)
        try:
            # Convert to ISO 8601 format with time (YYYY-MM-DDTHH:mm:ss.sssZ)
            parts = date_str.split('.')
            if len(parts) == 3:
                year, month, day = parts
                # Add default time (10:00:00 AM KST as it's typical auction time)
                return f"{year}-{int(month):02d}-{int(day):02d}T10:00:00.000Z"
        except Exception:
            pass
    
    return None

def parse_list(html: str) -> List[Dict[str, str]]:
    """
    Parse the auction result listing grid from the Korean Court Auction system.
    Uses the same 2-row structure as ongoing auctions (row2 + row5).
    
    Args:
        html: The HTML content of the results page
        
    Returns:
        List of dictionaries containing auction result data
    """
    soup = BeautifulSoup(html, 'html.parser')
    grid_body = soup.select_one(f'tbody#{config.RESULTS_GRID_BODY_ID}')
    
    if not grid_body:
        logger.warning(f"Results grid body ({config.RESULTS_GRID_BODY_ID}) not found in HTML.")
        return []

    # Find all starting rows (data-tr-id="row2") - similar to ongoing auctions
    start_rows = grid_body.find_all('tr', attrs={'data-tr-id': 'row2'}, recursive=False)
    results = []
    
    logger.debug(f"Found {len(start_rows)} potential auction result starting rows.")
    
    # Debug: Save HTML for analysis
    if config.DEBUG and len(start_rows) > 0:
        import os
        os.makedirs(config.DEBUG_DIR, exist_ok=True)
        debug_html_path = os.path.join(config.DEBUG_DIR, 'car_auction_results_sample.html')
        with open(debug_html_path, 'w', encoding='utf-8') as f:
            f.write(str(grid_body))
        logger.info(f"Saved HTML sample to {debug_html_path} for analysis")

    for index, row1 in enumerate(start_rows):
        try:
            tr_index_attr = row1.get('data-trindex')
            if tr_index_attr is None:
                logger.debug(f"Warning: Could not find data-trindex for row at enumerate index {index}. Skipping.")
                continue

            # Find the matching second row (data-tr-id="row5" for auction results)
            row2 = row1.find_next_sibling('tr', attrs={'data-tr-id': 'row5'})
            if not row2:
                logger.debug(f"Could not find matching second row (row5) for starting row index {tr_index_attr}. Skipping.")
                continue

            cols1 = row1.find_all('td', recursive=False)
            cols2 = row2.find_all('td', recursive=False)

            # Minimum column count check
            if len(cols1) < 6 or len(cols2) < 3:
                logger.debug(f"Unexpected number of columns found (Row1: {len(cols1)}, Row2: {len(cols2)}). Skipping row index {tr_index_attr}.")
                continue
            
            # Debug: Log first few rows to understand structure
            if config.DEBUG and index < 3:
                col1_texts = [safe_get_text(col)[:30] + "..." if len(safe_get_text(col)) > 30 else safe_get_text(col) for col in cols1[:10]]
                col2_texts = [safe_get_text(col)[:30] + "..." if len(safe_get_text(col)) > 30 else safe_get_text(col) for col in cols2[:5]]
                logger.info(f"Row {index} - Row1 ({len(cols1)} cols): {col1_texts}")
                logger.info(f"Row {index} - Row2 ({len(cols2)} cols): {col2_texts}")

            try:
                # Extract data based on actual column structure
                # Note: These indices need to be adjusted based on the actual HTML structure
                
                # Row1 columns (main info)
                # Column 1: Court info and base auction number (multiline format)
                court_auction_lines = safe_get_multiline_text(cols1[1]) if len(cols1) > 1 else ['N/A']
                if len(court_auction_lines) >= 2:
                    court_name = court_auction_lines[0]  # 서울중앙지방법원
                    base_auction_no = court_auction_lines[1]  # 2025타경103083
                else:
                    court_name = court_auction_lines[0] if court_auction_lines else 'N/A'
                    base_auction_no = 'N/A'
                
                # Column 2: Item number (물건번호)
                item_number = safe_get_text(cols1[2]).strip() if len(cols1) > 2 else 'N/A'
                
                # Create complete auction number: base_auction_no + "-" + item_number
                if base_auction_no != 'N/A' and item_number != 'N/A':
                    auction_no = f"{base_auction_no}-{item_number}"
                else:
                    auction_no = base_auction_no if base_auction_no != 'N/A' else 'N/A'
                
                # Column 3: Car name/model
                car_name = safe_get_text(cols1[3]).strip() if len(cols1) > 3 else 'N/A'
                
                # Column 4: Additional car info (might contain year, type, etc.)
                car_info = safe_get_text(cols1[4]).strip() if len(cols1) > 4 else 'N/A'
                
                # Column 5: Appraisal value (감정가)
                appraisal_value = clean_number_text(safe_get_text(cols1[5])) if len(cols1) > 5 else 'N/A'
                
                # Column 6: Sale date info (format: 경매13계2025.09.24 or multiline format: 경매7계 \n 2025.09.18)  
                sale_date_raw = safe_get_text(cols1[6]) if len(cols1) > 6 else 'N/A'
                sale_date_multiline = safe_get_multiline_text(cols1[6]) if len(cols1) > 6 else ['N/A']
                
                # Try multiline parsing first, then fallback to single line
                if len(sale_date_multiline) > 1:
                    sale_date = parse_date_from_multiline(sale_date_multiline)
                else:
                    sale_date = parse_date_text(sale_date_raw)
                
                # Debug: Log sale date parsing for first few records
                if config.DEBUG and index < 3:
                    logger.info(f"Row {index} - sale_date_raw: '{sale_date_raw}', multiline: {sale_date_multiline} -> parsed: '{sale_date}'")
                
                # Row2 columns (additional info)
                # Column 1: Min bid price (최저매각가격)
                min_bid_price = clean_number_text(safe_get_text(cols2[1])) if len(cols2) > 1 else 'N/A'
                
                # Column 2: Sale result (multiline format: 매각 \n 26,580,000 or 유찰)
                sale_result_lines = safe_get_multiline_text(cols2[2]) if len(cols2) > 2 else ['N/A']
                sale_price = extract_sale_price_from_multiline(sale_result_lines)
                
                # Determine auction outcome from sale result
                if sale_result_lines and len(sale_result_lines) > 0:
                    first_line = sale_result_lines[0]
                    if '매각' in first_line:
                        auction_outcome = '매각'
                    elif '유찰' in first_line:
                        auction_outcome = '유찰'
                    else:
                        auction_outcome = first_line
                else:
                    auction_outcome = 'N/A'
                
                # Column 3: Bid rate or additional info
                bid_info = safe_get_text(cols2[3]).strip() if len(cols2) > 3 else 'N/A'
                
                # Try to parse bid rate from the bid_info or other sources
                bid_rate = parse_bid_rate(bid_info) if bid_info != 'N/A' else None

                # Extract year from car_info or car_name
                car_model_year = None
                car_type = car_info
                
                # Try to extract year (formats: 2020, '20, 20년, etc.)
                for text in [car_name, car_info]:
                    year_match = re.search(r'(\d{4})', text)
                    if year_match:
                        car_model_year = year_match.group(1)
                        break

                # Skip if we don't have essential data
                if not auction_no or auction_no == 'N/A':
                    logger.debug(f"Skipping row {index} - no auction number")
                    continue

                record = {
                    'auction_no': auction_no,
                    'court_name': court_name,
                    'car_name': car_name,
                    'car_model_year': car_model_year,
                    'car_type': car_type,
                    'appraisal_value': appraisal_value,
                    'min_bid_price': min_bid_price,
                    'sale_date': sale_date,
                    'sale_price': sale_price,
                    'bid_rate': bid_rate,
                    'auction_outcome': auction_outcome
                }
                
                results.append(record)
                logger.debug(f"Parsed record {len(results)}: {auction_no}")
                
                # Debug: Log full record data for first few records
                if config.DEBUG and len(results) <= 3:
                    logger.info(f"FULL RECORD {len(results)}: {record}")
                
            except Exception as col_e:
                logger.warning(f"Error parsing columns for row {index}: {col_e}")
                continue
                
        except Exception as row_e:
            logger.warning(f"Error processing row {index}: {row_e}")
            continue

    logger.info(f"Successfully parsed {len(results)} auction result records from HTML.")
    return results


def parse_detail_page(html: str, auction_no: str) -> Dict[str, str]:
    """
    Parse detailed auction information from a detail page.
    
    Args:
        html: The HTML content of the detail page
        auction_no: The auction number for reference
        
    Returns:
        Dictionary containing detailed auction information
    """
    soup = BeautifulSoup(html, 'html.parser')
    details = {'auction_no': auction_no}
    
    # This is a placeholder - implement based on actual detail page structure
    logger.debug(f"Parsing detail page for auction {auction_no}")
    
    # Add detail parsing logic here based on the actual HTML structure
    # of the auction detail pages
    
    return details