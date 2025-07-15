import { Injectable } from '@nestjs/common';
import puppeteer from 'puppeteer';
import * as fs from 'fs';

@Injectable()
export class CrawlingService {
  /**
   * 카히스토리 홈페이지에서 로그인 → 차량조회 → 결과 HTML 반환 (puppeteer)
   */
  async crawlCarHistoryReport(
    carNumber: string,
    loginId: string,
    loginPw: string
  ): Promise<string | null> {
    const browser = await puppeteer.launch({ headless: true });
    const page = await browser.newPage();
    await page.setViewport({ width: 1920, height: 1080 });

    let loginFailed = false;
    let loginErrorThrown = false;
    page.on('dialog', async dialog => {
      console.log('[CrawlingService] 다이얼로그 감지:', dialog.message());
      if (dialog.message().includes('아이디') && dialog.message().includes('비밀번호')) {
        loginFailed = true;
        await dialog.dismiss();
        if (!loginErrorThrown) {
          loginErrorThrown = true;
          throw new Error('로그인에 실패했습니다. 아이디/비밀번호를 확인하세요.');
        }
      } else {
        await dialog.dismiss();
      }
    });

    // .tmp 폴더 생성
    if (!fs.existsSync('./.tmp')) {
      fs.mkdirSync('./.tmp', { recursive: true });
    }

    try {
      // 1) 로그인 페이지 이동
      await page.goto('https://www.carhistory.or.kr/login/login.car', { waitUntil: 'networkidle0' });

      // 2) 팝업/레이어 닫기 시도
      for (let i = 0; i < 3; i++) {
        try {
          const selectors = [
            '.fn-modal-close',
            '.fn-footer-btn.fn-right',
            '.modal .close',
            '.popup .close',
            '.layer .close',
            '.btn-close'
          ];
          let closed = false;
          for (const sel of selectors) {
            const btn = await page.$(sel);
            if (btn) {
              await btn.click();
              console.log(`[CrawlingService] 팝업 닫기 클릭: ${sel}`);
              // → waitForTimeout 대신 setTimeout 프로미스
              await new Promise(resolve => setTimeout(resolve, 500));
              closed = true;
              break;
            }
          }
          if (!closed) {
            await page.evaluate(() => {
              document
                .querySelectorAll('.modal, .popup, .layer, .fn-modal-overlay, .fn-modal-box')
                .forEach(el => (el as HTMLElement).style.display = 'none');
            });
            console.log('[CrawlingService] evaluate로 모든 팝업/모달 강제 닫기');
          }
          if (closed) break;
        } catch {
          console.info('[CrawlingService] 팝업 닫기 클릭 생략(팝업 없음)');
          await page.evaluate(() => {
            document
              .querySelectorAll('.modal, .popup, .layer, .fn-modal-overlay, .fn-modal-box')
              .forEach(el => (el as HTMLElement).style.display = 'none');
          });
          break;
        }
      }

      // 3) 로그인 처리
      if (await page.$('#id')) {
        await page.type('#id', loginId, { delay: 50 });
        await page.type('#pwd', loginPw, { delay: 50 });

        // doLogin() 호출 (Encrypt → form.submit)
        await Promise.all([
          page.waitForNavigation({ waitUntil: 'networkidle0', timeout: 15000 }),
          page.click('button[onClick="doLogin();"]')
        ]);

        // 로그인 폼이 남아 있으면 실패
        if (await page.$('#id')) {
          throw new Error('로그인에 실패했습니다. 아이디/비밀번호를 확인하세요.');
        }
        console.log('[CrawlingService] 로그인 성공');
      } else {
        console.log('[CrawlingService] 이미 로그인 상태');
      }

      // 4) 메인 페이지 이동
      await page.goto('https://www.carhistory.or.kr/main.car?lang=kr', { waitUntil: 'networkidle0' });
      console.log('[CrawlingService] 메인 페이지 이동 완료');
      await page.screenshot({ path: './.tmp/after_login.png' });

      // 5) 차량번호 입력 & 조회
      await page.waitForSelector('#carnum', { timeout: 10000 });
      await page.type('#carnum', carNumber, { delay: 50 });

      // 클릭과 로딩(waitUntil)을 동시에 대기
      await Promise.all([
        page.waitForNavigation({ waitUntil: 'networkidle2', timeout: 30000 }),
        page.click('#searchBtn'),
      ]);

      // 5-1) 결제 수단 선택 페이지에 왔는지 체크
      if (page.url().includes('/initSearch.car') || await page.$('.payment-method-wrap')) {
        // “무료조회” 버튼 클릭 (셀렉터는 실제 페이지에서 확인)
        await Promise.all([
          page.waitForNavigation({ waitUntil: 'networkidle2', timeout: 30000 }),
          page.click('button.free-service')  
        ]);
      }



      // 7) 결과 화면 로딩 대기
      await page.waitForSelector('.report-title-wrap', { timeout: 30000 });
      const htmlContent = await page.content();
      await page.screenshot({ path: './.tmp/after_search.png' });

      return htmlContent;
    } catch (e) {
      console.error('[CrawlingService] 크롤링 오류:', e);
      await page.screenshot({ path: './.tmp/crawling_error.png' });
      return null;
    } finally {
      await page.close();
      await browser.close();
    }
  }
}
