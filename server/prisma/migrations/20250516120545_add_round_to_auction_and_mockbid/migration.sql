/*
  Warnings:

  - A unique constraint covering the columns `[userId,auctionNo,auction_round]` on the table `MockBid` will be added. If there are existing duplicate values, this will fail.
  - Added the required column `auction_round` to the `MockBid` table without a default value. This is not possible if the table is not empty.

*/
-- DropIndex
DROP INDEX "MockBid_userId_auctionNo_key";

-- AlterTable
ALTER TABLE "AuctionBaseInfo" ADD COLUMN     "current_round" INTEGER NOT NULL DEFAULT 0;

-- AlterTable
ALTER TABLE "MockBid" ADD COLUMN     "auction_round" INTEGER NOT NULL;

-- CreateIndex
CREATE INDEX "AuctionBaseInfo_current_round_idx" ON "AuctionBaseInfo"("current_round");

-- CreateIndex
CREATE INDEX "MockBid_auction_round_idx" ON "MockBid"("auction_round");

-- CreateIndex
CREATE UNIQUE INDEX "MockBid_userId_auctionNo_auction_round_key" ON "MockBid"("userId", "auctionNo", "auction_round");
