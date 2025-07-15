-- AlterTable
ALTER TABLE "User" ADD COLUMN     "experiencePoints" INTEGER NOT NULL DEFAULT 0;

-- CreateTable
CREATE TABLE "MockBid" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "auctionNo" TEXT NOT NULL,
    "bidAmount" BIGINT NOT NULL,
    "bidTime" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "isProcessed" BOOLEAN NOT NULL DEFAULT false,
    "rank" INTEGER,
    "earnedExperiencePoints" INTEGER,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "MockBid_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "MockBid_userId_idx" ON "MockBid"("userId");

-- CreateIndex
CREATE INDEX "MockBid_auctionNo_idx" ON "MockBid"("auctionNo");

-- CreateIndex
CREATE INDEX "MockBid_bidTime_idx" ON "MockBid"("bidTime");

-- CreateIndex
CREATE INDEX "MockBid_isProcessed_idx" ON "MockBid"("isProcessed");

-- CreateIndex
CREATE UNIQUE INDEX "MockBid_userId_auctionNo_key" ON "MockBid"("userId", "auctionNo");

-- AddForeignKey
ALTER TABLE "MockBid" ADD CONSTRAINT "MockBid_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "MockBid" ADD CONSTRAINT "MockBid_auctionNo_fkey" FOREIGN KEY ("auctionNo") REFERENCES "AuctionBaseInfo"("auction_no") ON DELETE CASCADE ON UPDATE CASCADE;
