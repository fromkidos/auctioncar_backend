import time
import logging
from functools import wraps
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException, NoSuchElementException, ElementClickInterceptedException

logger = logging.getLogger(__name__)

DEFAULT_RETRY_EXCEPTIONS = (
    StaleElementReferenceException,
    TimeoutException,
    NoSuchElementException,
    ElementClickInterceptedException # 자주 발생하는 예외 추가
)

def retry(attempts=3, delay_seconds=1, backoff_factor=1, exceptions_to_catch=DEFAULT_RETRY_EXCEPTIONS, log_retry=True):
    """
    지정된 횟수만큼, 특정 예외 발생 시 작업을 재시도하는 데코레이터.

    Args:
        attempts (int): 최대 재시도 횟수.
        delay_seconds (float): 초기 재시도 간 지연 시간 (초).
        backoff_factor (float): 재시도 시 지연 시간에 적용할 백오프 계수. 
                                예를 들어 2이면 지연시간이 1, 2, 4... 로 늘어남.
        exceptions_to_catch (tuple): 재시도할 예외 유형들의 튜플.
        log_retry (bool): 재시도 시 로그 기록 여부.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay_seconds
            for attempt in range(1, attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions_to_catch as e:
                    if log_retry:
                        instance_str = ""
                        if args and hasattr(args[0], '__class__'):
                             instance_str = f" on instance of {args[0].__class__.__name__}"
                        
                        logger.warning(
                            f"Attempt {attempt}/{attempts} failed for {func.__name__}{instance_str} "
                            f"due to {type(e).__name__}: {str(e)}. Retrying in {current_delay:.2f}s..."
                        )
                    
                    if attempt == attempts:
                        logger.error(
                            f"All {attempts} attempts failed for {func.__name__}{instance_str} "
                            f"due to {type(e).__name__}: {str(e)}."
                        )
                        raise # 마지막 시도 실패 시 예외 다시 발생
                    
                    time.sleep(current_delay)
                    current_delay *= backoff_factor
        return wrapper
    return decorator 