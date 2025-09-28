import { IsString, IsNumber, IsNotEmpty, IsOptional } from 'class-validator';

export class VerifyPurchaseDto {
  @IsString()
  @IsNotEmpty()
  productId: string;

  @IsString()
  @IsNotEmpty()
  purchaseToken: string;

  @IsNumber()
  purchaseTime: number;

  @IsString()
  @IsNotEmpty()
  orderId: string;

  @IsString()
  @IsNotEmpty()
  signature: string;

  @IsString()
  @IsNotEmpty()
  originalJson: string;

  @IsString()
  @IsOptional()
  packageName?: string;

  @IsString()
  @IsOptional()
  planId?: string; // 구독 상품의 요금제 ID
}
