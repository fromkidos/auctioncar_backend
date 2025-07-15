// src/auctions/dto/update-auction-result.dto.ts
import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import {
  IsString,
  IsNotEmpty,
  IsOptional,
  IsInt,
  IsNumber,
  IsDateString,
} from 'class-validator';

export class UpdateAuctionResultDto {
  @ApiProperty({ description: '경매 번호 (예: "2024타경128478-1")', example: '2024타경128478-1' })
  @IsString()
  @IsNotEmpty()
  auction_no: string;

  @ApiPropertyOptional({ description: '차량 이름', example: 'E220 CDI' })
  @IsOptional()
  @IsString()
  car_name?: string;

  @ApiPropertyOptional({ description: '차량 연식', example: 2014 })
  @IsOptional()
  @IsInt()
  car_model_year?: number;

  @ApiPropertyOptional({ description: '차량 종류', example: '승용차' })
  @IsOptional()
  @IsString()
  car_type?: string;

  @ApiPropertyOptional({ description: '감정평가액', example: 15000000 })
  @IsOptional()
  @IsNumber()
  appraisal_value?: number;

  @ApiPropertyOptional({ description: '최저매각가격', example: 10000000 })
  @IsOptional()
  @IsNumber()
  min_bid_price?: number;

  @ApiPropertyOptional({ description: '매각기일 (ISO 8601 형식)', example: '2024-08-15T10:00:00.000Z' })
  @IsOptional()
  @IsDateString()
  sale_date?: string;

  @ApiPropertyOptional({ description: '매각대금 (실제 낙찰가)', example: 12000000 })
  @IsOptional()
  @IsNumber()
  sale_price?: number;

  @ApiPropertyOptional({ description: '낙찰율', example: 80.0 })
  @IsOptional()
  @IsNumber()
  bid_rate?: number;

  @ApiPropertyOptional({ description: '매각 결과 (예: \'매각\', \'유찰\')', example: '매각', required: false })
  @IsOptional()
  @IsString()
  auction_outcome?: string;
}