/*
  Warnings:

  - You are about to drop the column `current_round` on the `AuctionBaseInfo` table. All the data in the column will be lost.
  - You are about to drop the column `auction_round` on the `MockBid` table. All the data in the column will be lost.
  - A unique constraint covering the columns `[userId,auctionNo,auction_sale_date]` on the table `MockBid` will be added. If there are existing duplicate values, this will fail.
  - Added the required column `auction_sale_date` to the `MockBid` table without a default value. This is not possible if the table is not empty.

*/
-- DropIndex
DROP INDEX "AuctionBaseInfo_current_round_idx";

-- DropIndex
DROP INDEX "MockBid_auction_round_idx";

-- DropIndex
DROP INDEX "MockBid_userId_auctionNo_auction_round_key";

-- AlterTable
ALTER TABLE "AuctionBaseInfo" DROP COLUMN "current_round";

-- AlterTable
ALTER TABLE "MockBid" DROP COLUMN "auction_round",
ADD COLUMN     "auction_sale_date" TIMESTAMP(3) NOT NULL;

-- CreateIndex
CREATE INDEX "MockBid_auction_sale_date_idx" ON "MockBid"("auction_sale_date");

-- CreateIndex
CREATE UNIQUE INDEX "MockBid_userId_auctionNo_auction_sale_date_key" ON "MockBid"("userId", "auctionNo", "auction_sale_date");
