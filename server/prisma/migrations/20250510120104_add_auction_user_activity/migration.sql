-- CreateTable
CREATE TABLE "AuctionUserActivity" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "auctionNo" TEXT NOT NULL,
    "viewCount" INTEGER NOT NULL DEFAULT 0,
    "lastViewed" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "isFavorite" BOOLEAN NOT NULL DEFAULT false,

    CONSTRAINT "AuctionUserActivity_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "AuctionUserActivity_userId_idx" ON "AuctionUserActivity"("userId");

-- CreateIndex
CREATE INDEX "AuctionUserActivity_auctionNo_idx" ON "AuctionUserActivity"("auctionNo");

-- CreateIndex
CREATE INDEX "AuctionUserActivity_isFavorite_idx" ON "AuctionUserActivity"("isFavorite");

-- CreateIndex
CREATE UNIQUE INDEX "AuctionUserActivity_userId_auctionNo_key" ON "AuctionUserActivity"("userId", "auctionNo");

-- AddForeignKey
ALTER TABLE "AuctionUserActivity" ADD CONSTRAINT "AuctionUserActivity_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "AuctionUserActivity" ADD CONSTRAINT "AuctionUserActivity_auctionNo_fkey" FOREIGN KEY ("auctionNo") REFERENCES "AuctionBaseInfo"("auction_no") ON DELETE CASCADE ON UPDATE CASCADE;
