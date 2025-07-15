/*
  Warnings:

  - The `sale_date` column on the `AuctionResult` table would be dropped and recreated. This will lead to data loss if there is data in the column.

*/
-- AlterTable
ALTER TABLE "AuctionResult" DROP COLUMN "sale_date",
ADD COLUMN     "sale_date" TIMESTAMP(3);

-- CreateIndex
CREATE INDEX "AuctionResult_sale_date_idx" ON "AuctionResult"("sale_date");
