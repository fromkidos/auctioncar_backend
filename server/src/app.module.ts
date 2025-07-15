import { Module } from '@nestjs/common';
import { AppController } from './app.controller';
import { AppService } from './app.service';
import { PrismaModule } from './prisma/prisma.module';
import { AuthModule } from './auth/auth.module';
import { ConfigModule, ConfigService } from '@nestjs/config';
import { AuctionsModule } from './auctions/auctions.module';
import { ScrapingModule } from './scraping/scraping.module';
import { MockBidsModule } from './mock-bids/mock-bids.module';

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
      envFilePath: [
        process.env.NODE_ENV === 'production' 
          ? '../.env.production'  // server/../.env.production
          : '../.env',           // server/../.env
        '.env', // fallback to local .env if exists
      ],
    }),
    PrismaModule,
    AuthModule,
    AuctionsModule,
    ScrapingModule,
    MockBidsModule,
  ],
  controllers: [AppController],
  providers: [AppService],
})
export class AppModule {}
