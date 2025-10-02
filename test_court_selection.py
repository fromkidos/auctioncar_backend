import sys
import os
sys.stdout.reconfigure(encoding='utf-8')

# 경로 설정
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'crawling'))

def test_court_selection():
    """법원 선택 테스트"""
    try:
        from crawling_auction_ongoing.driver_utils import initialize_driver
        from crawling_auction_ongoing.page_objects import AuctionListPage
        from crawling_auction_ongoing import config as crawler_config
        from selenium.webdriver.support.ui import WebDriverWait, Select
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        
        print("🧪 법원 선택 테스트 시작")
        
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
            
            # 법원 선택 드롭다운 확인
            print("\n🔍 법원 선택 드롭다운 확인:")
            try:
                court_elem = driver.find_element(By.ID, crawler_config.COURT_SELECT_ID)
                select_obj = Select(court_elem)
                
                # 사용 가능한 옵션들 확인
                available_options = [option.text for option in select_obj.options]
                print(f"사용 가능한 법원 옵션들 ({len(available_options)}개):")
                for i, option in enumerate(available_options):
                    print(f"  {i+1}. {option}")
                
                # 현재 선택된 값 확인
                current_value = select_obj.first_selected_option.text
                print(f"\n현재 선택된 법원: {current_value}")
                
                # "고양지원" 찾기
                target_court = "고양지원"
                print(f"\n'{target_court}' 찾기:")
                
                found_exact = False
                found_partial = False
                
                for option in select_obj.options:
                    if option.text == target_court:
                        print(f"✅ 정확한 매칭 발견: {option.text}")
                        found_exact = True
                        break
                    elif target_court in option.text or option.text in target_court:
                        print(f"🔍 부분 매칭 발견: {option.text}")
                        found_partial = True
                
                if not found_exact and not found_partial:
                    print(f"❌ '{target_court}'을 찾을 수 없음")
                
                # 실제 선택 시도
                if found_exact or found_partial:
                    print(f"\n'{target_court}' 선택 시도:")
                    try:
                        select_obj.select_by_visible_text(target_court)
                        print(f"✅ 선택 성공: {target_court}")
                    except Exception as e:
                        print(f"❌ 선택 실패: {e}")
                        
                        # 부분 매칭으로 재시도
                        for option in select_obj.options:
                            if target_court in option.text:
                                try:
                                    select_obj.select_by_visible_text(option.text)
                                    print(f"✅ 부분 매칭으로 선택 성공: {option.text}")
                                    break
                                except Exception as e2:
                                    print(f"❌ 부분 매칭 선택도 실패: {e2}")
                
                # 선택 후 확인
                selected_value = select_obj.first_selected_option.text
                print(f"\n선택 후 현재 값: {selected_value}")
                
            except Exception as e:
                print(f"❌ 법원 선택 드롭다운 확인 실패: {e}")
                return False
            
            print("\n🎉 법원 선택 테스트 완료!")
            return True
            
    except Exception as e:
        print(f"❌ 법원 선택 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_court_selection()
    if success:
        print("✅ 법원 선택 테스트 성공!")
    else:
        print("❌ 법원 선택 테스트 실패!")
