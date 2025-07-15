-- CreateTable
CREATE TABLE "User" (
    "id" TEXT NOT NULL,
    "provider" TEXT NOT NULL,
    "providerId" TEXT NOT NULL,
    "displayName" TEXT,
    "profileImageUrl" TEXT,
    "email" TEXT,
    "points" INTEGER NOT NULL DEFAULT 0,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "User_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "PointTransaction" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "type" TEXT NOT NULL,
    "amount" INTEGER NOT NULL,
    "balanceAfter" INTEGER NOT NULL,
    "description" TEXT,
    "relatedId" TEXT,
    "transactionDate" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "PointTransaction_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "AuctionAnalysisAccess" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "auctionNo" TEXT NOT NULL,
    "accessDate" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "pointTransactionId" TEXT,

    CONSTRAINT "AuctionAnalysisAccess_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "User_provider_providerId_key" ON "User"("provider", "providerId");

-- CreateIndex
CREATE INDEX "PointTransaction_userId_idx" ON "PointTransaction"("userId");

-- CreateIndex
CREATE INDEX "PointTransaction_type_idx" ON "PointTransaction"("type");

-- CreateIndex
CREATE UNIQUE INDEX "AuctionAnalysisAccess_pointTransactionId_key" ON "AuctionAnalysisAccess"("pointTransactionId");

-- CreateIndex
CREATE INDEX "AuctionAnalysisAccess_userId_idx" ON "AuctionAnalysisAccess"("userId");

-- CreateIndex
CREATE INDEX "AuctionAnalysisAccess_auctionNo_idx" ON "AuctionAnalysisAccess"("auctionNo");

-- CreateIndex
CREATE UNIQUE INDEX "AuctionAnalysisAccess_userId_auctionNo_key" ON "AuctionAnalysisAccess"("userId", "auctionNo");

-- AddForeignKey
ALTER TABLE "PointTransaction" ADD CONSTRAINT "PointTransaction_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "AuctionAnalysisAccess" ADD CONSTRAINT "AuctionAnalysisAccess_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "AuctionAnalysisAccess" ADD CONSTRAINT "AuctionAnalysisAccess_auctionNo_fkey" FOREIGN KEY ("auctionNo") REFERENCES "AuctionBaseInfo"("auction_no") ON DELETE CASCADE ON UPDATE CASCADE;
