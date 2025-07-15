import { IsString, IsBoolean, IsOptional } from 'class-validator';

export class AuctionUserActivityDto {
  userId: string;
  auctionNo: string;
  viewCount: number;
  lastViewed: Date;
  isFavorite: boolean;
}

export class UpdateAuctionUserActivityDto {
  @IsString()
  userId: string;

  @IsString()
  auctionNo: string;

  @IsBoolean()
  @IsOptional()
  isFavorite?: boolean;
}

export class IncrementAuctionViewDto {
  userId: string;
  auctionNo: string;
} 