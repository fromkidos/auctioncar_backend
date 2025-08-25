import { AuctionListItemDto } from './auction-list-item.dto';
import { AuctionResult, AuctionUserActivity, MockBid, AuctionResult as PrismaAuctionResult, MockBid as PrismaMockBid } from '@prisma/client';
import { CourtInfoDto } from './court-info.dto';

export class AuctionHomeSummaryDto {
  popular: AuctionListItemDto[];
  //myFavorites: string[];
  //myViewed: string[];
  myActivity: AuctionUserActivity[];
  myMockBids: MockBid[];

  newlyRegisteredAuctions: AuctionListItemDto[];
  recentAuctionResults: AuctionResult[];
  courtInfos: CourtInfoDto[];
} 