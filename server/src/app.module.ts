import { Module } from '@nestjs/common';
import { AppController } from './app.controller';
import { AppService } from './app.service';
import { PrismaModule } from './prisma/prisma.module';
import { AuthModule } from './auth/auth.module';
import { ConfigModule, ConfigService } from '@nestjs/config';
import { AuctionsModule } from './auctions/auctions.module';
import { ScrapingModule } from './scraping/scraping.module';
import { MockBidsModule } from './mock-bids/mock-bids.module';
import { BillingModule } from './billing/billing.module';
import { ProductsModule } from './products/products.module';
import { DetailViewsModule } from './detail-views/detail-views.module';

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
    BillingModule,
    ProductsModule,
    DetailViewsModule,
  ],
  controllers: [AppController],
  providers: [AppService],
})
export class AppModule {}
