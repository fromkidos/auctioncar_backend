/*
  Warnings:

  - You are about to alter the column `appraisal_price` on the `AuctionBaseInfo` table. The data in that column could be lost. The data in that column will be cast from `Decimal(65,30)` to `Integer`.
  - You are about to alter the column `min_bid_price` on the `AuctionBaseInfo` table. The data in that column could be lost. The data in that column will be cast from `Decimal(65,30)` to `Integer`.
  - You are about to alter the column `claim_amount` on the `AuctionDetailInfo` table. The data in that column could be lost. The data in that column will be cast from `Decimal(65,30)` to `Integer`.
  - You are about to alter the column `min_bid_price` on the `DateHistory` table. The data in that column could be lost. The data in that column will be cast from `Decimal(65,30)` to `Integer`.
  - You are about to alter the column `avg_appraisal_price` on the `SimilarSale` table. The data in that column could be lost. The data in that column will be cast from `Decimal(65,30)` to `Integer`.
  - You are about to alter the column `avg_sale_price` on the `SimilarSale` table. The data in that column could be lost. The data in that column will be cast from `Decimal(65,30)` to `Integer`.

*/
-- AlterTable
ALTER TABLE "AuctionBaseInfo" ALTER COLUMN "appraisal_price" SET DATA TYPE INTEGER,
ALTER COLUMN "min_bid_price" SET DATA TYPE INTEGER;

-- AlterTable
ALTER TABLE "AuctionDetailInfo" ALTER COLUMN "claim_amount" SET DATA TYPE INTEGER;

-- AlterTable
ALTER TABLE "DateHistory" ALTER COLUMN "min_bid_price" SET DATA TYPE INTEGER;

-- AlterTable
ALTER TABLE "SimilarSale" ALTER COLUMN "avg_appraisal_price" SET DATA TYPE INTEGER,
ALTER COLUMN "avg_sale_price" SET DATA TYPE INTEGER;
