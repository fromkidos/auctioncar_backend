export class VerifyPurchaseDto {
  productId: string;
  purchaseToken: string;
  purchaseTime: number;
  orderId: string;
  signature: string;
  originalJson: string;
}
