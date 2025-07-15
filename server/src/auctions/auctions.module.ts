import { Module } from '@nestjs/common';
import { AuctionsController } from './auctions.controller'; // 기본 컨트롤러, 필요시 주석 해제 또는 사용
import { AuctionsService } from './auctions.service'; // 기본 서비스, 필요시 주석 해제 또는 사용
import { PrismaModule } from '../prisma/prisma.module'; // 경로 수정
import { ConfigModule } from '@nestjs/config'; // ConfigService를 사용하기 위해 import
import { MockBidsModule } from '../mock-bids/mock-bids.module'; // MockBidsModule 임포트 추가

import { AuctionResultInternalController } from './controllers/internal/auction-result-internal.controller';
import { AuctionResultService } from './services/auction-result.service';
import { AuctionRankingService } from './services/auction-ranking.service';

@Module({
  imports: [
    PrismaModule, 
    ConfigModule, // ConfigModule import 추가 (ApiKeyAuthGuard에서 ConfigService 사용)
    MockBidsModule, // MockBidsModule 임포트
  ],
  controllers: [
    AuctionsController, // 기존 컨트롤러 (필요시 사용) -> 주석 해제
    AuctionResultInternalController,
  ],
  providers: [
    AuctionsService, // 기존 서비스 (필요시 사용) -> 주석 해제
    AuctionResultService,
    AuctionRankingService,
  ],
  exports: [
    AuctionResultService, // 다른 모듈에서 호출할 가능성은 낮지만, 필요시 export
    AuctionRankingService,
    AuctionsService, // AuctionsService도 다른 곳에서 사용될 수 있으므로 export 추가 (선택 사항)
  ]
})
export class AuctionsModule {} 