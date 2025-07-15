import { ApiProperty } from '@nestjs/swagger';
import { IsNotEmpty, IsString, IsNumber, Min, IsDateString } from 'class-validator';

export class CreateMockBidDto {
  @ApiProperty({
    description: '모의 입찰을 진행할 경매 번호 (예: "2024타경12345-1")',
    example: '2024타경12345-1',
  })
  @IsNotEmpty()
  @IsString()
  auctionNo: string;

  @ApiProperty({
    description: '모의 입찰 대상 경매의 매각기일 (ISO 8601 형식, 예: YYYY-MM-DD 또는 YYYY-MM-DDTHH:mm:ss.sssZ)',
    example: '2024-08-15', // 또는 '2024-08-15T10:00:00.000Z'
  })
  @IsNotEmpty()
  @IsDateString()
  auction_sale_date: string; // 클라이언트에서 이 경매의 정확한 sale_date를 보내야 함

  @ApiProperty({
    description: '모의 입찰 금액',
    example: 15000000,
    type: Number,
  })
  @IsNotEmpty()
  @IsNumber()
  @Min(0) // 음수 입찰 방지, 실제 최소 입찰가는 서비스 로직에서 검증
  bidAmount: number;
} 