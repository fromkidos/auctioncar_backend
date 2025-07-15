-- CreateTable
CREATE TABLE "AuctionResult" (
    "auction_no" TEXT NOT NULL,
    "title" TEXT,
    "usage" TEXT,
    "appraisal_value" BIGINT,
    "min_bid_price" BIGINT,
    "sale_date" TEXT,
    "sale_price" BIGINT,
    "bid_rate" DOUBLE PRECISION,

    CONSTRAINT "AuctionResult_pkey" PRIMARY KEY ("auction_no")
);

-- CreateIndex
CREATE INDEX "AuctionResult_sale_date_idx" ON "AuctionResult"("sale_date");

-- CreateIndex
CREATE INDEX "AuctionResult_usage_idx" ON "AuctionResult"("usage");
