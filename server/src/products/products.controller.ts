import { Controller, Get } from '@nestjs/common';
import { ProductsService } from './products.service';
import { ProductInfo } from '@prisma/client';

@Controller('products')
export class ProductsController {
  constructor(private readonly productsService: ProductsService) {}

  @Get()
  async findAll(): Promise<ProductInfo[]> {
    return this.productsService.findAll();
  }
}
