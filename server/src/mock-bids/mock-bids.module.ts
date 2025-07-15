import { Module } from '@nestjs/common';
import { MockBidsController } from './mock-bids.controller';
import { MockBidsService } from './mock-bids.service';
import { PrismaModule } from '../prisma/prisma.module'; // PrismaModule 경로 확인
// import { AuthModule } from '../auth/auth.module'; // 실제 AuthModule 경로로 수정 필요 (JWT 전략 등 포함)

@Module({
  imports: [
    PrismaModule,
    // AuthModule, // JWT 가드 및 전략 사용을 위해 AuthModule 임포트 (실제 경로 확인 필요)
  ],
  controllers: [MockBidsController],
  providers: [MockBidsService],
  exports: [MockBidsService], // 다른 모듈에서 MockBidsService를 사용해야 할 경우
})
export class MockBidsModule {} 