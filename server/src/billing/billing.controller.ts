import { Controller, Post, Body, UseGuards, Request, Req, HttpCode } from '@nestjs/common';
import { BillingService } from './billing.service';
import { VerifyPurchaseDto } from './dto/verify-purchase.dto';
import { User as UserModel } from '@prisma/client';
import { PubSubMessage } from './dto/rtdn.dto';
import { JwtAuthGuard } from '../auth/guards/jwt-auth.guard';

@Controller('billing')
export class BillingController {
  constructor(private readonly billingService: BillingService) {}

  @UseGuards(JwtAuthGuard)
  @Post('verify-purchase')
  async verifyPurchase(@Req() req, @Body() purchaseDto: VerifyPurchaseDto) {
    return this.billingService.verifyPurchase(req.user as UserModel, purchaseDto);
  }

  @Post('rtdn')
  @HttpCode(204) // 성공 시 No Content 응답
  async handleRtdn(@Body() body: PubSubMessage) {
    try {
      await this.billingService.handleRtdn(body);
    } catch (error) {
      // 에러가 발생하더라도 Google에 성공으로 응답해야 재시도를 막을 수 있음
      // 실제 에러는 로깅으로 처리
      this.billingService.getLogger().error('Error handling RTDN', error.stack);
    }
  }
}
