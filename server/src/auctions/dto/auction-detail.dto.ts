import {
  AuctionBaseInfo,
  AuctionDetailInfo,
  DateHistory,
  SimilarSale,
  AuctionAnalysisAccess,
} from '@prisma/client';
import { CourtInfoDto } from './court-info.dto';

export class AuctionDetailDto {
  baseInfo: any; // AuctionBaseInfo와 관련된 DTO로 변환될 수 있음
  detailInfo: AuctionDetailInfo | null;
  dateHistories: DateHistory[];
  similarSales: SimilarSale[];
  analysisAccesses: AuctionAnalysisAccess[];
  isFavorite: boolean;
  courtInfo: CourtInfoDto | null;
} 