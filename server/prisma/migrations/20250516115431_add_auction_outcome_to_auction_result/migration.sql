-- AlterTable
ALTER TABLE "AuctionResult" ADD COLUMN     "auction_outcome" TEXT;

-- CreateIndex
CREATE INDEX "AuctionResult_auction_outcome_idx" ON "AuctionResult"("auction_outcome");
