import { AuctionListItemDto } from './auction-list-item.dto';
import { AuctionResult as PrismaAuctionResult, MockBid as PrismaMockBid } from '@prisma/client';
import { CourtInfoDto } from './court-info.dto';

export interface RecentAuctionResultWithDetailsDto extends PrismaAuctionResult {
  auctionBaseInfo: AuctionListItemDto | null;
}

export interface MyMockBidWithAuctionDetailsDto extends PrismaMockBid {
  auctionBaseInfo: AuctionListItemDto | null;
}

export class AuctionHomeSummaryDto {
  popular: AuctionListItemDto[];
  myFavorites: AuctionListItemDto[];
  myViewed: AuctionListItemDto[];
  myMockBids: MyMockBidWithAuctionDetailsDto[];

  newlyRegisteredAuctions: AuctionListItemDto[];
  recentAuctionResults: RecentAuctionResultWithDetailsDto[];
  courtInfos: CourtInfoDto[];
} 