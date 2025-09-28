import { Injectable } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';
import { ProductInfo, ProductType } from '@prisma/client';

const DEFAULT_PRODUCTS = [
  // Point Products
  {
    productId: 'point_100',
    type: ProductType.POINT,
    name: '100포인트',
    description: '100포인트 충전',
    value: 100,
    planId: null,
    planTier: null,
    features: [],
  },
  {
    productId: 'point_550',
    type: ProductType.POINT,
    name: '550포인트 (10% 보너스)',
    description: '500포인트 + 보너스 50포인트',
    value: 550,
    planId: null,
    planTier: null,
    features: [],
  },
  {
    productId: 'point_1200',
    type: ProductType.POINT,
    name: '1200포인트 (20% 보너스)',
    description: '1000포인트 + 보너스 200포인트',
    value: 1200,
    planId: null,
    planTier: null,
    features: [],
  },
  // Subscription Products
  {
    productId: 'subscription_monthly_basic',
    type: ProductType.SUBSCRIPTION,
    name: '베이직 플랜',
    description: '월간 구독 베이직 플랜입니다.',
    value: 9900, // 원화 가격
    planId: 'monthly-basic',
    planTier: 'BASIC',
    features: ['모의입찰 무제한', '관심차량 등록 10개'],
  },
];

@Injectable()
export class ProductsService {
  constructor(private prisma: PrismaService) {}

  async findAll(): Promise<ProductInfo[]> {
    const count = await this.prisma.productInfo.count();
    if (count === 0) {
      console.log('No products found, seeding default products...');
      await this.seedProducts();
    }
    return this.prisma.productInfo.findMany();
  }

  private async seedProducts(): Promise<void> {
    await this.prisma.productInfo.createMany({
      data: DEFAULT_PRODUCTS,
      skipDuplicates: true,
    });
    console.log('Default products seeded.');
  }
}
