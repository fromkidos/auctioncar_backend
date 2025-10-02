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
  photoUrls: Array<{ photo_index: number; image_path_or_url: string | null; }>;
  similarSales: SimilarSale[];
  analysisAccesses: AuctionAnalysisAccess[];
  isFavorite: boolean;
  courtInfo: CourtInfoDto | null;
} 