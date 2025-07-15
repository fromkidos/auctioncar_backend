// src/scraping/scraping.service.ts (일부)
import { Injectable } from '@nestjs/common';
import * as cheerio from 'cheerio';
import axios from 'axios';
import * as fs from 'fs';
import * as path from 'path';
import { PrismaService } from '../prisma/prisma.service';
import { CrawlingService } from './crawling.service';

@Injectable()
export class ScrapingService {
  constructor(
    private readonly prisma: PrismaService,
    private readonly crawlingService: CrawlingService,
  ) {}

  async fetchAndSaveSampleHtml(): Promise<string> {
    console.log('[ScrapingService] fetchAndSaveSampleHtml called');
    try {
      const response = await axios.get('https://www.carhistory.or.kr/guide/sample.page');
      const htmlContent = response.data;
      console.log(`[ScrapingService] fetchAndSaveSampleHtml: HTML content length: ${htmlContent.length}`);
      
      const tmpDir = path.join(__dirname, '..', '..', '.tmp');
      if (!fs.existsSync(tmpDir)) {
        fs.mkdirSync(tmpDir, { recursive: true });
        console.log(`[ScrapingService] fetchAndSaveSampleHtml: Created temporary directory at ${tmpDir}`);
      }
      const filePath = path.join(tmpDir, 'carhistory_sample.html');
      
      fs.writeFileSync(filePath, htmlContent);
      console.log(`[ScrapingService] fetchAndSaveSampleHtml: Saved HTML to ${filePath}`);
      
      return filePath;
    } catch (error) {
      console.error('[ScrapingService] fetchAndSaveSampleHtml Error:', error);
      throw error;
    }
  }

  async parseAuctionPageData(htmlContent: string, auctionNo: string) {
    console.log(`[ScrapingService] parseAuctionPageData called: auctionNo=${auctionNo}, html length=${htmlContent.length}`);
    const $ = cheerio.load(htmlContent);
    
    try {
      // 기본 정보 파싱
      const titleText = $('.report-title-wrap .h4').text().trim();
      const [modelName, vehicleNumber] = titleText.split('/').map(s => s.trim());
      const reportDateText = $('.report-title-wrap .h5').text().trim();
      const reportDate = reportDateText.replace('정보조회일자 :', '').trim();

      // 차량 기본 사양 정보 파싱 (#report2)
      const specs = this.parseVehicleSpecs($);

      // 사고이력 요약 정보 파싱
      const accidentHistory = this.parseAccidentHistory($);

      // 보험이력 정보 파싱
      const insuranceHistory = this.parseInsuranceHistory($);

      // 정비이력 정보 파싱
      const maintenanceHistory = this.parseMaintenanceHistory($);

      // 종합 평가 정보 파싱
      const overallEvaluation = this.parseOverallEvaluation($);

      // 첨단 안전 장치 정보 파싱
      const safetyFeatures = this.parseSafetyFeatures($);

      // 특수 용도 이력 정보 파싱
      const specialUsage = this.parseSpecialUsageHistory($);

      const specialAccidents = this.parseSpecialAccidents($);

      const ownerAndNumberChanges = this.parseOwnerAndNumberChanges($);

      const insuranceAccidentsDetails = this.parseInsuranceAccidentsDetails($);

      const mileageHistory = this.parseMileageHistory($);

      const vehicleValueRange = this.parseVehicleValueRange($);

      const vehiclePredictedPrice = this.parseVehiclePredictedPrice($);

      const reportData = {
        auction_no: auctionNo,
        car_reg_number: vehicleNumber || '',
        crawledAt: new Date(),
        reportQueryDate: reportDate || null,
        manufacturer: specs.manufacturer || null,
        modelYear: specs.modelYear || null,
        displacement: specs.engineDisplacement || null,
        fuelType: specs.fuelType || null,
        bodyType: specs.bodyType || null,
        usageAndVehicleType: specs.usageType || null,
        detailModelName: specs.detailedModel || null,
        firstInsuranceDate: specs.firstInsuranceDate || null,

        // 사고이력 요약
        summaryTotalLossCount: accidentHistory.total_loss,
        summaryTheftCount: accidentHistory.theft,
        summaryFloodDamage: accidentHistory.flood ? "있음" : "없음",
        summarySpecialUseHistory: accidentHistory.special_use ? "있음" : "없음",
        summaryMyCarDamageCount: accidentHistory.self_damage_count,
        summaryMyCarDamageAmount: accidentHistory.self_damage_amount,
        summaryOtherCarDamageCount: accidentHistory.other_damage_count,
        summaryOtherCarDamageAmount: accidentHistory.other_damage_amount,
        summaryOwnerChangeCount: accidentHistory.ownership_changes,
        summaryNumberChangeHistory: accidentHistory.number_changes ? "있음" : "없음",

        // 보험/정비/주행거리 등 JSON 필드
        insuranceAccidentsDetailsJson: insuranceAccidentsDetails,
        mileageHistoryJson: mileageHistory,
        vehicleValueRangeMin: vehicleValueRange?.min ?? undefined,
        vehicleValueRangeMax: vehicleValueRange?.max ?? undefined,

        // 첨단 안전 장치 정보
        safetyFeaturesJson: safetyFeatures ?? undefined,

        // 특수 용도 이력 정보
        specialUsageRentalHistory: specialUsage.rental ?? undefined,
        specialUsageBusinessUseHistory: specialUsage.business ?? undefined,
        specialUsageGovernmentUseHistory: specialUsage.government ?? undefined,

        // 소유자 및 차량번호 변경 이력 정보
        ownerAndNumberChangesJson: ownerAndNumberChanges,

        // 특수사고 이력 정보
        specialAccidentsTotalLossDate: specialAccidents.totalLossDate ?? undefined,
        specialAccidentsTheftDate: specialAccidents.theftDate ?? undefined,
        specialAccidentsFloodDamageDate: specialAccidents.floodDamageDate ?? undefined,

        // 차량예측시세 정보
        vehiclePredictedPriceJson: vehiclePredictedPrice ?? undefined,

        // 기타 필요한 필드도 동일하게 추가
      };

      // 데이터베이스에 저장
      const savedReport = await this.prisma.vehicleComprehensiveReport.upsert({
        where: { auction_no: auctionNo },
        update: reportData,
        create: reportData,
      });
      
      console.log(`[ScrapingService] Successfully saved report for auction ${auctionNo}`);
      return savedReport;
    } catch (error) {
      console.error(`[ScrapingService] Error parsing/saving data for auction ${auctionNo}:`, error);
      return null;
    }
  }

  private parseVehicleSpecs($) {
    const specs: {
      manufacturer: string | null,
      modelYear: number | null,
      engineDisplacement: string | null,
      fuelType: string | null,
      bodyType: string | null,
      usageType: string | null,
      detailedModel: string | null,
      firstInsuranceDate: string | null
    } = {
      manufacturer: null,
      modelYear: null,
      engineDisplacement: null,
      fuelType: null,
      bodyType: null,
      usageType: null,
      detailedModel: null,
      firstInsuranceDate: null
    };

    // 좌측 테이블 파싱
    $('#report2 .col-md-6:first-child .report-table tbody tr').each((_, tr) => {
      const $tr = $(tr);
      const label = $tr.find('th').text().trim();
      const value = $tr.find('td').text().trim();

      switch (label) {
        case '제조사':
          specs.manufacturer = value;
          break;
        case '배기량':
          specs.engineDisplacement = value;
          break;
        case '사용연료':
          specs.fuelType = value;
          break;
        case '세부모델':
          specs.detailedModel = value;
          break;
      }
    });

    // 우측 테이블 파싱
    $('#report2 .col-md-6:last-child .report-table tbody tr').each((_, tr) => {
      const $tr = $(tr);
      const label = $tr.find('th').text().trim();
      const value = $tr.find('td').text().trim();

      switch (label) {
        case '연식(Model year)':
          specs.modelYear = parseInt(value, 10);
          break;
        case '차체형상':
          specs.bodyType = value;
          break;
        case '용도 및 차종':
          specs.usageType = value;
          break;
        case '최초 보험 가입일자':
          specs.firstInsuranceDate = value;
          break;
      }
    });

    return specs;
  }

  private parseAccidentHistory($) {
    const summary = {
      total_loss: 0,
      theft: 0,
      flood: false,
      special_use: false,
      self_damage_count: 0,
      self_damage_amount: 0,
      other_damage_count: 0,
      other_damage_amount: 0,
      ownership_changes: 0,
      number_changes: false
    };

    // 사고이력 요약 정보 파싱
    $('#report1 .result-summary .icon-text-container').each((_, container) => {
      const $container = $(container);
      const label = $container.find('span').text().trim();
      const value = $container.find('.price strong').text().trim();

      switch (label) {
        case '전손 보험사고':
          summary.total_loss = value === '없음' ? 0 : parseInt(value, 10);
          break;
        case '도난 보험사고':
          summary.theft = value === '없음' ? 0 : parseInt(value, 10);
          break;
        case '침수 보험사고':
          summary.flood = value === '있음';
          break;
        case '특수 용도 이력':
          summary.special_use = value === '있음';
          break;
        case '내차 피해': {
          const matches = value.match(/(\d+)회 \((\d+(?:,\d+)*)원\)/);
          if (matches) {
            summary.self_damage_count = parseInt(matches[1], 10);
            summary.self_damage_amount = parseInt(matches[2].replace(/,/g, ''), 10);
          }
          break;
        }
        case '상대차 피해': {
          const matches = value.match(/(\d+)회 \((\d+(?:,\d+)*)원\)/);
          if (matches) {
            summary.other_damage_count = parseInt(matches[1], 10);
            summary.other_damage_amount = parseInt(matches[2].replace(/,/g, ''), 10);
          }
          break;
        }
        case '소유자 변경':
          summary.ownership_changes = value === '없음' ? 0 : parseInt(value, 10);
          break;
        case '차량번호 변경':
          summary.number_changes = value === '있음';
          break;
      }
    });

    return summary;
  }

  private parseInsuranceHistory($) {
    // 보험 이력 정보 파싱 로직
    const insuranceRecords = $('#report6 .insurance-history').map((_, el) => {
      const $el = $(el);
      return {
        period: $el.find('.period').text().trim(),
        company: $el.find('.company').text().trim(),
        type: $el.find('.type').text().trim()
      };
    }).get();

    return {
      insurance_records: insuranceRecords.length > 0 ? JSON.stringify(insuranceRecords) : null
    };
  }

  private parseMaintenanceHistory($) {
    // 정비 이력 정보 파싱 로직
    const maintenanceRecords = $('#report7 .maintenance-history').map((_, el) => {
      const $el = $(el);
      return {
        date: $el.find('.date').text().trim(),
        mileage: $el.find('.mileage').text().trim(),
        details: $el.find('.details').text().trim()
      };
    }).get();

    return {
      maintenance_records: maintenanceRecords.length > 0 ? JSON.stringify(maintenanceRecords) : null
    };
  }

  private parseOverallEvaluation($) {
    // 종합 평가 정보 파싱 로직
    const evaluationPoints = $('.evaluation-points').map((_, el) => {
      const $el = $(el);
      return {
        category: $el.find('.category').text().trim(),
        score: parseInt($el.find('.score').text().trim(), 10) || 0,
        description: $el.find('.description').text().trim()
      };
    }).get();

    return {
      evaluation_summary: evaluationPoints.length > 0 ? JSON.stringify(evaluationPoints) : null
    };
  }

  private parseSafetyFeatures($): Record<string, string> | null {
    const features: Record<string, string> = {};

    // 모든 report-table2 테이블의 tbody > tr 순회
    $('.report-table2 tbody tr').each((_, tr) => {
      const $tr = $(tr);
      const name = $tr.find('th.textTh').text().trim();
      const value = $tr.find('td').text().trim();
      if (name && value) {
        features[name] = value;
      }
    });

    // 마지막 table의 tbody 바깥에 tr이 있는 경우도 처리
    $('.report-table2 > tr').each((_, tr) => {
      const $tr = $(tr);
      const name = $tr.find('th.textTh').text().trim();
      const value = $tr.find('td').text().trim();
      if (name && value) {
        features[name] = value;
      }
    });

    return Object.keys(features).length > 0 ? features : null;
  }

  private parseSpecialUsageHistory($): {
    rental: string | null,
    business: string | null,
    government: string | null
  } {
    // collapse-area > #report3 내부의 .icon-text-container를 순회
    const result = {
      rental: null,
      business: null,
      government: null
    };

    $('#report3 .icon-text-container').each((_, el) => {
      const $el = $(el);
      const label = $el.find('span').text().trim();
      const value = $el.find('.price strong').text().trim();

      if (label.includes('대여용도')) {
        result.rental = value;
      } else if (label.includes('영업용도')) {
        result.business = value;
      } else if (label.includes('관용용도')) {
        result.government = value;
      }
    });

    return result;
  }

  private parseOwnerAndNumberChanges($): any[] | undefined {
    const changes: any[] = [];

    // #report4 내부의 .tb-body.tb-row를 순회
    $('#report4 .tb-body.tb-row').each((_, el) => {
      const $el = $(el);
      const tds = $el.find('.td');
      // 순서: 0=날짜, 1=소유자변경, 2=차량번호, 3=차량용도
      changes.push({
        changeDate: tds.eq(0).text().trim(),
        ownerChanged: tds.eq(1).text().trim(),
        vehicleNumber: tds.eq(2).text().trim(),
        vehicleUse: tds.eq(3).text().trim(),
      });
    });

    return changes.length > 0 ? changes : undefined;
  }

  private parseSpecialAccidents($): {
    totalLossDate: string | undefined,
    theftDate: string | undefined,
    floodDamageDate: string | undefined
  } {
    let totalLossDate: string | undefined;
    let theftDate: string | undefined;
    let floodDamageDate: string | undefined;

    $('#report5 .icon-text-container').each((_, el) => {
      const $el = $(el);
      const label = $el.find('span').text().trim();
      const value = $el.find('.price strong').text().trim();

      if (label.includes('전손')) {
        totalLossDate = value;
      } else if (label.includes('도난')) {
        theftDate = value;
      } else if (label.includes('침수')) {
        floodDamageDate = value;
      }
    });

    return {
      totalLossDate,
      theftDate,
      floodDamageDate
    };
  }

  private parseInsuranceAccidentsDetails($): any[] | undefined {
    const details: any[] = [];

    // #report6의 사고 리스트(li) 순회
    $('#report6 .crash-info-list').each((_, el) => {
      const $el = $(el);

      // 1. 사고 일자
      const date = $el.find('.date .color-key').first().text().trim();

      // 2. 내 차 사고/상대 차 사고 구분
      const myCarTable = $el.find('.col-md-6 table.report-table').first();
      const otherCarTable = $el.find('.col-md-4 table.report-table').first();

      // 3. 내 차 보험 정보
      let myCarType = null, myCarStatus = null, myCarInsurancePayment: number | null = null, myCarRepairCost: number | null = null, myCarRepairBreakdown: { parts?: number; labor?: number; paint?: number } = {}, myCarBadge = null;
      if (myCarTable.length) {
        const myCarTd = myCarTable.find('tbody td').first();
        // 보험유형(전손/도난 등)
        myCarBadge = myCarTd.find('.badge').text().trim() || null;
        // 보험금
        const insurancePaymentText = myCarTd.find('.color-key').first().text().replace(/[^0-9]/g, '');
        myCarInsurancePayment = insurancePaymentText ? parseInt(insurancePaymentText, 10) : null;
        // 수리비 breakdown
        const repairCostMatch = myCarTd.html()?.match(/수리\(견적\)비용.*?([0-9,]+)원/);
        if (repairCostMatch) {
          myCarRepairCost = parseInt(repairCostMatch[1].replace(/,/g, ''), 10);
        }
        // breakdown(부품, 공임, 도장)
        const partsMatch = myCarTd.html()?.match(/부품\s*:\s*([0-9,]+)원/);
        const laborMatch = myCarTd.html()?.match(/공임\s*:\s*([0-9,]+)원/);
        const paintMatch = myCarTd.html()?.match(/도장\s*:\s*([0-9,]+)원/);
        if (partsMatch) myCarRepairBreakdown.parts = parseInt(partsMatch[1].replace(/,/g, ''), 10);
        if (laborMatch) myCarRepairBreakdown.labor = parseInt(laborMatch[1].replace(/,/g, ''), 10);
        if (paintMatch) myCarRepairBreakdown.paint = parseInt(paintMatch[1].replace(/,/g, ''), 10);
      }

      // 4. 상대 차 보험 정보
      let otherCarInsurancePayment: number | null = null;
      if (otherCarTable.length) {
        const otherCarTd = otherCarTable.find('tbody td').first();
        const otherInsurancePaymentText = otherCarTd.find('.color-green').first().text().replace(/[^0-9]/g, '');
        otherCarInsurancePayment = otherInsurancePaymentText ? parseInt(otherInsurancePaymentText, 10) : null;
      }

      // 5. 손상부위(수리부위)
      // (이 부분은 별도 테이블에서 label만 추출)
      // 예시: #repairAll, 혹은 사고별 상세 모달에서 추출 필요

      details.push({
        accidentDate: date,
        type: myCarBadge, // 전손/도난/침수 등
        insurancePayment: myCarInsurancePayment,
        repairCost: myCarRepairCost,
        repairBreakdown: myCarRepairBreakdown,
        otherCarInsurancePayment,
        // damagedParts: [...], // 필요시 추가 구현
      });
    });

    return details.length > 0 ? details : undefined;
  }

  private parseMileageHistory($): any[] | undefined {
    const history: any[] = [];

    // #report7의 .responsive-table > .tb-body.tb-row 순회
    $('#report7 .responsive-table .tb-body.tb-row').each((_, el) => {
      const $el = $(el);
      const tds = $el.find('.td');
      // 순서: 0=날짜, 1=주행거리, 2=제공처
      history.push({
        inspectionDate: tds.eq(0).text().trim().replace(/\./g, '-').replace(/\//g, '-'),
        mileage: tds.eq(1).text().replace(/[^0-9]/g, ''), // 숫자만 추출
        provider: tds.eq(2).text().trim(),
      });
    });

    return history.length > 0 ? history : undefined;
  }

  private parseVehicleValueRange($): { min: number | null, max: number | null } | undefined {
    // #report8의 차량가액 범위 텍스트 추출
    const valueText = $('#report8 .td strong').first().text().replace(/[^\d~]/g, '').trim();
    // 예: "2256~2886"
    if (valueText) {
      const [minStr, maxStr] = valueText.split('~').map(s => s.trim());
      const min = minStr ? parseInt(minStr, 10) : null;
      const max = maxStr ? parseInt(maxStr, 10) : null;
      return { min, max };
    }
    return undefined;
  }

  private parseVehiclePredictedPrice($): Record<string, any> | undefined {
    // #report9 내부의 표준시세, 개별시세, 1년후 시세 등 추출
    const result: Record<string, any> = {};

    // 표준 시세 (예: "2,256~2,886 만원")
    const stdPriceText = $('#report9 .responsive-table2 .tb-head.tb-row').eq(0).find('.td').text().replace(/[^\d~]/g, '').trim();
    if (stdPriceText) {
      const [minStr, maxStr] = stdPriceText.split('~').map(s => s.trim());
      result.standardPriceMin = minStr ? parseInt(minStr, 10) : null;
      result.standardPriceMax = maxStr ? parseInt(maxStr, 10) : null;
    }

    // 개별 시세 (예: "1,299 만원")
    const individualPriceText = $('#report9 .responsive-table2 .tb-head.tb-row').eq(1).find('.td').text().replace(/[^\d]/g, '').trim();
    if (individualPriceText) {
      result.individualPrice = parseInt(individualPriceText, 10);
    }

    // 1년후 시세 (예: "1,046 만원")
    const after1YearPriceText = $('#report9 .responsive-table2 .tb-head.tb-row').eq(2).find('.td').text().replace(/[^\d]/g, '').trim();
    if (after1YearPriceText) {
      result.after1YearPrice = parseInt(after1YearPriceText, 10);
    }

    // 기타 필요시 추가 정보 추출 가능

    return Object.keys(result).length > 0 ? result : undefined;
  }

  /**
   * 분석보고서 요청 핸들러: DB에 있으면 반환, 없으면 크롤링 후 저장/반환
   */
  async getOrCrawlReportWithAuctionNo(userId: string, auctionNo: string) {
    console.log(`[ScrapingService] getOrCrawlReportWithAuctionNo called: userId=${userId}, auctionNo=${auctionNo}`);
    // 1. 회원 포인트 확인
    const user = await this.prisma.user.findUnique({ where: { id: userId } });
    if (!user) {
      throw new Error('회원 정보를 찾을 수 없습니다.');
    }
    const userPoints = user.points ?? 0;
    const pointsToConsume = 120;
    if (userPoints < pointsToConsume) {
      console.error(`[ScrapingService] 포인트 부족: userId=${userId}, points=${userPoints}`);
      throw new Error('포인트가 부족합니다.');
    }

    // 2. auctionNo로 carNumber 조회
    const auction = await this.prisma.auctionBaseInfo.findUnique({ where: { auction_no: auctionNo } });
    if (!auction) {
      console.error(`[ScrapingService] 경매 정보가 없습니다. auctionNo=${auctionNo}`);
      throw new Error('경매 정보가 없습니다.');
    }
    const carNumber = auction.car_reg_number;
    if (!carNumber) {
      throw new Error('차량번호 정보가 없습니다.');
    }
    console.log(`[ScrapingService] carNumber for auctionNo ${auctionNo}: ${carNumber}`);

    // 3. DB에 기존 분석 리포트가 있으면 포인트 차감 후 반환
    let report = await this.prisma.vehicleComprehensiveReport.findUnique({ where: { auction_no: auctionNo } });
    if (report) {
      console.log(`[ScrapingService] 기존 분석 리포트가 DB에 존재합니다. auctionNo=${auctionNo}`);
      // 트랜잭션으로 포인트 차감 및 리포트 반환
      await this.prisma.$transaction([
        this.prisma.user.update({
          where: { id: userId },
          data: { points: { decrement: pointsToConsume } },
        })
      ]);
      return report;
    }

    // 4. 없으면 크롤링/파싱/DB저장
    try {
      const loginId = process.env.CARHISTORY_ID;
      const loginPw = process.env.CARHISTORY_PW;
      if (!loginId || !loginPw) {
        throw new Error('카히스토리 로그인 정보가 .env에 없습니다.');
      }
      // 크롤링
      const html = await this.crawlingService.crawlCarHistoryReport(carNumber, loginId, loginPw);
      if (!html) {
        throw new Error('크롤링에 실패했습니다.');
      }
      // 파싱 및 DB 저장
      report = await this.parseAuctionPageData(html, auctionNo);
      if (!report) {
        throw new Error('파싱/DB 저장에 실패했습니다.');
      }
      // 트랜잭션으로 포인트 차감 및 리포트 반환
      await this.prisma.$transaction([
        this.prisma.user.update({
          where: { id: userId },
          data: { points: { decrement: pointsToConsume } },
        })
      ]);
      console.log(`[ScrapingService] 새 분석 리포트 저장 및 반환. auctionNo=${auctionNo}`);
      return report;
    } catch (e) {
      console.error(`[ScrapingService] 분석/크롤링/저장 중 오류 발생:`, e);
      // 실패 시 포인트 차감 없이 에러 반환
      throw e;
    }
  }
}