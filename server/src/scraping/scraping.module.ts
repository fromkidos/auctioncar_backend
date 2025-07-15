import { Module } from '@nestjs/common';
import { ScrapingService } from './scraping.service';
import { CrawlingService } from './crawling.service';
import { PrismaService } from '../prisma/prisma.service';
import { ScrapingController } from './scraping.controller';

@Module({
  providers: [ScrapingService, CrawlingService, PrismaService],
  controllers: [ScrapingController],
  exports: [ScrapingService],
})
export class ScrapingModule {}
