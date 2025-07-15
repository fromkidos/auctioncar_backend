import { Controller, Get, Param, Query, Patch, Body, Logger } from '@nestjs/common';
import { AuctionsService } from './auctions.service';
import { UpdateAuctionUserActivityDto } from './dto/auction-user-activity.dto';
import { AuctionDetailDto } from './dto/auction-detail.dto';

import { AuctionListItemDto } from './dto/auction-list-item.dto';
import { AuctionHomeSummaryDto } from './dto/auction-home-summary.dto';

@Controller('auctions')
export class AuctionsController {
  private readonly logger = new Logger(AuctionsController.name);

  constructor(private readonly auctionsService: AuctionsService) {}

  @Get('ongoing')
  async findOngoingAuctions(): Promise<AuctionListItemDto[]> {
    try {
      return await this.auctionsService.findOngoingAuctions();
    } catch (error) {
      this.logger.error('[findOngoingAuctions] Error:', error);
      throw error;
    }
  }

  @Get('home-summary')
  async getHomeSummary(@Query('userId') userId: string): Promise<AuctionHomeSummaryDto> {
    try {
      return await this.auctionsService.getHomeSummary(userId);
    } catch (error) {
      this.logger.error('[getHomeSummary] Error:', error);
      throw error;
    }
  }

  @Get('detail/:auction_no')
  async getAuctionDetailWithView(
    @Param('auction_no') auctionNo: string,
    @Query('userId') userId?: string,
  ): Promise<AuctionDetailDto> {
    try {
      if (!userId) {
        throw new Error('User ID is required for auction detail access');
      }
      return await this.auctionsService.getAuctionDetailWithView(auctionNo, userId);
    } catch (error) {
      this.logger.error(`[getAuctionDetailWithView] Error for auction ${auctionNo}:`, error);
      throw error;
    }
  }

  @Get('health')
  getHealth(): { status: string; timestamp: Date } {
    return {
      status: 'ok',
      timestamp: new Date(),
    };
  }

  @Patch('user-activity')
  async updateAuctionUserActivity(@Body() dto: UpdateAuctionUserActivityDto) {
    try {
      return await this.auctionsService.updateAuctionFavorite(dto);
    } catch (error) {
      this.logger.error(`[updateAuctionUserActivity] Error:`, error);
      throw error;
    }
  }
} 