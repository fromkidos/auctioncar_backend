import { NestFactory } from '@nestjs/core';
import { AppModule } from '../app.module';
import { ScrapingService } from './scraping.service';
import * as fs from 'fs';

async function main() {
  const app = await NestFactory.createApplicationContext(AppModule);
  const scrapingService = app.get(ScrapingService);

  // 1. 샘플 HTML 저장
  const filePath = await scrapingService.fetchAndSaveSampleHtml();
  console.log('[테스트] 샘플 HTML 저장 경로:', filePath);

  // 2. HTML 파일 읽기
  const htmlContent = fs.readFileSync(filePath, 'utf-8');
  console.log('[테스트] HTML 파일 읽기 완료, 길이:', htmlContent.length);

  // 3. 파싱 및 DB 저장
  const result = await scrapingService.parseAuctionPageData(htmlContent, '2024타경116061-1');
  console.log('[테스트] 파싱 및 DB 저장 결과:', result);

  await app.close();
}

main();