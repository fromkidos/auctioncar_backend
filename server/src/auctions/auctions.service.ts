import { Injectable, NotFoundException, Logger } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';
import { AuctionListItemDto } from './dto/auction-list-item.dto';
import { AuctionUserActivityDto, UpdateAuctionUserActivityDto, IncrementAuctionViewDto } from './dto/auction-user-activity.dto';
import { AuctionHomeSummaryDto } from './dto/auction-home-summary.dto';
import { AuctionDetailDto } from './dto/auction-detail.dto';
import { Prisma } from '@prisma/client';

// 임시로 any 타입 사용 - Prisma 클라이언트 타입 재생성 후 수정 필요
type AuctionBaseInfo = any;
type PhotoURL = any;
type AuctionDetailInfo = any;
type DateHistory = any;
type SimilarSale = any;
type AuctionAnalysisAccess = any;
type CourtInfo = any;
type AuctionResult = any;
type MockBid = any;
type AuctionAppraisalSummary = any;
import { CourtInfoDto } from './dto/court-info.dto';
import { ConfigService } from '@nestjs/config';
import { AuctionUserActivity } from '@prisma/client';

// --- URL 구성에 필요한 상수 ---
// const SERVER_BASE_URL = 'http://192.168.0.10:4000'; // 삭제: ConfigService에서 가져올 것임
// const STATIC_FILES_URL_PREFIX = '/uploads/auction_images/'; // 삭제: toWebImageUrl 메소드 내에서 직접 사용

// 날짜 조정 헬퍼 함수
function adjustDateForKstInterpretation(date: Date | null | undefined): Date | null {
  if (!date) return null;
  return new Date(date.getTime() - (9 * 60 * 60 * 1000));
}

// 데이터를 클라이언트로 보내기 전 변환 (BigInt -> string, Date -> ISO string)
function convertDataForClient(obj: any, visitedObjects = new WeakSet(), depth = 0): any {
  // 순환 참조 감지 및 깊이 제한
  if (depth > 10) {
    console.warn(`[convertDataForClient] Maximum depth reached (${depth}), stopping recursion`);
    return '[Max Depth Reached]';
  }
  
  if (obj === null || obj === undefined) return obj; // null 또는 undefined는 그대로 반환
  
  if (obj instanceof Date) {
    // 이 함수로 전달되는 Date 객체는 이미 adjustDateForKstInterpretation를 통해
    // 올바른 UTC 기준으로 조정된 상태여야 합니다.
    return obj.toISOString();
  }
  
  if (Array.isArray(obj)) {
    return obj.map((item, index) => {
      try {
        return convertDataForClient(item, visitedObjects, depth + 1);
      } catch (error) {
        console.error(`[convertDataForClient] Error processing array item at index ${index}:`, error);
        return item; // 원본 반환
      }
    });
  }
  
  if (obj && typeof obj === 'object' && obj !== null) {
    // 순환 참조 체크
    if (visitedObjects.has(obj)) {
      console.warn(`[convertDataForClient] Circular reference detected, skipping object`);
      return '[Circular Reference]';
    }
    
    // 현재 객체를 방문한 객체 집합에 추가
    visitedObjects.add(obj);
    
    try {
      const newObj: { [key: string]: any } = {};
      for (const key in obj) {
        if (Object.prototype.hasOwnProperty.call(obj, key)) {
          try {
            // auctionBaseInfo, recentAuctionResults, myMockBids는 이미 DTO 형태로 변환되었으므로, 
            // convertDataForClient를 재귀적으로 호출하지 않고 그대로 할당합니다.
            if ((key === 'auctionBaseInfo' || key === 'recentAuctionResults' || key === 'myMockBids') && obj[key] !== null && typeof obj[key] === 'object') {
              newObj[key] = obj[key];
            } else {
              newObj[key] = convertDataForClient(obj[key], visitedObjects, depth + 1);
            }
          } catch (error) {
            console.error(`[convertDataForClient] Error processing property '${key}':`, error);
            newObj[key] = obj[key]; // 원본 값 할당
          }
        }
      }
      
      // 처리 완료 후 객체를 집합에서 제거 (다른 경로에서 재방문 가능하도록)
      visitedObjects.delete(obj);
      return newObj;
    } catch (error) {
      // 오류 발생 시 객체를 집합에서 제거
      visitedObjects.delete(obj);
      console.error(`[convertDataForClient] Error processing object:`, error);
      return obj; // 원본 반환
    }
  }
  
  if (typeof obj === 'bigint') {
    return obj.toString();
  }
  
  return obj;
}

const fullAuctionInclude = {
  photoUrls: { 
    orderBy: { photo_index: 'asc' as const },
    take: 50, // 이미지 수 제한
  },
  detailInfo: true,
  dateHistories: { 
    orderBy: { date_time: 'asc' as const },
    take: 100, // 날짜 히스토리 수 제한
  },
  similarSales: {
    take: 20, // 유사 판매 수 제한
  },
  analysisAccesses: {
    take: 50, // 분석 접근 수 제한
  },
  appraisalSummary: true,
  auctionResult: true,
} as const;

export type FullAuction = AuctionBaseInfo & {
  photoUrls: PhotoURL[];
  detailInfo: AuctionDetailInfo | null;
  dateHistories: DateHistory[];
  similarSales: SimilarSale[];
  analysisAccesses: AuctionAnalysisAccess[];
  appraisalSummary: AuctionAppraisalSummary | null;
  auctionResult: AuctionResult | null;
};

// Prisma의 AuctionBaseInfo & 관련 모델 타입을 위한 인터페이스 확장 (DTO 변환 전 단계)
interface AuctionBaseInfoWithRelations extends AuctionBaseInfo {
  photoUrls: PhotoURL[];
  detailInfo?: AuctionDetailInfo | null;
  dateHistories: DateHistory[];
  similarSales: SimilarSale[];
  analysisAccesses: AuctionAnalysisAccess[];
  appraisalSummary?: AuctionAppraisalSummary | null;
  auctionResult?: AuctionResult | null;
}

@Injectable()
export class AuctionsService {
  private readonly logger = new Logger(AuctionsService.name);
  // private readonly staticFilesUrlPrefix = '/uploads/auction_images/'; // 삭제

  constructor(
    private readonly prisma: PrismaService,
    private readonly configService: ConfigService,
  ) {}

  private toWebImageUrl(dbFilePath: string | null | undefined): string | null {

  try {
    if (!dbFilePath) {
      return null;
    }
    
    // 이미 완전한 URL인 경우 그대로 반환 (예: 외부 이미지 URL)
    if (dbFilePath.startsWith('http://') || dbFilePath.startsWith('https://')) {
      return dbFilePath;
    }

    const serverBaseUrl = this.configService.get<string>('SERVER_BASE_URL') || 
      `http://${this.configService.get<string>('HOST', '127.0.0.1')}:${this.configService.get<string>('PORT', '4000')}`;
    const staticPrefix = '/static';
    const imageBasePath = '/uploads/auction_images/';
    
    // dbFilePath가 혹시라도 전체 경로를 포함하고 있다면 파일명만 추출 (일반적으로는 파일명만 저장되어 있을 것으로 예상)
    const filename = dbFilePath.includes('/') ? dbFilePath.substring(dbFilePath.lastIndexOf('/') + 1) : dbFilePath;

    const finalUrl = `${serverBaseUrl}${staticPrefix}${imageBasePath}${filename}`;
    return finalUrl;
  } catch (error) {
    this.logger.error(`[toWebImageUrl] Error generating web URL for: ${dbFilePath}`, error);
    return null;
  }

    // try {
    //   if (!dbFilePath) {
    //     return null;
    //   }
      
    //   // 이미 완전한 URL인 경우 그대로 반환 (예: 외부 이미지 URL)
    //   if (dbFilePath.startsWith('http://') || dbFilePath.startsWith('https://')) {
    //     return dbFilePath;
    //   }

    //   const serverBaseUrl = this.configService.get<string>('SERVER_BASE_URL') || 
    //     `http://${this.configService.get<string>('HOST', '127.0.0.1')}:${this.configService.get<string>('PORT', '4000')}`;
    //   const staticPrefix = '/static';
    //   const imageBasePath = '/uploads/auction_images/';
      
    //   // dbFilePath가 혹시라도 전체 경로를 포함하고 있다면 파일명만 추출 (일반적으로는 파일명만 저장되어 있을 것으로 예상)
    //   const filename = dbFilePath.includes('/') ? dbFilePath.substring(dbFilePath.lastIndexOf('/') + 1) : dbFilePath;

    //   const finalUrl = `${serverBaseUrl}${staticPrefix}${imageBasePath}${filename}`;
    //   return finalUrl;
    // } catch (error) {
    //   this.logger.error(`[toWebImageUrl] Error generating web URL for: ${dbFilePath}`, error);
    //   return null;
    // }
  }





  // CourtInfo[] -> CourtInfoDto[] 변환 유틸 (클래스 내부 private 메소드로 변경)
  private toCourtInfoDtos(courtInfos: CourtInfo[]): CourtInfoDto[] {
    return courtInfos.map(info => ({
      court_name: info.court_name,
      region: info.region ?? '지역 정보 없음',
      address: info.address,
      latitude: info.latitude,
      longitude: info.longitude,
    }));
  }

  // 이 서비스 내에서만 사용되는 DTO 변환 함수
  private toAuctionListItemDto(auction: FullAuction): AuctionListItemDto {
    const webAccessibleImageUrl = (auction.photoUrls && auction.photoUrls.length > 0)
      ? this.toWebImageUrl(auction.photoUrls[auction.representative_photo_index]?.image_path_or_url ?? auction.photoUrls[0].image_path_or_url)
      : null;

    // 상세 정보와 동일하게 날짜 조정 로직 추가
    const adjustedSaleDate = adjustDateForKstInterpretation(auction.sale_date);

    return {
      id: auction.auction_no,
      case_year: auction.case_year,
      case_number: auction.case_number,
      item_no: auction.item_no,
      court_name: auction.court_name,
      appraisal_price: auction.appraisal_price?.toString() ?? null,
      min_bid_price: auction.min_bid_price?.toString() ?? null,
      min_bid_price_2: auction.min_bid_price_2?.toString() ?? null,
      sale_date: adjustedSaleDate, // 조정된 날짜 사용
      status: auction.status,
      car_name: auction.car_name,
      car_model_year: auction.car_model_year,
      car_reg_number: auction.car_reg_number,
      car_mileage: auction.car_mileage,
      car_fuel: auction.car_fuel,
      car_transmission: auction.car_transmission,
      car_type: auction.car_type,
      manufacturer: auction.manufacturer,
      representative_photo_index: auction.representative_photo_index,
      image_url: webAccessibleImageUrl,
      appraisalSummary: auction.appraisalSummary,
      auctionResult: auction.auctionResult,
    };
  }
  
  private toAuctionListItemDtos(auctions: FullAuction[]): AuctionListItemDto[] {
    return auctions.map(a => this.toAuctionListItemDto(a));
  }

  async findOngoingAuctions(): Promise<AuctionListItemDto[]> {
    const ongoingAuctions = await this.prisma.auctionBaseInfo.findMany({
      where: {
        OR: [
          { status: '경매진행' }, 
          { status: '입찰가능' }, 
          { sale_date: { gte: new Date() } },
        ],
      },
      include: fullAuctionInclude,
      orderBy: { sale_date: 'asc' },
    });
    return this.toAuctionListItemDtos(ongoingAuctions);
  }

  // AuctionUserActivity: 경매 조회수 증가
  async incrementAuctionView(dto: IncrementAuctionViewDto): Promise<AuctionUserActivityDto> {
    const { userId, auctionNo } = dto;
    
    try {
      // upsert: row가 있으면 viewCount+1, 없으면 새로 생성
      const activity = await this.prisma.auctionUserActivity.upsert({
        where: {
          userId_auctionNo: { userId, auctionNo },
        },
        update: {
          viewCount: { increment: 1 },
          lastViewed: new Date(),
        },
        create: {
          userId,
          auctionNo,
          viewCount: 1,
          lastViewed: new Date(),
          isFavorite: false,
        },
      });
      
      return activity;
    } catch (error) {
      this.logger.error(`[incrementAuctionView] Error incrementing view count for user: ${userId}, auction: ${auctionNo}:`, error);
      throw new Error(`조회수 증가 중 오류가 발생했습니다: ${error.message}`);
    }
  }

  // AuctionUserActivity: 즐겨찾기 토글/설정
  async updateAuctionFavorite(dto: UpdateAuctionUserActivityDto): Promise<AuctionUserActivityDto> {
    const { userId, auctionNo, isFavorite } = dto;
    // row가 없으면 생성, 있으면 isFavorite만 변경
    const activity = await this.prisma.auctionUserActivity.upsert({
      where: {
        userId_auctionNo: { userId, auctionNo },
      },
      update: {
        isFavorite: isFavorite ?? true,
        lastViewed: new Date(),
      },
      create: {
        userId,
        auctionNo,
        viewCount: 0,
        lastViewed: new Date(),
        isFavorite: isFavorite ?? true,
      },
    });
    return activity;
  }

  // AuctionUserActivity: 유저별 즐겨찾기 목록
  async getUserFavorites(userId: string): Promise<AuctionUserActivityDto[]> {
    return this.prisma.auctionUserActivity.findMany({
      where: { userId, isFavorite: true },
      include: { auction: { include: { photoUrls: { orderBy: {photo_index: 'asc'}} } } } 
    });
  }

  // AuctionUserActivity: 경매별 유니크 조회자 수, 총 조회수
  async getAuctionActivityStats(auctionNo: string): Promise<{ uniqueViewers: number; totalViews: number }> {
    const activities = await this.prisma.auctionUserActivity.findMany({
      where: { auctionNo },
      select: { viewCount: true },
    });
    const uniqueViewers = activities.length;
    const totalViews = activities.reduce((sum: number, a: any) => sum + a.viewCount, 0);
    return { uniqueViewers, totalViews };
  }

  // 인기차량(조회 row 많은 순)
  async getPopularAuctions(limit = 10): Promise<AuctionListItemDto[]> {
    const popularActivities = await this.prisma.auctionUserActivity.groupBy({
      by: ['auctionNo'],
      _count: {
        auctionNo: true,
      },
      orderBy: {
        _count: {
          auctionNo: 'desc',
        },
      },
      take: limit,
    });
    
    const auctionNos = popularActivities.map(activity => activity.auctionNo);
    
    if (auctionNos.length === 0) {
      return [];
    }

    const popularAuctions = await this.prisma.auctionBaseInfo.findMany({
      where: {
        auction_no: { in: auctionNos },
      },
      include: fullAuctionInclude,
    });

    // groupBy 결과 순서를 유지하기 위한 처리
    const sortedAuctions = auctionNos.map(no => popularAuctions.find(a => a.auction_no === no)).filter(Boolean) as FullAuction[];

    return this.toAuctionListItemDtos(sortedAuctions);
  }

  // DTO 변경에 따라 myFavorites, myViewed 대신 myActivity를 반환하도록 수정
  async getUserActivity(userId: string): Promise<AuctionUserActivity[]> {
    if (!userId) {
      return [];
    }
    return this.prisma.auctionUserActivity.findMany({
      where: { userId: userId },
      orderBy: { lastViewed: 'desc' },
      take: 50, // 최근 활동 50개 제한
    });
  }

  async getHomeSummary(userId: string): Promise<AuctionHomeSummaryDto> {
    this.logger.debug(`[getHomeSummary] 시작 - userId: ${userId}`);
    
    try {
      // 1. "인기 경매" (조회수 기준) - auctionNo 배열
      const popularAuctionsPromise = this.getPopularAuctions(50);

      // 2. "나의 즐겨찾기"
      const myFavoritesPromise = this.prisma.auctionUserActivity
        .findMany({
          where: { userId: userId, isFavorite: true },
          orderBy: { lastViewed: 'desc' },
          take: 50,
          include: { auction: { include: fullAuctionInclude } },
        })
        .then((activities) =>
          this.toAuctionListItemDtos(
            activities.map((a) => a.auction).filter(Boolean) as FullAuction[],
          ),
        );

      // 3. "내가 조회한 경매"
      const myViewedPromise = this.prisma.auctionUserActivity
        .findMany({
          where: { userId: userId, viewCount: { gt: 0 } },
          orderBy: { lastViewed: 'desc' },
          take: 50,
          include: { auction: { include: fullAuctionInclude } },
        })
        .then((activities) =>
          this.toAuctionListItemDtos(
            activities.map((a) => a.auction).filter(Boolean) as FullAuction[],
          ),
        );

      // 4. "나의 모의 입찰" - MockBid 객체 배열
      const myMockBidsPromise = this.prisma.mockBid.findMany({
        where: { userId: userId },
        orderBy: { createdAt: 'desc' },
      });

      // 5. "신규 등록" 및 "정보 변경" - AuctionListItemDto 객체 배열
      const threeDaysAgo = new Date();
      threeDaysAgo.setDate(threeDaysAgo.getDate() - 3);
      const todayStart = new Date();
      todayStart.setHours(0, 0, 0, 0);

      const newlyRegisteredAuctionsPromise = this.prisma.auctionBaseInfo.findMany({
        where: {
          status: { in: ['경매진행', '입찰가능', '신건', '유찰 1회', '유찰'] },
          OR: [
            { created_at: { gte: todayStart } }, // 신규: 오늘 생성된 경매
            {
              // 정보 변경: 오늘 업데이트되었지만, 오늘 생성되지 않은 경매
              AND: [
                { updated_at: { gte: todayStart } },
                { created_at: { lt: todayStart } },
              ],
            },
          ],
        },
        include: fullAuctionInclude,
        orderBy: {
          created_at: 'desc'
        },
        take: 50, // 50개 제한
      }).then(auctions => this.toAuctionListItemDtos(auctions));
      
      // 6. "최근 매각" - AuctionResult 객체 배열 (Full)
      const recentAuctionResultsPromise = this.prisma.auctionResult.findMany({
        where: {
          auction_outcome: '매각',
          updated_at: { gte: new Date(new Date().setHours(0, 0, 0, 0)) }, // 오늘 등록된 경매
        },
        include: {
          auction: { // 'auctionBaseInfo' -> 'auction'
            include: {
              photoUrls: {
                orderBy: { photo_index: 'asc' },
              },
            },
          },
        },
      }).then(results => results.map(result => {
          const baseInfo = (result as any).auction;
          if (baseInfo) {
            const representativePhoto = baseInfo.photoUrls.find(p => p.photo_index === baseInfo.representative_photo_index) 
                                      ?? baseInfo.photoUrls[0];
            
            (result as any).auctionBaseInfo = {
              ...baseInfo,
              image_url: this.toWebImageUrl(representativePhoto?.image_path_or_url)
            };
            delete (result as any).auction; // 원래의 'auction' 필드는 삭제
          }
          return result;
      }));

      // 7. 법원 정보
      const courtInfosPromise = this.prisma.courtInfo.findMany();

      const [
        popular,
        myFavorites,
        myViewed,
        myMockBids,
        newlyRegisteredAuctions,
        recentAuctionResults,
        courtInfosRaw,
      ] = await Promise.all([
        popularAuctionsPromise,
        myFavoritesPromise,
        myViewedPromise,
        myMockBidsPromise,
        newlyRegisteredAuctionsPromise,
        recentAuctionResultsPromise,
        courtInfosPromise,
      ]);

      const courtInfos = this.toCourtInfoDtos(courtInfosRaw);
      
      this.logger.debug('[getHomeSummary] 모든 데이터 조회 완료');

      const summary: Omit<AuctionHomeSummaryDto, 'myActivity'> & {
        myFavorites?: AuctionListItemDto[];
        myViewed?: AuctionListItemDto[];
      } = {
        popular,
        myFavorites,
        myViewed,
        myMockBids,
        newlyRegisteredAuctions,
        recentAuctionResults,
        courtInfos,
      };

      // `convertDataForClient`는 BigInt 등을 처리하지만, 최상위 DTO 구조를 변경하지는 않습니다.
      // 따라서 여기서 반환하는 값은 AuctionHomeSummaryDto와 구조적으로 호환됩니다.
      return convertDataForClient(summary);

    } catch (error) {
      this.logger.error(`[getHomeSummary] 홈 화면 데이터 요약 생성 중 오류 발생 - userId: ${userId}`, error);
      throw new Error('홈 화면 요약 정보를 가져오는 데 실패했습니다.');
    }
  }

  // 경매 상세 정보 조회 + 조회수 증가
  async getAuctionDetailWithView(auction_no: string, userId: string): Promise<AuctionDetailDto> {
    this.logger.log(`[getAuctionDetailWithView] Starting detail fetch for auction: ${auction_no}, user: ${userId}`);
    
    try {
      // 1. 조회수 증가
      await this.incrementAuctionView({ userId, auctionNo: auction_no });

      // 2. 데이터 조회
      const baseInfoData: FullAuction | null = await this.prisma.auctionBaseInfo.findUnique({
        where: { auction_no },
        include: fullAuctionInclude,
      });

      if (!baseInfoData) {
        this.logger.error(`[getAuctionDetailWithView] Auction not found: ${auction_no}`);
        throw new NotFoundException('경매 정보를 찾을 수 없습니다.');
      }
      
      // 3. 사용자 활동 정보 조회
      const userActivity = await this.prisma.auctionUserActivity.findUnique({
        where: { userId_auctionNo: { userId, auctionNo: auction_no } },
        select: { isFavorite: true },
      });
      
      // 4. 날짜 조정
      const adjustedSaleDate = adjustDateForKstInterpretation(baseInfoData.sale_date);

      // 5. 데이터 구조 분해
      const { detailInfo, dateHistories, photoUrls, similarSales, analysisAccesses, ...restOfBaseInfo } = baseInfoData;
      
      // 6. 클라이언트용 데이터 준비
      const clientReadyBaseInfo = {
          ...restOfBaseInfo,
          sale_date: adjustedSaleDate 
      };
      
      // 7. 날짜 히스토리 처리
      const clientReadyDateHistories = (dateHistories || []).map(h => ({ 
        ...h, 
        date_time: adjustDateForKstInterpretation(h.date_time) 
      }));
      
      // 8. 상세 정보 처리
      const clientReadyDetailInfo = detailInfo ? {
          ...detailInfo,
          case_received_date: adjustDateForKstInterpretation(detailInfo.case_received_date),
          auction_start_date: adjustDateForKstInterpretation(detailInfo.auction_start_date),
          distribution_due_date: adjustDateForKstInterpretation(detailInfo.distribution_due_date),
      } : null;

      const isFavorite = userActivity?.isFavorite ?? false;

      // 9. 이미지 URL 처리
      const processedPhotoUrls = (photoUrls || []).map((p, index) => {
        try {
          //const webUrl = this.toWebImageUrl(p.image_path_or_url);
          const webUrl = p.image_path_or_url;
          return {
            ...p,
            image_path_or_url: webUrl,
          };
        } catch (error) {
          this.logger.error(`[getAuctionDetailWithView] Error processing photo URL ${index} for auction ${auction_no}:`, error);
          return {
            ...p,
            image_path_or_url: null,
          };
        }
      });

      // 10. 최종 데이터 구조 생성
      const finalDataStructure = { 
        baseInfo: clientReadyBaseInfo, 
        detailInfo: clientReadyDetailInfo, 
        dateHistories: clientReadyDateHistories, 
        photoUrls: processedPhotoUrls,
        similarSales: (similarSales || []).map(sale => {
          try {
            return convertDataForClient(sale);
          } catch (error) {
            this.logger.error(`[getAuctionDetailWithView] Error converting similar sale for auction ${auction_no}:`, error);
            return sale;
          }
        }),
        analysisAccesses: (analysisAccesses || []).map(access => {
          try {
            return convertDataForClient(access);
          } catch (error) {
            this.logger.error(`[getAuctionDetailWithView] Error converting analysis access for auction ${auction_no}:`, error);
            return access;
          }
        }),
        isFavorite: isFavorite,
      };
      
      // 11. 최종 데이터 변환
      const result = convertDataForClient(finalDataStructure) as AuctionDetailDto;
      this.logger.log(`[getAuctionDetailWithView] Successfully completed detail fetch for auction: ${auction_no}`);
      
      return result;
    } catch (error) {
      this.logger.error(`[getAuctionDetailWithView] Error fetching auction detail for ${auction_no}:`, error);
      if (error instanceof NotFoundException) {
        throw error;
      }
      throw new Error(`경매 상세 정보 조회 중 오류가 발생했습니다: ${error.message}`);
    }
  }





  async isFavorite(userId: string | undefined, auctionNo: string): Promise<boolean> {
    if (!userId) {
      return false;
    }
    const activity = await this.prisma.auctionUserActivity.findUnique({
      where: { userId_auctionNo: { userId, auctionNo } },
    });
    return activity?.isFavorite ?? false;
  }

  // TODO: 특정 경매 상세 정보 조회, 입찰 등의 메소드 추가 예정
} 