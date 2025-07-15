-- AlterEnum
ALTER TYPE "PointTransactionType" ADD VALUE 'MOCK_BID_WINNER_REWARD';

-- AddForeignKey
ALTER TABLE "AuctionResult" ADD CONSTRAINT "AuctionResult_auction_no_fkey" FOREIGN KEY ("auction_no") REFERENCES "AuctionBaseInfo"("auction_no") ON DELETE RESTRICT ON UPDATE CASCADE;
