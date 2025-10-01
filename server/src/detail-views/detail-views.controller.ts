import { Body, Controller, Get, Post, Req, UseGuards } from '@nestjs/common';
import { JwtAuthGuard } from '../auth/guards/jwt-auth.guard';
import { DetailViewsService } from './detail-views.service';

@Controller('detail-views')
@UseGuards(JwtAuthGuard)
export class DetailViewsController {
  constructor(private readonly service: DetailViewsService) {}

  @Get('status')
  async getStatus(@Req() req) {
    return this.service.getStatus(req.user.id);
  }

  @Post('consume')
  async consume(@Req() req, @Body() body: { amount?: number }) {
    return this.service.consume(req.user.id, body?.amount ?? 1);
  }

  @Post('reward')
  async reward(@Req() req, @Body() body: { views?: number }) {
    return this.service.reward(req.user.id, body?.views ?? 5);
  }

  @Post('purchase')
  async purchase(@Req() req, @Body() body: { costPoints?: number; addViews?: number }) {
    const cost = body?.costPoints ?? 10;
    const add = body?.addViews ?? 10;
    return this.service.purchaseWithPoints(req.user.id, cost, add);
  }
}


