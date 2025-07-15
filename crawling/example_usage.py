"""
환경변수 사용 예시
"""
# env_loader 모듈 임포트 (자동으로 .env 파일 로드됨)
from env_loader import (
    get_env, 
    get_database_url, 
    get_court_credentials,
    get_crawling_config
)

def example_usage():
    """환경변수 사용 예시"""
    
    print("=== 환경변수 사용 예시 ===")
    
    # 데이터베이스 URL
    db_url = get_database_url()
    print(f"Database URL: {db_url}")
    
    # 법원 사이트 로그인 정보
    login_id, login_password = get_court_credentials()
    print(f"Court Login ID: {login_id}")
    print(f"Court Password: {'*' * len(login_password) if login_password else 'Not set'}")
    
    # 크롤링 설정
    config = get_crawling_config()
    print(f"Crawling config: {config}")
    
    # 개별 환경변수
    node_env = get_env('NODE_ENV', 'development')
    print(f"NODE_ENV: {node_env}")
    
    # JWT Secret (마스킹)
    jwt_secret = get_env('JWT_SECRET', '')
    print(f"JWT Secret: {'*' * min(len(jwt_secret), 10) if jwt_secret else 'Not set'}")

if __name__ == "__main__":
    example_usage() 