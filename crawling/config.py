DETAIL_DATE_HISTORY_TABLE_SELECTOR = "table#mf_wfm_mainFrame_grd_dxdyDtsLst_body_table" # 기일내역 테이블 선택자 (tbody까지 포함)
DETAIL_SIMILAR_STATS_CONTENT_DIV_ID = "mf_wfm_mainFrame_tac_aroundGdsExm_contents_content1" # 유사매각통계 내용 div
DETAIL_SIMILAR_STATS_TABLE_ID = "mf_wfm_mainFrame_wq_uuid_779_body_table" # 유사매각통계 테이블 ID (tbody 아님)
DETAIL_APPRAISAL_SUMMARY_TEXTAREA_ID = "mf_wfm_mainFrame_txa_pgrKorRptCon" # 감정평가요항표 textarea ID (구)
DETAIL_APPRAISAL_SUMMARY_CONTAINER_SELECTOR = "div.w2textarea_content_container" # 감정평가요항표 내용 컨테이너 (신)
DETAIL_APPRAISAL_SUMMARY_MAIN_DIV_ID = "mf_wfm_mainFrame_wq_uuid_771" # 감정평가요항표 메인 div ID (신)

# 환경변수 로드
from env_loader import get_env, get_crawling_config, get_court_credentials

# 디버그 설정
DEBUG = get_env('DEBUG', 'True').lower() == 'true'

# 크롤링 설정
CRAWLING_CONFIG = get_crawling_config()
COURT_LOGIN_ID, COURT_LOGIN_PASSWORD = get_court_credentials()

# 헤더 텍스트 (실제 HTML과 일치해야 함)
HEADER_BASIC_INFO = "물건기본정보"
HEADER_CASE_INFO = "사건기본내역" # HTML 구조에 따라 실제 사용하는 텍스트로 변경 필요할 수 있음
HEADER_ITEM_DETAILS = "목록내역"
HEADER_DATE_HISTORY = "기일내역"
HEADER_APPRAISAL = "감정평가요항표 요약" # 경우에 따라 "1. 자동차감정평가요항표" 등 구체적인 텍스트 사용 고려
# HEADER_SIMILAR_SALE = "유사매각물건사례" # 현재는 테이블 ID로 직접 접근

# 감정평가요항표 요약 (AuctionAppraisalSummary) 테이블 관련 레이블
# 실제 웹사이트의 레이블과 정확히 일치해야 합니다.
LABEL_SUMMARY_HEADER = "감정평가요항표 요약"
LABEL_SUMMARY_YEAR_MILEAGE = "연식및주행거리" # 공백 제거된 형태 또는 실제 사이트의 정확한 레이블
LABEL_SUMMARY_COLOR = "색상"
LABEL_SUMMARY_MANAGEMENT_STATUS = "관리상태"
LABEL_SUMMARY_FUEL = "사용연료"
LABEL_SUMMARY_INSPECTION_VALIDITY = "검사유효기간"
LABEL_SUMMARY_OPTIONS_ETC = "기타사항" # 예시이며, 실제 사이트의 레이블 확인 필요 (예: "주요옵션 및 참고사항")

# 로그 관련 설정 