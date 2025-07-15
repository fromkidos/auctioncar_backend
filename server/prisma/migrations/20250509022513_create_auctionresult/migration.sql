/*
  Warnings:

  - You are about to drop the column `title` on the `AuctionResult` table. All the data in the column will be lost.
  - You are about to drop the column `usage` on the `AuctionResult` table. All the data in the column will be lost.

*/
-- DropIndex
DROP INDEX "AuctionResult_usage_idx";

-- AlterTable
ALTER TABLE "AuctionResult" DROP COLUMN "title",
DROP COLUMN "usage",
ADD COLUMN     "car_model_year" INTEGER,
ADD COLUMN     "car_name" TEXT,
ADD COLUMN     "car_type" TEXT;

-- CreateIndex
CREATE INDEX "AuctionResult_car_type_idx" ON "AuctionResult"("car_type");

-- CreateIndex
CREATE INDEX "AuctionResult_car_name_idx" ON "AuctionResult"("car_name");

-- CreateIndex
CREATE INDEX "AuctionResult_car_model_year_idx" ON "AuctionResult"("car_model_year");
