import { AuctionAppraisalSummary, AuctionResult } from "@prisma/client";

export class AuctionListItemDto {
  id: string;
  case_year: number;
  case_number: string;
  item_no: number;
  court_name: string;
  appraisal_price: string | null;
  min_bid_price: string | null;
  min_bid_price_2: string | null;
  sale_date: Date | string | null;
  status: string | null;
  car_name: string | null;
  car_model_year: number | null;
  car_reg_number: string | null;
  car_mileage: number | null;
  car_fuel: string | null;
  car_transmission: string | null;
  car_type: string | null;
  manufacturer: string | null;
  total_photo_count: number;
  appraisalSummary: AuctionAppraisalSummary | null;
  auctionResult: AuctionResult | null;
  // 필요시 관계형 데이터도 추가
} 