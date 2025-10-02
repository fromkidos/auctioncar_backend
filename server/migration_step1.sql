-- 1단계: total_photo_count 컬럼 추가
ALTER TABLE "AuctionBaseInfo" ADD COLUMN "total_photo_count" INTEGER DEFAULT 0;

-- 2단계: 기존 representative_photo_index 데이터를 total_photo_count로 이전
-- (PhotoURL 테이블에서 실제 사진 개수를 계산하여 업데이트)
UPDATE "AuctionBaseInfo" 
SET "total_photo_count" = (
    SELECT COUNT(*) 
    FROM "PhotoURL" 
    WHERE "PhotoURL"."auction_no" = "AuctionBaseInfo"."auction_no"
);
