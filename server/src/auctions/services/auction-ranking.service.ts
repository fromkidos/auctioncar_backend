import { Injectable, Logger } from '@nestjs/common';
import { PrismaService } from 'src/prisma/prisma.service';
import { ConfigService } from '@nestjs/config';
import { PointTransactionType } from '@prisma/client';
// import { AuctionResult } from '@prisma/client'; // 필요시 주석 해제

@Injectable()
export class AuctionRankingService {
  private readonly logger = new Logger(AuctionRankingService.name);
  private readonly mockBidPointsRefundOnCancel: number;
  private readonly mockBidXpGrantOnCancel: number;

  constructor(
    private readonly prisma: PrismaService,
    private readonly configService: ConfigService,
  ) {
    this.mockBidPointsRefundOnCancel = +this.configService.get<number>('MOCK_BID_CREATION_POINTS_DEDUCTION', 30);
    this.mockBidXpGrantOnCancel = +this.configService.get<number>('MOCK_BID_XP_GRANT_ON_CANCEL', 50);
  }

  /**
   * 특정 경매의 실제 낙찰 결과를 바탕으로 모의 입찰 순위를 처리하고 경험치를 지급합니다. (매각 시)
   * @param auctionNo 처리할 경매 번호
   * @param actualSalePrice 실제 낙찰가
   */
  async processAuctionRankings(
    auctionNo: string,
    actualSalePrice: number, 
  ): Promise<void> {
    this.logger.log(
      `[${auctionNo}] 모의 입찰 순위 처리 시작. 실제 낙찰가: ${actualSalePrice}`,
    );

    if (actualSalePrice === null || actualSalePrice === undefined) {
      this.logger.warn(
        `[${auctionNo}] 실제 낙찰가가 없어 순위 처리를 건너뛸 수 있습니다.`,
      );
      return;
    }

    const mockBids = await this.prisma.mockBid.findMany({
      where: {
        auctionNo: auctionNo,
        isProcessed: false,
      },
      include: {
        user: true,
      },
    });

    if (mockBids.length === 0) {
      this.logger.log(`[${auctionNo}] 처리할 모의 입찰 내역이 없습니다.`);
      await this.prisma.mockBid.updateMany({
        where: { auctionNo: auctionNo },
        data: { isProcessed: true, rank: -1 },
      });
      return;
    }

    const totalParticipants = new Set(mockBids.map(mb => mb.userId)).size;
    this.logger.log(`[${auctionNo}] 총 모의 입찰 참여자 수: ${totalParticipants}`);

    const eligibleBids = mockBids.filter(bid => {
      const bidAmount = Number(bid.bidAmount);
      return bidAmount >= actualSalePrice && bidAmount <= actualSalePrice * 1.10;
    });

    const nonEligibleBidIds = mockBids
      .filter(bid => !eligibleBids.some(eb => eb.id === bid.id))
      .map(bid => bid.id);

    if (eligibleBids.length === 0) {
      this.logger.log(`[${auctionNo}] 순위 부여 조건을 만족하는 모의 입찰이 없습니다. (모든 입찰 rank: -1 처리)`);
      await this.prisma.mockBid.updateMany({
        where: { auctionNo: auctionNo, id: { in: mockBids.map(mb => mb.id) } },
        data: { isProcessed: true, rank: -1, earnedExperiencePoints: 0 },
      });
      return;
    }

    eligibleBids.sort((a, b) => Number(a.bidAmount) - Number(b.bidAmount));

    let currentRank = 0;
    let previousBidAmount = -1;
    const rankedBids = eligibleBids.map((bid, index) => {
      const bidAmount = Number(bid.bidAmount);
      if (bidAmount !== previousBidAmount) {
        currentRank = index + 1;
      }
      previousBidAmount = bidAmount;
      return { ...bid, assignedRank: currentRank };
    });

    const winningMockBids = rankedBids.filter(bid => bid.assignedRank === 1);
    const numberOfWinners = winningMockBids.length;

    this.logger.log(
      `[${auctionNo}] 1위 입찰 금액: ${winningMockBids.length > 0 ? winningMockBids[0]?.bidAmount ?? '없음' : '없음'}, 1위 동점자 수: ${numberOfWinners}`
    );

    let xpPerWinner = 0;
    let pointsPerWinner = 0;

    if (numberOfWinners > 0 && totalParticipants > 0) {
      xpPerWinner = Math.round(totalParticipants / numberOfWinners);
      const mockBidCost = this.mockBidPointsRefundOnCancel;
      const nonWinnersCount = totalParticipants - numberOfWinners;
      const totalPoolForWinners = mockBidCost * numberOfWinners;
      const poolFromNonWinners = nonWinnersCount * mockBidCost * 0.8;
      pointsPerWinner = Math.floor((totalPoolForWinners + poolFromNonWinners) / numberOfWinners);
    }
    this.logger.log(`[${auctionNo}] 각 1위에게 지급될 경험치: ${xpPerWinner}, 포인트: ${pointsPerWinner}`);

    try {
      await this.prisma.$transaction(async (tx) => {
        for (const winnerBid of winningMockBids) {
          await tx.mockBid.update({
            where: { id: winnerBid.id },
            data: {
              isProcessed: true,
              rank: 1,
              earnedExperiencePoints: xpPerWinner,
            },
          });

          const userUpdateData: any = {
            experiencePoints: { increment: xpPerWinner },
          };
          if (pointsPerWinner > 0) {
            userUpdateData.points = { increment: pointsPerWinner };
          }
          await tx.user.update({
            where: { id: winnerBid.userId },
            data: userUpdateData,
          });

          if (pointsPerWinner > 0) {
            const balanceAfter = winnerBid.user.points + pointsPerWinner;
            await tx.pointTransaction.create({
              data: {
                userId: winnerBid.userId,
                type: PointTransactionType.MOCK_BID_WINNER_REWARD,
                amount: pointsPerWinner,
                balanceAfter: balanceAfter,
                description: `모의입찰 ${auctionNo} 1등 보상`,
                relatedId: winnerBid.id,
              },
            });
          }
        }

        const otherRankedBids = rankedBids.filter(bid => bid.assignedRank > 1);
        for (const bid of otherRankedBids) {
          await tx.mockBid.update({
            where: { id: bid.id },
            data: {
              isProcessed: true,
              rank: bid.assignedRank,
              earnedExperiencePoints: 0,
            },
          });
        }

        if (nonEligibleBidIds.length > 0) {
          await tx.mockBid.updateMany({
            where: { id: { in: nonEligibleBidIds } },
            data: {
              isProcessed: true,
              rank: -1,
              earnedExperiencePoints: 0,
            },
          });
        }
        this.logger.log(`[${auctionNo}] ${winningMockBids.length}명의 1위, ${otherRankedBids.length}명의 순위권, ${nonEligibleBidIds.length}명의 순위 외 입찰자 정보 업데이트 완료.`);
      });
      this.logger.log(`[${auctionNo}] 순위 처리 및 경험치/포인트 지급 성공 (트랜잭션 완료)`);
    } catch (error) {
      this.logger.error(
        `[${auctionNo}] 순위 처리 중 오류 발생 (트랜잭션 롤백): ${error.message}`,
        error.stack,
      );
    }
  }

  /**
   * '유찰' 및 기타 '매각/낙찰/정지/취소'가 아닌 경매 결과에 대한 모의 입찰을 처리합니다.
   * 참여자들은 탈락 처리되며, 별도 순위나 경험치는 부여되지 않습니다.
   * @param auctionNo 처리할 경매 번호
   * @param auctionSaleDate 해당 경매의 매각기일
   */
  async processUnsoldOrOtherOutcomes( 
    auctionNo: string,
    auctionSaleDate: Date | null,
  ): Promise<void> {
    this.logger.log(
      `[${auctionNo}] '유찰 및 기타' 결과에 대한 모의 입찰 처리 시작. 매각기일: ${auctionSaleDate?.toISOString()}`,
    );
    if (!auctionSaleDate) {
      this.logger.warn(`[${auctionNo}] 매각기일 정보가 없어 '유찰 및 기타' 모의 입찰 처리를 건너뜁니다.`);
      return;
    }

    const targetSaleDateStart = new Date(auctionSaleDate.getFullYear(), auctionSaleDate.getMonth(), auctionSaleDate.getDate());
    const targetSaleDateEnd = new Date(auctionSaleDate.getFullYear(), auctionSaleDate.getMonth(), auctionSaleDate.getDate() + 1);

    const mockBidsToProcess = await this.prisma.mockBid.findMany({
      where: {
        auctionNo: auctionNo,
        auction_sale_date: {
          gte: targetSaleDateStart,
          lt: targetSaleDateEnd,
        },
        isProcessed: false,
      },
    });

    if (mockBidsToProcess.length === 0) {
      this.logger.log(`[${auctionNo}] [${targetSaleDateStart.toISOString().split('T')[0]}] '유찰 및 기타' 결과로 처리할 모의 입찰 내역이 없습니다.`);
      return;
    }

    this.logger.log(
      `[${auctionNo}] [${targetSaleDateStart.toISOString().split('T')[0]}] ${mockBidsToProcess.length}건의 모의 입찰을 '유찰 및 기타' 결과로 처리합니다.`,
    );

    try {
      const idsToUpdate = mockBidsToProcess.map(bid => bid.id);
      await this.prisma.mockBid.updateMany({
        where: {
          id: { in: idsToUpdate },
        },
        data: {
          isProcessed: true,
          rank: -1,
          earnedExperiencePoints: 0, 
        },
      });
      this.logger.log(
        `[${auctionNo}] [${targetSaleDateStart.toISOString().split('T')[0]}] '유찰 및 기타' 결과 모의 입찰 처리 완료.`,
      );
    } catch (error) {
      this.logger.error(
        `[${auctionNo}] [${targetSaleDateStart.toISOString().split('T')[0]}] '유찰 및 기타' 결과 모의 입찰 처리 중 오류: ${error.message}`,
        error.stack,
      );
    }
  }


  /**
   * '정지', '취소'된 경매 결과에 대한 모의 입찰을 처리합니다.
   * 참여자들에게는 포인트가 환불(여기서는 생성 시 30점 차감 가정)되고, 고정 경험치 50점이 지급됩니다.
   * @param auctionNo 처리할 경매 번호
   * @param auctionSaleDate 해당 경매의 매각기일
   */
  async processCancellationOrSuspensionOutcomes(
    auctionNo: string,
    auctionSaleDate: Date | null,
  ): Promise<void> {
    this.logger.log(
      `[${auctionNo}] '정지/취소' 결과에 대한 모의 입찰 처리 시작. 매각기일: ${auctionSaleDate?.toISOString()}`,
    );

    if (!auctionSaleDate) {
      this.logger.warn(`[${auctionNo}] 매각기일 정보가 없어 '정지/취소' 모의 입찰 처리를 건너뜁니다.`);
      return;
    }

    const pointsToRefund = this.mockBidPointsRefundOnCancel;
    const experiencePointsToGrant = this.mockBidXpGrantOnCancel;

    const targetSaleDateStart = new Date(auctionSaleDate.getFullYear(), auctionSaleDate.getMonth(), auctionSaleDate.getDate());
    const targetSaleDateEnd = new Date(auctionSaleDate.getFullYear(), auctionSaleDate.getMonth(), auctionSaleDate.getDate() + 1);

    const mockBidsToProcess = await this.prisma.mockBid.findMany({
      where: {
        auctionNo: auctionNo,
        auction_sale_date: {
          gte: targetSaleDateStart,
          lt: targetSaleDateEnd,
        },
        isProcessed: false,
      },
      select: { id: true, userId: true },
    });

    if (mockBidsToProcess.length === 0) {
      this.logger.log(`[${auctionNo}] [${targetSaleDateStart.toISOString().split('T')[0]}] '정지/취소' 결과로 처리할 모의 입찰 내역이 없습니다.`);
      return;
    }

    this.logger.log(
      `[${auctionNo}] [${targetSaleDateStart.toISOString().split('T')[0]}] ${mockBidsToProcess.length}건의 모의 입찰을 '정지/취소' 결과로 처리합니다. (포인트 ${pointsToRefund} 환불, 경험치 ${experiencePointsToGrant} 지급)`,
    );

    try {
      await this.prisma.$transaction(async (tx) => {
        for (const bid of mockBidsToProcess) {
          await tx.mockBid.update({
            where: { id: bid.id },
            data: {
              isProcessed: true,
              rank: -1,
              earnedExperiencePoints: experiencePointsToGrant,
            },
          });

          await tx.user.update({
            where: { id: bid.userId },
            data: {
              points: { increment: pointsToRefund },
              experiencePoints: { increment: experiencePointsToGrant },
            },
          });
        }
      });
      this.logger.log(
        `[${auctionNo}] [${targetSaleDateStart.toISOString().split('T')[0]}] '정지/취소' 결과 모의 입찰 처리 (포인트 환불, 경험치 지급) 완료.`,
      );
    } catch (error) {
      this.logger.error(
        `[${auctionNo}] [${targetSaleDateStart.toISOString().split('T')[0]}] '정지/취소' 결과 모의 입찰 처리 중 오류: ${error.message}`,
        error.stack,
      );
    }
  }
} 