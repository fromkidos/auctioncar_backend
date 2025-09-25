import { IsString, IsNumber, IsNotEmpty } from 'class-validator';

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
}
