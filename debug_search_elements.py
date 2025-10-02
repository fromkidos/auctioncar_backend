import sys
import os
sys.stdout.reconfigure(encoding='utf-8')

# 경로 설정
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'crawling'))

def debug_search_elements():
    """검색 요소들 디버깅"""
    try:
        from crawling_auction_ongoing.driver_utils import initialize_driver
        from crawling_auction_ongoing.page_objects import AuctionListPage
        from crawling_auction_ongoing import config as crawler_config
        from selenium.webdriver.support.ui import WebDriverWait
        
        print("🔍 검색 요소들 디버깅 시작")
        
        # 드라이버 생성
        with initialize_driver() as driver:
            wait = WebDriverWait(driver, 10)
            
            # 경매 목록 페이지로 이동
            list_page = AuctionListPage(driver, wait)
            
            print("📄 페이지 초기화 시도...")
            if list_page.initialize_search():
                print("✅ 페이지 초기화 성공")
            else:
                print("❌ 페이지 초기화 실패")
                return False
            
            print("⏳ 그리드 로드 대기...")
            if list_page.wait_for_grid():
                print("✅ 그리드 로드 성공")
            else:
                print("❌ 그리드 로드 실패")
                return False
            
            # 검색 버튼 활성화
            try:
                search_button = driver.find_element("id", "mf_wfm_mainFrame_btn_search")
                driver.execute_script("arguments[0].style.display = 'block';", search_button)
                print("✅ 검색 버튼 활성화 완료")
            except Exception as e:
                print(f"❌ 검색 버튼 활성화 실패: {e}")
            
            # 검색 요소들 찾기
            print("\n🔍 검색 요소들 찾기:")
            
            # 1. 법원 선택 (이미 확인됨)
            try:
                court_select = driver.find_element("id", "mf_wfm_mainFrame_sbx_carTmidCortOfc")
                print(f"✅ 법원 선택: {court_select.get_attribute('id')}")
            except Exception as e:
                print(f"❌ 법원 선택 찾기 실패: {e}")
            
            # 2. 연도 선택 찾기
            year_selectors = [
                'select[id*="year"]',
                'select[name*="year"]', 
                'select[title*="연도"]',
                'select[id*="carTmid"]',
                'select[class*="w2selectbox"]'
            ]
            
            for selector in year_selectors:
                try:
                    year_select = driver.find_element("css selector", selector)
                    print(f"✅ 연도 선택 발견: {selector} -> {year_select.get_attribute('id')}")
                    break
                except:
                    continue
            else:
                print("❌ 연도 선택을 찾을 수 없음")
            
            # 3. 사건번호 입력 찾기
            case_selectors = [
                'input[id*="carTmidCsNo"]',
                'input[id*="caseNo"]',
                'input[placeholder*="사건번호"]',
                'input[title*="사건번호"]',
                'input[class*="w2textbox"]'
            ]
            
            for selector in case_selectors:
                try:
                    case_input = driver.find_element("css selector", selector)
                    print(f"✅ 사건번호 입력 발견: {selector} -> {case_input.get_attribute('id')}")
                    break
                except:
                    continue
            else:
                print("❌ 사건번호 입력을 찾을 수 없음")
            
            # 4. 모든 select 요소들 나열
            print("\n📋 모든 select 요소들:")
            try:
                selects = driver.find_elements("tag name", "select")
                for i, select in enumerate(selects):
                    select_id = select.get_attribute('id')
                    select_class = select.get_attribute('class')
                    select_title = select.get_attribute('title')
                    print(f"  {i+1}. ID: {select_id}, Class: {select_class}, Title: {select_title}")
            except Exception as e:
                print(f"❌ select 요소들 찾기 실패: {e}")
            
            # 5. 모든 input 요소들 나열
            print("\n📋 모든 input 요소들:")
            try:
                inputs = driver.find_elements("tag name", "input")
                for i, input_elem in enumerate(inputs):
                    input_id = input_elem.get_attribute('id')
                    input_type = input_elem.get_attribute('type')
                    input_placeholder = input_elem.get_attribute('placeholder')
                    input_title = input_elem.get_attribute('title')
                    if input_id and ('carTmid' in input_id or 'case' in input_id.lower() or 'year' in input_id.lower()):
                        print(f"  {i+1}. ID: {input_id}, Type: {input_type}, Placeholder: {input_placeholder}, Title: {input_title}")
            except Exception as e:
                print(f"❌ input 요소들 찾기 실패: {e}")
            
            print("\n🎉 검색 요소 디버깅 완료!")
            return True
            
    except Exception as e:
        print(f"❌ 디버깅 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = debug_search_elements()
    if success:
        print("✅ 검색 요소 디버깅 성공!")
    else:
        print("❌ 검색 요소 디버깅 실패!")
