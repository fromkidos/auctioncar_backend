import re
import logging
from decimal import Decimal, InvalidOperation
from bs4 import BeautifulSoup, Tag
import os

from . import car_auction_config as config

logger = logging.getLogger(__name__)

# ---------------------------------------
# 내부 유틸
# ---------------------------------------
_NUM_EXTRACT_RE = re.compile(r'[\d,]+')

def _as_text(node, sep=" ", strip=True) -> str:
    """모든 하위 텍스트를 안전하게 결합해서 반환."""
    if not node:
        return ""
    try:
        return node.get_text(sep=sep, strip=strip)
    except Exception:
        return str(node).strip()

def _digits_only(s: str) -> str:
    """문자열에서 숫자/쉼표만 추려 반환."""
    if not s:
        return ""
    m = _NUM_EXTRACT_RE.search(s)
    return (m.group(0) if m else "").replace(",", "")

def _extract_after_br_text(container: Tag) -> str:
    """
    div 등 컨테이너에서 <br> 다음에 오는 '텍스트 노드'를 우선 추출.
    없으면 전체 텍스트 중 날짜/금액 패턴 추정치 반환.
    """
    if not container:
        return ""
    try:
        br = container.find("br")
        if br and isinstance(br.next_sibling, str):
            cand = br.next_sibling.strip()
            if cand:
                return cand
        # fallback: 전체 텍스트
        return _as_text(container)
    except Exception:
        return _as_text(container)

# ---------------------------------------
# 메인 파서
# ---------------------------------------
def parse_list(html: str) -> list[dict]:
    """
    Parse the listing grid and extract auction info based on a structural row pattern.
    Robust to row1/row2 열 개수(3/7, 7/3) 뒤바뀜. 블록 내에서 '넓은 행(>=7 td)'과
    '좁은 행(>=3 td)'을 찾아 매핑.
    Extracts: auction_no, car_name, car_model_year, car_type, appraisal_value,
              min_bid_price, sale_date, sale_price, bid_rate, auction_outcome.
    """
    soup = BeautifulSoup(html, 'html.parser')
    grid_body = soup.select_one(f'tbody#{config.RESULTS_GRID_BODY_ID}')
    if not grid_body:
        logger.warning("Results grid body not found in HTML.")
        return []

    all_trs = grid_body.find_all('tr', recursive=False)
    results = []
    logger.debug(f"Found {len(all_trs)} total TRs in the grid body for structural parsing.")

    ITEM_BLOCK_SIZE = 5  # 사이트가 한 아이템을 5개의 TR 블록으로 구성한다고 가정
    i = 0

    while i < len(all_trs):
        BLOCK = all_trs[i:i + ITEM_BLOCK_SIZE]
        if not BLOCK:
            break

        # 블록 내에서 후보 행 수집
        candidates = [(idx, tr, tr.select('td')) for idx, tr in enumerate(BLOCK)]
        # 넓은 행(상세)은 td가 가장 많은 행, 좁은 행(요약)은 그 외에서 td>=3
        try:
            wide = max(candidates, key=lambda x: len(x[2]))  # (idx, tr, cols)
        except ValueError:
            # 빈 블록 등
            wide = None

        narrow = None
        if wide:
            for c in candidates:
                if c is wide:
                    continue
                if len(c[2]) >= 3:
                    narrow = c
                    break

        # 정규화(항상 cols1=넓은 행(>=7), cols2=좁은 행(>=3))
        if not wide or len(wide[2]) < 7 or not narrow:
            logger.warning(
                f"Unexpected block structure at TR base index {i}: "
                f"block_len={len(BLOCK)}, "
                f"cols_counts={[len(c[2]) for c in candidates]}"
            )
            if getattr(config, "DEBUG", False):
                try:
                    os.makedirs(config.DEBUG_DIR, exist_ok=True)
                    filename = f"parser_unexpected_block_tr_base_{i}.html"
                    full_path = os.path.join(config.DEBUG_DIR, filename)
                    with open(full_path, "w", encoding="utf-8") as f_debug:
                        f_debug.write(html)
                    logger.info(f"[DEBUG] Saved HTML due to unexpected block to: {full_path}")
                except Exception as e_save:
                    logger.error(f"Failed to save debug HTML: {e_save}")
            i += ITEM_BLOCK_SIZE
            continue

        row1, cols1 = wide[1], wide[2]   # 상세(>=7칸)
        row2, cols2 = narrow[1], narrow[2]  # 요약(>=3칸)

        auction_no = "UNKNOWN_AUCTION_NO"  # 기본값
        try:
            # -----------------------------
            # 1) 사건번호/물건번호 (cols1[1], cols1[2] 기준)
            # -----------------------------
            case_no_text = _as_text(cols1[1]) if len(cols1) > 1 else "N/A"
            item_no_text = _as_text(cols1[2]) if len(cols1) > 2 else "N/A"
            item_no_text = item_no_text.strip()
            auction_no = f"{case_no_text}-{item_no_text}" if case_no_text != "N/A" else f"N/A-{item_no_text}"

            # -----------------------------
            # 2) 제목/차명/연식/차종 (cols1[3]의 div에서 title-like 텍스트 추정)
            # -----------------------------
            raw_title_text = "N/A"
            location_desc_div = cols1[3].select_one('div') if len(cols1) > 3 else None
            if location_desc_div:
                # br 다음 텍스트 우선, 없으면 전체 텍스트
                raw_title_text = _extract_after_br_text(location_desc_div) or "N/A"
            else:
                raw_title_text = _as_text(cols1[3]) if len(cols1) > 3 else "N/A"

            car_name = None
            car_model_year = None
            car_type = None

            if raw_title_text and raw_title_text != "N/A":
                # "[모델명 2019 년식 XXX]" 등 패턴 우선 시도
                match_name_year = re.search(
                    r"(?P<name_year_group>\[?(?P<name>.*?)\s+(?P<year>\d{4})\s*년식\s*)",
                    raw_title_text
                )
                if match_name_year:
                    car_name = match_name_year.group('name').strip()
                    # 괄호 내용 제거
                    car_name = re.sub(r'\s*\(.*?\)\s*', '', car_name).strip()
                    try:
                        car_model_year = int(match_name_year.group('year'))
                    except ValueError:
                        car_model_year = None

                    # 남은 꼬리 텍스트를 차종 후보로
                    name_year_end_pos = match_name_year.end('name_year_group')
                    potential_car_type = raw_title_text[name_year_end_pos:].strip()
                    if potential_car_type:
                        car_type = potential_car_type[:-1].strip() if potential_car_type.endswith(']') else potential_car_type
                        car_type = car_type or None
                else:
                    # 연식 패턴 없으면 제목에서 괄호 제거 후 이름만
                    car_name = re.sub(r'\s*\(.*?\)\s*', '', raw_title_text.strip("[] ")).strip()

            # -----------------------------
            # 3) 감정가, 매각기일 (cols1[5], cols1[6] 기준)
            # -----------------------------
            appraisal_value_str = _digits_only(_as_text(cols1[5])) if len(cols1) > 5 else ""
            sale_date_text = "N/A"
            dept_div = cols1[6].select_one('div') if len(cols1) > 6 else None
            if dept_div:
                # 보통 "부서명\nYYYY.MM.DD" 형태라면 '.'이 2번 이상
                cand = _extract_after_br_text(dept_div)
                if cand and cand.count('.') >= 2:
                    sale_date_text = cand.strip()
                else:
                    # 전체에서 날짜 추정
                    txt = _as_text(dept_div)
                    sale_date_text = txt if txt.count('.') >= 2 else "N/A"
            else:
                # div가 없으면 칸 전체에서 추정
                txt = _as_text(cols1[6]) if len(cols1) > 6 else ""
                sale_date_text = txt if txt.count('.') >= 2 else "N/A"

            # -----------------------------
            # 4) 용도/최저가/결과+낙찰가 (cols2[0], cols2[1], cols2[2])
            # -----------------------------
            usage_text = _as_text(cols2[0]) if len(cols2) > 0 else "N/A"
            min_bid_price_str = _digits_only(_as_text(cols2[1])) if len(cols2) > 1 else ""

            result_status_text = "N/A"
            sale_price_str = ""

            if len(cols2) > 2:
                result_cell = cols2[2]
                nobr = result_cell.select_one('nobr')
                if nobr:
                    contents = list(nobr.contents)
                    txt_all = nobr.get_text(strip=False)
                    if contents:
                        if isinstance(contents[0], str) and contents[0].strip():
                            result_status_text = contents[0].strip()
                        else:
                            # 첫 단어를 상태로 추정
                            words = _as_text(nobr).split()
                            result_status_text = words[0] if words else "N/A"

                        # "상태<br>123,456" 패턴
                        if len(contents) > 2 and isinstance(contents[1], Tag) and contents[1].name == 'br' and isinstance(contents[2], str):
                            sale_price_str = _digits_only(contents[2])
                        else:
                            # 상태를 제거한 나머지에서 금액 추정
                            if result_status_text != '유찰':
                                dm = _NUM_EXTRACT_RE.search(txt_all.replace(result_status_text, '', 1))
                                sale_price_str = (dm.group(0).replace(',', '') if dm else "")
                else:
                    # nobr가 없을 때: "상태 123,456" 패턴
                    fallback_text = _as_text(result_cell)
                    parts = fallback_text.split()
                    result_status_text = parts[0] if parts else "N/A"
                    if len(parts) > 1:
                        sale_price_str = _digits_only(parts[1])

            # 차종 보정(미지정일 때 용도 기준 추정)
            if car_type is None:
                ut = usage_text
                if ut and ut != 'N/A':
                    if "승용차" in ut:
                        car_type = "승용차"
                    elif "화물차" in ut:
                        car_type = "화물차"
                    elif "승합차" in ut:
                        car_type = "승합차"
                    elif "버스" in ut:
                        car_type = "버스"
                    elif "중기" in ut or "건설기계" in ut:
                        car_type = "건설기계"
                    elif "특수차" in ut:
                        car_type = "특수차"
                    elif "기타차량" in ut:
                        car_type = "기타차량"
                    elif ut == '자동차':
                        if car_name and any(kw in car_name.lower() for kw in ['트럭', '포터', '봉고', '카고', '탑차']):
                            car_type = "화물차"
                        else:
                            car_type = "승용차"
                    elif len(ut) > 1:
                        car_type = ut
                    else:
                        car_type = "기타"
            if car_type is None:
                car_type = "기타"

            # -----------------------------
            # 5) 낙찰율
            # -----------------------------
            bid_rate = None
            try:
                app_val = Decimal(appraisal_value_str) if appraisal_value_str else Decimal('0')
                s_price = Decimal(sale_price_str) if sale_price_str else None
                if s_price is not None and app_val > 0:
                    bid_rate = round((s_price / app_val) * Decimal('100'), 2)
                elif result_status_text == '매각' and s_price is None and getattr(config, "DEBUG", False):
                    logger.debug(f"DEBUG_BID_RATE: Auction No: {auction_no}, Marked '매각' but no sale price. Bid rate None.")
            except InvalidOperation:
                if getattr(config, "DEBUG", False):
                    logger.debug(f"DEBUG_BID_RATE: Auction No: {auction_no}, Decimal conversion error for bid_rate. Bid rate None.")
            except Exception as e_br:
                if getattr(config, "DEBUG", False):
                    logger.debug(f"DEBUG_BID_RATE: Auction No: {auction_no}, Error calculating bid rate: {e_br}. Bid rate None.")

            results.append({
                'auction_no': auction_no,
                'car_name': car_name,
                'car_model_year': int(car_model_year) if isinstance(car_model_year, int) else None,
                'car_type': car_type,
                'appraisal_value': appraisal_value_str,           # 문자열(정수형 문자열)
                'min_bid_price': min_bid_price_str,               # 문자열(정수형 문자열)
                'sale_date': sale_date_text,                      # 예: '2025.09.23'
                'sale_price': sale_price_str or None,             # 문자열(정수형 문자열) 또는 None
                'bid_rate': float(bid_rate) if bid_rate is not None else None,
                'auction_outcome': result_status_text
            })

        except (AttributeError, IndexError, TypeError) as e:
            logger.error(f"Error parsing a block (base TR index {i}) for auction {auction_no}: {e}. Skipping.", exc_info=True)
            if getattr(config, "DEBUG", False):
                try:
                    os.makedirs(config.DEBUG_DIR, exist_ok=True)
                    filename_err = f"parser_error_tr_base_{i}_auction_no_{auction_no.replace('/', '_').replace(':', '_')}.html"
                    full_path_err = os.path.join(config.DEBUG_DIR, filename_err)
                    with open(full_path_err, "w", encoding="utf-8") as f_debug_err:
                        f_debug_err.write(html)
                    logger.info(f"Saved HTML due to parsing error to: {full_path_err}")
                except Exception as e_save_err:
                    logger.error(f"Failed to save debug HTML (on error) to {full_path_err}: {e_save_err}")

        # 다음 블록으로
        i += ITEM_BLOCK_SIZE

    return results
