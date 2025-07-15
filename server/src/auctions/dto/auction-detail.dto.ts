import { AuctionListItemDto } from './auction-list-item.dto';
import {
  AuctionAnalysisAccess,
  AuctionDetailInfo,
  DateHistory,
  PhotoURL,
  SimilarSale,
} from '@prisma/client';

export class AuctionDetailDto {
  baseInfo: AuctionListItemDto;
  detailInfo: AuctionDetailInfo | null;
  dateHistories: DateHistory[];
  similarSales: SimilarSale[];
  analysisAccesses: AuctionAnalysisAccess[];
  isFavorite: boolean;
  photoUrls: PhotoURL[];
} 