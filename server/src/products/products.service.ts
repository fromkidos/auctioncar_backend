import { Injectable } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';
import { ProductInfo } from '@prisma/client';

@Injectable()
export class ProductsService {
  constructor(private prisma: PrismaService) {}

  /**
   * 데이터베이스에서 모든 상품 정보를 조회합니다.
   * @returns {Promise<ProductInfo[]>} 상품 정보 배열
   */
  async findAll(): Promise<ProductInfo[]> {
    // DB에서 모든 ProductInfo를 찾아 반환합니다.
    return this.prisma.productInfo.findMany();
  }
}
