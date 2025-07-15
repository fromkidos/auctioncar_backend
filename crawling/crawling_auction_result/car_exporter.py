import json
import logging
import requests
from requests import Session
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, retry_if_result

from . import car_auction_config as config
from .. import db_manager # Assuming db_manager.py is in the same 'crawling' directory

logger = logging.getLogger(__name__)

# --- Global Requests Session ---
api_session = Session()

@retry(
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(3),
    retry=(retry_if_exception_type(requests.exceptions.RequestException) |
           retry_if_result(lambda response: response.status_code >= 500)),
    reraise=True
)
def insert_auction_result(record: dict) -> requests.Response:
    """Sends a single auction record to the NestJS API with retry logic and returns the Response object."""
    api_payload = {
        'auction_no': db_manager.clean_string(record.get('auction_no')),
        'car_name': db_manager.clean_string(record.get('car_name')),
        'car_model_year': db_manager.to_int_or_none(record.get('car_model_year'), field_name_for_logging='car_model_year_result'),
        'car_type': db_manager.clean_string(record.get('car_type')),
        'appraisal_value': db_manager.to_int_or_none(record.get('appraisal_value'), field_name_for_logging='appraisal_value_result'),
        'min_bid_price': db_manager.to_int_or_none(record.get('min_bid_price'), field_name_for_logging='min_bid_price_result'),
        'sale_price': db_manager.to_int_or_none(record.get('sale_price'), field_name_for_logging='sale_price_result'),
        'bid_rate': record.get('bid_rate'),
        'auction_outcome': db_manager.clean_string(record.get('auction_outcome'))
    }

    parsed_sale_date = db_manager.parse_custom_date(record.get('sale_date'))
    api_payload['sale_date'] = parsed_sale_date.strftime('%Y-%m-%d') if parsed_sale_date else None

    if not api_payload['auction_no']:
        logger.error(f"Error: auction_no is missing. Cannot send to API: {record}")
        raise ValueError(f"auction_no is missing in record: {record}")

    headers = {
        'Content-Type': 'application/json',
        'x-api-key': config.NESTJS_API_KEY
    }

    if not config.NESTJS_API_KEY:
        logger.warning("NESTJS_API_KEY is not set. API call will likely fail.")
        # Potentially return None or raise an error if the key is critical for all operations

    try:
        logger.info(f"Sending auction result for {api_payload['auction_no']} to API: {config.NESTJS_API_URL}")
        response = api_session.post(config.NESTJS_API_URL, headers=headers, data=json.dumps(api_payload, default=str), timeout=10)

        # Log based on status code, but return the full response object for tenacity and caller
        if response.ok: # response.ok checks for 2xx status codes
            logger.info(f"API call successful for {api_payload['auction_no']}. Status: {response.status_code}")
        else:
            logger.error(f"API call failed for {api_payload['auction_no']}. Status: {response.status_code}, Response: {response.text}")
        
        return response # 실제 Response 객체 반환

    except requests.exceptions.RequestException as e:
        logger.error(f"RequestException sending auction result for {api_payload['auction_no']} to API: {e}")
        raise # Reraise to be caught by tenacity
    except Exception as e:
        logger.error(f"An unexpected error occurred while sending data for {api_payload['auction_no']} to API: {e}", exc_info=True)
        # For unexpected errors not covered by RequestException, re-raise them so tenacity can handle if needed, or they propagate.
        # Alternatively, construct a mock Response object if a Response must always be returned, though re-raising is often cleaner.
        raise # Re-raise unexpected errors as well 