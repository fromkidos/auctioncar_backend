import { Controller, Post, Body, UseGuards, Request, Req, HttpCode, UsePipes, ValidationPipe, Get } from '@nestjs/common';
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
  @UsePipes(new ValidationPipe({ 
    transform: true, 
    whitelist: true, 
    forbidNonWhitelisted: false // 추가 필드 허용
  }))
  async verifyPurchase(@Req() req, @Body() purchaseDto: VerifyPurchaseDto) {
    console.log('[Billing] Authorization:', req.headers?.authorization ?? '(none)');
    console.log('[Billing] req.user:', req.user ?? '(none)');
    console.log('[Billing] purchaseDto:', {
      productId: purchaseDto.productId,
      orderId: purchaseDto.orderId,
      packageName: purchaseDto.packageName || '(none)',
      purchaseToken: purchaseDto.purchaseToken ? `${purchaseDto.purchaseToken.slice(0, 10)}...` : '(none)'
    });
    
    // 설정 정보 로깅 (디버깅용)
    const configInfo = this.billingService.getConfigInfo();
    console.log('[Billing] Service configuration:', configInfo);
    
    try {
      const result = await this.billingService.verifyPurchase(req.user as UserModel, purchaseDto);
      console.log('[Billing] Purchase verification successful for user:', req.user?.id);
      return result;
    } catch (error) {
      console.error('[Billing] Purchase verification failed for user:', req.user?.id, 'Error:', error.message);
      console.error('[Billing] Config at time of error:', configInfo);
      throw error;
    }
  }

  @Get('products')
  async getProducts(@Req() req) {
    const type = req.query?.type; // ?type=POINT 또는 ?type=SUBSCRIPTION
    const planTier = req.query?.planTier; // ?planTier=BASIC 또는 ?planTier=PREMIUM
    return this.billingService.getProducts(type, planTier);
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
