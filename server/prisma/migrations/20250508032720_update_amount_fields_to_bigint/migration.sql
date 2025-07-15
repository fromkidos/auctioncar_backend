-- AlterTable
ALTER TABLE "AuctionBaseInfo" ALTER COLUMN "appraisal_price" SET DATA TYPE BIGINT,
ALTER COLUMN "min_bid_price" SET DATA TYPE BIGINT,
ALTER COLUMN "min_bid_price_2" SET DATA TYPE BIGINT;

-- AlterTable
ALTER TABLE "AuctionDetailInfo" ALTER COLUMN "claim_amount" SET DATA TYPE BIGINT;

-- AlterTable
ALTER TABLE "DateHistory" ALTER COLUMN "min_bid_price" SET DATA TYPE BIGINT;

-- AlterTable
ALTER TABLE "SimilarSale" ALTER COLUMN "avg_appraisal_price" SET DATA TYPE BIGINT,
ALTER COLUMN "avg_sale_price" SET DATA TYPE BIGINT;
