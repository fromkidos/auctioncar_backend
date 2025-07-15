import { Module, Global } from '@nestjs/common';
import { PrismaService } from './prisma.service';

@Global() // PrismaService를 앱 전체에서 쉽게 주입받을 수 있도록 Global 모듈로 설정
@Module({
  providers: [PrismaService],
  exports: [PrismaService], // 다른 모듈에서 PrismaService를 사용하기 위해 export
})
export class PrismaModule {} 