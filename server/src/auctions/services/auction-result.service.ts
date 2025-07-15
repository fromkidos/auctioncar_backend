import { Injectable, Logger, InternalServerErrorException, BadRequestException } from '@nestjs/common';
import { PrismaService } from '../../prisma/prisma.service';
import { UpdateAuctionResultDto } from '../dto/update-auction-result.dto';
import { AuctionRankingService } from './auction-ranking.service';

import { AuctionResult, Prisma } from '@prisma/client';
import { PrismaClientKnownRequestError } from '@prisma/client/runtime/library';

@Injectable()
export class AuctionResultService {
  private readonly logger = new Logger(AuctionResultService.name);

  constructor(
    private readonly prisma: PrismaService,
    private readonly auctionRankingService: AuctionRankingService,
  ) {}

  async updateAuctionResult(
    dto: UpdateAuctionResultDto,
  ): Promise<AuctionResult> {
    this.logger.log(`[${dto.auction_no}] [${dto.sale_date}] 낙찰 결과 업데이트/생성 시도.`);

    if (!dto.sale_date) {
      this.logger.error(`[${dto.auction_no}] sale_date가 제공되지 않았습니다. 처리를 중단합니다.`);
      throw new BadRequestException(`[${dto.auction_no}] sale_date가 누락되었습니다.`);
    }
    const newSaleDate = new Date(dto.sale_date);

    const existingAuctionResult = await this.prisma.auctionResult.findUnique({
      where: { auction_no: dto.auction_no },
    });

    if (existingAuctionResult) {
      // 기존 데이터가 존재할 경우
      const existingSaleDate = existingAuctionResult.sale_date;

      if (!existingSaleDate || newSaleDate >= existingSaleDate) {
        // 기존 sale_date가 없거나, 새 sale_date가 최신(거나 같을) 경우 -> 업데이트
        this.logger.log(
          `[${dto.auction_no}] 기존 결과 업데이트 진행. 새 sale_date (${newSaleDate.toISOString()})가 기존 (${existingSaleDate?.toISOString() || 'N/A'})보다 최신이거나 같음.`,
        );
        
        const updateData = this.prepareDatabaseData(dto, newSaleDate);
        try {
          const result = await this.prisma.$transaction(async (tx) => {
            const updatedResult = await tx.auctionResult.update({
              where: { auction_no: dto.auction_no },
              data: updateData,
            });
            await this.updateAuctionBaseInfoStatus(tx, updatedResult, dto.auction_no);
            return updatedResult;
          });
          
          await this.handlePostResultOperations(result, true);
          return result;
        } catch (error) {
            const msg = error instanceof Error ? error.message : 'Unknown error';
            this.logger.error(
              `[${dto.auction_no}] 기존 낙찰 결과 업데이트 중 DB 오류 발생: ${msg}`,
              error instanceof Error ? error.stack : undefined,
            );
            if (error instanceof PrismaClientKnownRequestError) {
                this.logger.warn(`PrismaClientKnownRequestError 발생 (code: ${error.code})`);
            }
            throw new InternalServerErrorException(`[${dto.auction_no}] 기존 낙찰 결과 업데이트 중 서버 오류가 발생했습니다.`);
        }
      } else {
        // 새 sale_date가 기존 것보다 과거임 -> 업데이트 안 함, 기존 데이터 반환
        this.logger.log(
          `[${dto.auction_no}] 업데이트 건너뜀. 새 sale_date (${newSaleDate.toISOString()})가 기존 (${existingSaleDate.toISOString()})보다 과거임. 기존 결과 반환.`,
        );
        return existingAuctionResult;
      }
    } else {
      // 기존 데이터가 없음 -> 새로 생성
      this.logger.log(`[${dto.auction_no}] 새 낙찰 결과 생성. sale_date: ${newSaleDate.toISOString()}`);
      
      // ⭐️ 추가: AuctionResult를 생성하기 전, AuctionBaseInfo가 실제로 존재하는지 확인
      const auctionBaseInfo = await this.prisma.auctionBaseInfo.findUnique({
        where: { auction_no: dto.auction_no },
        select: { auction_no: true }, // 필요한 필드만 선택하여 효율성 증대
      });

      if (!auctionBaseInfo) {
        this.logger.error(`[${dto.auction_no}]에 해당하는 AuctionBaseInfo를 찾을 수 없어 AuctionResult를 생성할 수 없습니다.`);
        throw new BadRequestException(`[${dto.auction_no}]는 존재하지 않는 경매 정보입니다.`);
      }

      const commonData = this.prepareDatabaseData(dto, newSaleDate);
      const createData: Prisma.AuctionResultCreateInput = {
        ...commonData,
        auction: {
          connect: { auction_no: dto.auction_no },
        },
      };

      try {
        const result = await this.prisma.$transaction(async (tx) => {
          const createdResult = await tx.auctionResult.create({
            data: createData,
          });
          await this.updateAuctionBaseInfoStatus(tx, createdResult, dto.auction_no);
          return createdResult;
        });

        await this.handlePostResultOperations(result, false);
        return result;
      } catch (error) {
        const msg = error instanceof Error ? error.message : 'Unknown error';
        this.logger.error(
            `[${dto.auction_no}] 새 낙찰 결과 생성 중 DB 오류 발생: ${msg}`,
            error instanceof Error ? error.stack : undefined,
        );
        if (error instanceof PrismaClientKnownRequestError) {
            this.logger.warn(`PrismaClientKnownRequestError 발생 (code: ${error.code})`);
            if (error.code === 'P2002') {
                this.logger.error(`[${dto.auction_no}] 데이터 생성 시 유니크 제약 조건 위반.`);
                 throw new InternalServerErrorException(`[${dto.auction_no}] 데이터 생성 중 유니크 제약 조건 위반 오류.`);
            } else if (error.code === 'P2025') {
              // Prisma의 P2025 오류(연관 레코드 없음)에 대한 명시적 처리
              this.logger.error(`[${dto.auction_no}] 새 낙찰 결과 생성 중 관련 AuctionBaseInfo를 찾지 못했습니다.`, error.stack);
              throw new InternalServerErrorException(`[${dto.auction_no}] 경매 기본 정보를 찾을 수 없어 결과를 생성할 수 없습니다.`);
            }
        }
        throw new InternalServerErrorException(`[${dto.auction_no}] 새 낙찰 결과 생성 중 서버 오류가 발생했습니다.`);
      }
    }
  }

  // 데이터 준비 로직을 별도 메소드로 분리, saleDate 인자 추가
  private prepareDatabaseData(dto: UpdateAuctionResultDto, saleDateForDb: Date) {
    return {
        car_name: dto.car_name ?? null,
        car_model_year: dto.car_model_year ?? null,
        car_type: dto.car_type ?? null,
        appraisal_value:
          dto.appraisal_value != null ? BigInt(dto.appraisal_value) : null,
        min_bid_price:
          dto.min_bid_price != null ? BigInt(dto.min_bid_price) : null,
        sale_date: saleDateForDb, // DTO의 sale_date 대신 변환된 Date 객체 사용
        sale_price:
          dto.sale_price != null ? BigInt(dto.sale_price) : null,
        bid_rate: dto.bid_rate ?? null,
        auction_outcome: dto.auction_outcome ?? null,
      };
  }

  // 트랜잭션 내에서 AuctionBaseInfo 상태 업데이트 로직 분리 (기존과 동일)
  private async updateAuctionBaseInfoStatus(
    tx: Prisma.TransactionClient, // Prisma.TransactionClient 타입 명시
    auctionResult: AuctionResult,
    auctionNo: string
  ) {
    if (
      auctionResult.sale_price !== null &&
      auctionResult.sale_price !== undefined
    ) {
      try {
        const updatedBaseInfo = await tx.auctionBaseInfo.updateMany({
          where: {
            auction_no: auctionNo,
          },
          data: {
            status: auctionResult.auction_outcome === '매각' || auctionResult.auction_outcome === '낙찰' ? '매각' : auctionResult.auction_outcome ?? '상태확인필요',
          },
        });

        if (updatedBaseInfo.count > 0) {
          this.logger.log(
            `[${auctionNo}] AuctionBaseInfo status를 '${auctionResult.auction_outcome}' 기반으로 업데이트했습니다 (트랜잭션 내).`,
          );
        } else {
          this.logger.log(
            `[${auctionNo}] AuctionBaseInfo status를 업데이트하지 않았습니다 (해당 경매번호를 찾을 수 없거나 조건 불일치) (트랜잭션 내).`,
          );
        }
      } catch (error) {
        this.logger.error(
          `[${auctionNo}] AuctionBaseInfo status 업데이트 중 오류 발생 (트랜잭션 내): ${error.message}`,
          error instanceof Error ? error.stack : undefined,
        );
        throw error; // 트랜잭션 롤백을 위해 오류 다시 throw
      }
    }
  }

  private async handlePostResultOperations(
    auctionResult: AuctionResult,
    isUpdate: boolean,
  ) {
    const operationType = isUpdate ? "업데이트" : "생성";
    const saleDateString = auctionResult.sale_date ? auctionResult.sale_date.toISOString().split('T')[0] : 'N/A';
    const auctionOutcome = auctionResult.auction_outcome;

    this.logger.log(
        `[${auctionResult.auction_no}] [${saleDateString}] 경매 결과(${auctionOutcome}) ${operationType} 후처리 작업 시작.`
    );

    const winningOutcomes = ['매각', '낙찰'];
    const cancellationOutcomes = ['정지', '취소']; // 필요시 '중지' 등 유사 상태 추가

    if (auctionOutcome && winningOutcomes.includes(auctionOutcome)) {
      // --- 매각 시 처리 ---
      if (auctionResult.sale_price != null) {
        this.logger.log(
          `[${auctionResult.auction_no}] [${saleDateString}] '매각/낙찰'로 판단되어 순위 처리 및 경험치 지급 로직 호출. 실제 낙찰가: ${auctionResult.sale_price}`,
        );
        this.auctionRankingService
          .processAuctionRankings(auctionResult.auction_no, Number(auctionResult.sale_price))
          .then(() =>
            this.logger.log(
              `[${auctionResult.auction_no}] [${saleDateString}] '매각/낙찰' 관련 모의 입찰 순위 처리 작업이 백그라운드로 시작되었습니다.`,
            ),
          )
          .catch((err) =>
            this.logger.error(
              `[${auctionResult.auction_no}] [${saleDateString}] '매각/낙찰' 관련 모의 입찰 순위 처리 중 오류: ${err.message}`,
              err.stack,
            ),
          );
      } else {
        this.logger.warn(
          `[${auctionResult.auction_no}] [${saleDateString}] 경매 결과는 '${auctionOutcome}'이지만, 실제 낙찰가(sale_price) 정보가 없어 순위 처리를 건너뜁니다. '유찰 및 기타'로 처리합니다.`,
        );
        await this.auctionRankingService.processUnsoldOrOtherOutcomes(
            auctionResult.auction_no,
            auctionResult.sale_date,
          );
      }
    } else if (auctionOutcome && cancellationOutcomes.includes(auctionOutcome)) {
      // --- 정지, 취소 시 처리 ---
      this.logger.log(
        `[${auctionResult.auction_no}] [${saleDateString}] '${auctionOutcome}'으로 판단되어 '정지/취소' 모의 입찰 처리 로직 호출.`,
      );
      await this.auctionRankingService.processCancellationOrSuspensionOutcomes(
        auctionResult.auction_no,
        auctionResult.sale_date,
      );
    } else {
      // --- 유찰 및 그 외 모든 경우 (auctionOutcome이 null 포함) 처리 ---
      this.logger.log(
        `[${auctionResult.auction_no}] [${saleDateString}] '${auctionOutcome || '결과값 없음'}'으로 판단되어 '유찰 및 기타' 모의 입찰 처리 로직 호출.`,
      );
      await this.auctionRankingService.processUnsoldOrOtherOutcomes(
        auctionResult.auction_no,
        auctionResult.sale_date,
      );
    }
  }
}
