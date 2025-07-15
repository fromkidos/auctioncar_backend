import { Controller, Post, Body, Req, UseGuards } from '@nestjs/common';
import { ScrapingService } from './scraping.service';
import { PrismaService } from '../prisma/prisma.service';
import { ConfigService } from '@nestjs/config';
import { AuthGuard } from '@nestjs/passport';

@Controller('scraping')
export class ScrapingController {
  constructor(
    private readonly scrapingService: ScrapingService,
    private readonly prisma: PrismaService,
    private readonly configService: ConfigService,
  ) {}

  @Post('report')
  @UseGuards(AuthGuard('jwt'))
  async getReport(@Body() body: { auctionNo: string }, @Req() req) {
    console.log('[ScrapingController] /scraping/report called', body, req.user);
    try {
      const userId = req.user.id;
      const { auctionNo } = body;
      const result = await this.scrapingService.getOrCrawlReportWithAuctionNo(userId, auctionNo);
      console.log('[ScrapingController] getOrCrawlReportWithAuctionNo result:', result);
      return result;
    } catch (e) {
      console.error('[ScrapingController] Error:', e);
      throw e;
    }
  }
} 