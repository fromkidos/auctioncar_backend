import { Injectable, Logger, NotFoundException, ConflictException, ForbiddenException, BadRequestException, InternalServerErrorException } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';
import { CreateMockBidDto } from './dto/create-mock-bid.dto';
import { User, MockBid, Prisma, AuctionBaseInfo } from '@prisma/client';

@Injectable()
export class MockBidsService {
  private readonly logger = new Logger(MockBidsService.name);

  constructor(private readonly prisma: PrismaService) {}

  async createMockBid(dto: CreateMockBidDto, user: User): Promise<MockBid> {
    this.logger.log(
      `User ${user.id} attempting to create/update mock bid for auction ${dto.auctionNo}, sale date ${dto.auction_sale_date} with amount ${dto.bidAmount}`,
    );

    const { auctionNo, auction_sale_date, bidAmount } = dto;

    // DTO의 auction_sale_date 문자열을 Date 객체로 변환 (시간 부분은 UTC 자정으로 설정하여 날짜만 비교하기 위함)
    // 또는 클라이언트가 항상 YYYY-MM-DD 형식만 보낸다고 가정하고 new Date(auction_sale_date_string) 사용.
    // 여기서는 일단 new Date()로 변환.
    const requestedSaleDate = new Date(auction_sale_date);
    if (isNaN(requestedSaleDate.getTime())) {
      throw new BadRequestException('유효하지 않은 auction_sale_date 형식입니다.');
    }

    // 1. AuctionBaseInfo 조회 및 유효성 검사
    const auction = await this.prisma.auctionBaseInfo.findUnique({
      where: { auction_no: auctionNo },
    });

    if (!auction) {
      throw new NotFoundException(
        `[${auctionNo}] 해당하는 경매 정보를 찾을 수 없습니다.`,
      );
    }

    // auction_sale_date 일치 여부 검사 (날짜 부분만 비교)
    if (!auction.sale_date) {
        throw new BadRequestException(`[${auctionNo}] 경매의 매각기일 정보가 없습니다.`);
    }
    // DB의 sale_date (DateTime)와 요청된 sale_date (Date)의 날짜 부분 비교
    // toDateString()은 로컬 타임존 기준으로 " 영향받을 수 있으므로 주의. 더 엄밀한 비교 필요시 라이브러리 사용.
    const dbSaleDate = new Date(auction.sale_date);
    if (dbSaleDate.toDateString() !== requestedSaleDate.toDateString()) {
        this.logger.warn(`Date mismatch: DB sale_date ${dbSaleDate.toISOString()} vs Requested ${requestedSaleDate.toISOString()}`);
        throw new BadRequestException(
            `[${auctionNo}] 요청된 매각기일(${requestedSaleDate.toLocaleDateString()})이 실제 경매의 매각기일(${dbSaleDate.toLocaleDateString()})과 일치하지 않습니다.`
        );
    }

    // 모의 입찰 마감일 로직 (요청된 매각기일이 과거인지 확인)
    const now = new Date();
    // 날짜만 비교하기 위해 now의 시간 부분을 제거
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()); 

    if (requestedSaleDate < today) { // requestedSaleDate는 이미 날짜의 시작으로 간주 (시간부분이 00:00:00 일 수 있음)
      throw new ForbiddenException(
        `[${auctionNo}] 해당 경매의 모의 입찰 기간이 마감되었습니다 (요청된 매각기일: ${requestedSaleDate.toLocaleDateString()}).`,
      );
    }

    // 경매 상태 검사 (예: '정지', '종료' 등 입찰 불가 상태)
    const nonBiddableStatus = ['정지', '종료', '취소', '기각', '매각완료', '유찰처리완료']; // 예시 상태값
    if (auction.status && nonBiddableStatus.includes(auction.status)) {
        throw new ForbiddenException(
            `[${auctionNo}] 현재 경매 상태(${auction.status})에서는 모의 입찰을 할 수 없습니다.`,
          );
    }
    // 만약 AuctionBaseInfo에 current_round가 있고 -1 (진행불가) 상태를 사용한다면 해당 검증도 추가

    // 2. 최소 입찰 금액 검사 (AuctionBaseInfo의 min_bid_price 기준)
    if (auction.min_bid_price !== null && auction.min_bid_price !== undefined && bidAmount < Number(auction.min_bid_price)) {
      throw new BadRequestException(
        `입찰 금액은 최저 매각 가격 (${Number(auction.min_bid_price).toLocaleString()}원) 이상이어야 합니다.`,
      );
    }

    // 3. MockBid 생성 또는 업데이트 (Upsert)
    const bidAmountBigInt = BigInt(bidAmount);

    // upsert를 위해 auction_sale_date는 DB에 저장될 Date 객체 (시간 정보 포함 가능)
    // DTO에서 받은 auction_sale_date 문자열을 new Date()로 변환한 requestedSaleDate를 사용.
    // 만약 YYYY-MM-DD만 받고 DB에도 시간 없이 저장하고 싶다면, new Date(YYYY, MM-1, DD) 형태로 생성 필요.
    // Prisma는 DateTime이므로 시간정보가 00:00:00Z 등으로 저장됨.
    const saleDateForDb = requestedSaleDate; 

    try {
      const mockBid = await this.prisma.$transaction(async (tx) => {
        const existingMockBid = await tx.mockBid.findUnique({
          where: {
            user_auction_sale_date_unique: {
              userId: user.id,
              auctionNo: auctionNo,
              auction_sale_date: saleDateForDb,
            },
          },
        });

        if (existingMockBid) {
          // 모의 입찰 업데이트: 포인트 차감 없음
          this.logger.log(
            `Updating existing mock bid ${existingMockBid.id} for user ${user.id}, auction ${auctionNo}, sale date ${saleDateForDb.toISOString()}. No point deduction.`
          );
          return tx.mockBid.update({
            where: { 
                // id: existingMockBid.id // id를 사용하거나 unique 제약조건을 사용
                user_auction_sale_date_unique: {
                    userId: user.id,
                    auctionNo: auctionNo,
                    auction_sale_date: saleDateForDb,
                }
            },
            data: {
              bidAmount: bidAmountBigInt,
              bidTime: new Date(),
              isProcessed: false, // 업데이트 시에도 초기화
              rank: null, // 관련 필드 초기화 또는 기존 값 유지 정책 필요
              earnedExperiencePoints: null,
            },
          });
        } else {
          // 모의 입찰 생성: 포인트 차감 진행
          this.logger.log(
            `Creating new mock bid for user ${user.id}, auction ${auctionNo}, sale date ${saleDateForDb.toISOString()}. Attempting point deduction.`
          );
          const userRecord = await tx.user.findUnique({
            where: { id: user.id },
            select: { points: true },
          });

          if (!userRecord) {
            throw new InternalServerErrorException('사용자 정보를 찾을 수 없습니다.');
          }

          const currentPoints = userRecord.points ?? 0;
          const pointsToDeduct = 30;

          if (currentPoints < pointsToDeduct) {
            throw new ForbiddenException(
              `모의 입찰 생성에 필요한 포인트(${pointsToDeduct}점)가 부족합니다. 현재 보유 포인트: ${currentPoints}점`,
            );
          }

          await tx.user.update({
            where: { id: user.id },
            data: { points: currentPoints - pointsToDeduct },
          });

          return tx.mockBid.create({
            data: {
              userId: user.id,
              auctionNo: auctionNo,
              auction_sale_date: saleDateForDb,
              bidAmount: bidAmountBigInt,
              bidTime: new Date(),
              isProcessed: false,
              rank: null,
              earnedExperiencePoints: null,
            },
          });
        }
      });

      this.logger.log(
        `User ${user.id} successfully created/updated mock bid for auction ${auctionNo}, sale date ${saleDateForDb.toISOString()}, ID ${mockBid.id}`,
      );
      return mockBid;
    } catch (error) {
      if (error instanceof Prisma.PrismaClientKnownRequestError) {
        if (error.code === 'P2002') {
          throw new ConflictException(
            '모의 입찰을 처리하는 중 충돌이 발생했습니다. 잠시 후 다시 시도해주세요.',
          );
        }
      }
      this.logger.error(
        `Failed to create/update mock bid for user ${user.id}, auction ${auctionNo}, sale date ${saleDateForDb.toISOString()}: ${error.message}`,
        error.stack,
      );
      throw new InternalServerErrorException('모의 입찰 처리 중 오류가 발생했습니다.');
    }
  }

  // 특정 사용자의 모의 입찰 내역 조회 로직
  async findMyMockBids(userId: string): Promise<any> {
    this.logger.log(`Fetching mock bids for user ${userId}`);
    const mockBids = await this.prisma.mockBid.findMany({
      where: { userId },
      orderBy: { bidTime: 'desc' },
      include: {
        auction: {
          include: {
            auctionResult: true, // 경매결과 정보 포함
          },
        },
      },
    });

    return mockBids.map((bid) => {
      const { auction, ...restOfBid } = bid;

      return {
        ...restOfBid,
        auctionBaseInfo: {
          ...auction,
          id: auction.auction_no,
          image_url: null, // 클라이언트에서 직접 URL 구성
        },
      };
    });
  }

  // 특정 경매의 특정 매각기일에 대한 모의 입찰 내역 조회 (새로운 메소드 또는 기존 메소드 수정)
  async getMockBidsByAuctionNoAndSaleDate(auctionNo: string, saleDateStr: string): Promise<MockBid[]> {
    this.logger.log(`Fetching mock bids for auction ${auctionNo} on sale date ${saleDateStr}`);
    const targetSaleDate = new Date(saleDateStr);
    if (isNaN(targetSaleDate.getTime())) {
        throw new BadRequestException('유효하지 않은 saleDateStr 형식입니다.');
    }

    // DB에서 해당 auctionNo의 AuctionBaseInfo를 찾아 sale_date를 가져와서, 
    // 요청된 targetSaleDate와 날짜 부분만 일치하는 MockBid를 찾아야 함.
    // 또는 MockBid의 auction_sale_date를 직접 범위로 검색.
    // 여기서는 Prisma의 DateTime 필터 기능을 활용하여 날짜 범위로 검색 (해당 날짜의 시작 ~ 끝)
    const startDate = new Date(targetSaleDate.getFullYear(), targetSaleDate.getMonth(), targetSaleDate.getDate());
    const endDate = new Date(targetSaleDate.getFullYear(), targetSaleDate.getMonth(), targetSaleDate.getDate() + 1);

    const mockBids = await this.prisma.mockBid.findMany({
      where: {
        auctionNo: auctionNo,
        auction_sale_date: {
          gte: startDate,
          lt: endDate,
        }
      },
      orderBy: { bidAmount: 'desc' },
      include: { user: { select: { id: true, displayName: true, profileImageUrl: true } } },
    });

    // BigInt를 문자열로 변환하기 위한 replacer 함수
    const replacer = (key: string, value: any) => {
      if (typeof value === 'bigint') {
        return value.toString();
      }
      return value;
    };

    this.logger.debug(
      `Raw mockBids data for auction ${auctionNo} on ${saleDateStr} before sending: ${JSON.stringify(mockBids, replacer)}`
    );

    return mockBids;
  }

  // 기존 getMockBidsByAuctionNo는 이제 여러 회차(sale_date)를 다 가져오므로, 최신 회차만 보여주거나, 페이지네이션 처리 등이 필요할 수 있음.
  // 우선은 모든 회차의 입찰을 가져오도록 둠.
  async getMockBidsByAuctionNo(auctionNo: string): Promise<MockBid[]> {
    this.logger.log(`Fetching ALL mock bids for auction ${auctionNo} across all sale dates`);
    const auctionExists = await this.prisma.auctionBaseInfo.findUnique({
      where: { auction_no: auctionNo },
    });
    if (!auctionExists) {
      throw new NotFoundException(`[${auctionNo}] 경매 정보를 찾을 수 없습니다.`);
    }

    return this.prisma.mockBid.findMany({
      where: { auctionNo },
      orderBy: [{ auction_sale_date: 'desc' }, { bidAmount: 'desc' }],
      include: { user: { select: { id: true, displayName: true, profileImageUrl: true } } },
    });
  }
} 