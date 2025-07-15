-- CreateTable
CREATE TABLE "AuctionAppraisalSummary" (
    "auction_no" TEXT NOT NULL,
    "summary_year_mileage" TEXT,
    "summary_color" TEXT,
    "summary_condition" TEXT,
    "summary_fuel" TEXT,
    "summary_inspection" TEXT,
    "summary_options_etc" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "AuctionAppraisalSummary_pkey" PRIMARY KEY ("auction_no")
);

-- AddForeignKey
ALTER TABLE "AuctionAppraisalSummary" ADD CONSTRAINT "AuctionAppraisalSummary_auction_no_fkey" FOREIGN KEY ("auction_no") REFERENCES "AuctionBaseInfo"("auction_no") ON DELETE CASCADE ON UPDATE CASCADE;
