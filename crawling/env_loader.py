"""
환경변수 로더 모듈
backend/.env 파일에서 환경변수를 로드합니다.
"""
import os
from pathlib import Path

def load_env_variables():
    """
    backend/.env 파일에서 환경변수를 로드합니다.
    python-dotenv가 없어도 작동하는 간단한 로더입니다.
    """
    # 현재 파일의 경로에서 backend 폴더의 .env 파일 경로 찾기
    current_dir = Path(__file__).parent  # crawling 폴더
    backend_dir = current_dir.parent     # backend 폴더
    env_file = backend_dir / '.env'
    
    if not env_file.exists():
        print(f"Warning: .env file not found at {env_file}")
        return {}
    
    env_vars = {}
    
    try:
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                
                # 빈 줄이나 주석 무시
                if not line or line.startswith('#'):
                    continue
                
                # KEY=VALUE 형태 파싱
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # 따옴표 제거
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]
                    
                    # 환경변수에 설정
                    os.environ[key] = value
                    env_vars[key] = value
        
        print(f"Loaded {len(env_vars)} environment variables from {env_file}")
        return env_vars
        
    except Exception as e:
        print(f"Error loading .env file: {e}")
        return {}

def get_env(key: str, default: str = None) -> str:
    """
    환경변수 값을 가져옵니다.
    
    Args:
        key: 환경변수 키
        default: 기본값
    
    Returns:
        환경변수 값 또는 기본값
    """
    return os.environ.get(key, default)

def get_database_url() -> str:
    """데이터베이스 URL을 가져옵니다."""
    return get_env('DATABASE_URL', 'postgresql://localhost:5432/courtauction_db')

def get_court_credentials() -> tuple:
    """법원 사이트 로그인 정보를 가져옵니다."""
    return (
        get_env('COURT_LOGIN_ID', ''),
        get_env('COURT_LOGIN_PASSWORD', '')
    )

def get_crawling_config() -> dict:
    """크롤링 설정을 가져옵니다."""
    return {
        'delay_ms': int(get_env('CRAWLING_DELAY_MS', '2000')),
        'max_retry': int(get_env('MAX_RETRY_COUNT', '3')),
        'headless': get_env('HEADLESS_MODE', 'true').lower() == 'true'
    }

# 모듈 임포트 시 자동으로 환경변수 로드
if __name__ != '__main__':
    load_env_variables() 