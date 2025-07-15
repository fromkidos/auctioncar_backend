-- CreateTable
CREATE TABLE "AuctionBaseInfo" (
    "auction_no" TEXT NOT NULL,
    "case_year" INTEGER NOT NULL,
    "case_number" TEXT NOT NULL,
    "item_no" INTEGER NOT NULL,
    "court_name" TEXT NOT NULL,
    "appraisal_price" DECIMAL(65,30),
    "min_bid_price" DECIMAL(65,30),
    "sale_date" TIMESTAMP(3),
    "status" TEXT,
    "car_name" TEXT,
    "car_model_year" INTEGER,
    "car_reg_number" TEXT,
    "car_mileage" INTEGER,
    "car_fuel" TEXT,
    "car_transmission" TEXT,
    "car_type" TEXT,
    "manufacturer" TEXT,

    CONSTRAINT "AuctionBaseInfo_pkey" PRIMARY KEY ("auction_no")
);

-- CreateTable
CREATE TABLE "AuctionDetailInfo" (
    "auction_no" TEXT NOT NULL,
    "court_name" TEXT NOT NULL,
    "location_address" TEXT,
    "sale_time" TEXT,
    "sale_location" TEXT,
    "car_vin" TEXT,
    "other_details" TEXT,
    "documents" JSONB,
    "kind" TEXT,
    "bid_method" TEXT,
    "case_received_date" TIMESTAMP(3),
    "auction_start_date" TIMESTAMP(3),
    "distribution_due_date" TIMESTAMP(3),
    "claim_amount" DECIMAL(65,30),
    "engine_type" TEXT,
    "approval_number" TEXT,
    "displacement" INTEGER,
    "department_info" TEXT,
    "dividend_demand_details" TEXT,
    "dividend_storage_method" TEXT,
    "appraisal_summary_text" TEXT,

    CONSTRAINT "AuctionDetailInfo_pkey" PRIMARY KEY ("auction_no")
);

-- CreateTable
CREATE TABLE "DateHistory" (
    "id" SERIAL NOT NULL,
    "auction_no" TEXT NOT NULL,
    "court_name" TEXT NOT NULL,
    "date_time" TIMESTAMP(3) NOT NULL,
    "type" TEXT NOT NULL,
    "location" TEXT,
    "min_bid_price" DECIMAL(65,30),
    "result" TEXT,

    CONSTRAINT "DateHistory_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "PhotoURL" (
    "id" SERIAL NOT NULL,
    "auction_no" TEXT NOT NULL,
    "court_name" TEXT NOT NULL,
    "photo_index" INTEGER NOT NULL,
    "image_path_or_url" TEXT NOT NULL,

    CONSTRAINT "PhotoURL_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "SimilarSale" (
    "id" SERIAL NOT NULL,
    "auction_no" TEXT NOT NULL,
    "court_name" TEXT NOT NULL,
    "period" TEXT NOT NULL,
    "sale_count" INTEGER,
    "avg_appraisal_price" DECIMAL(65,30),
    "avg_sale_price" DECIMAL(65,30),
    "sale_to_appraisal_ratio" DOUBLE PRECISION,
    "avg_unsold_count" DOUBLE PRECISION,

    CONSTRAINT "SimilarSale_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "AuctionBaseInfo_court_name_idx" ON "AuctionBaseInfo"("court_name");

-- CreateIndex
CREATE INDEX "AuctionBaseInfo_status_idx" ON "AuctionBaseInfo"("status");

-- CreateIndex
CREATE INDEX "AuctionBaseInfo_car_name_idx" ON "AuctionBaseInfo"("car_name");

-- CreateIndex
CREATE INDEX "AuctionBaseInfo_sale_date_idx" ON "AuctionBaseInfo"("sale_date");

-- CreateIndex
CREATE INDEX "AuctionDetailInfo_court_name_idx" ON "AuctionDetailInfo"("court_name");

-- CreateIndex
CREATE INDEX "DateHistory_auction_no_idx" ON "DateHistory"("auction_no");

-- CreateIndex
CREATE INDEX "DateHistory_court_name_idx" ON "DateHistory"("court_name");

-- CreateIndex
CREATE UNIQUE INDEX "DateHistory_auction_no_date_time_type_key" ON "DateHistory"("auction_no", "date_time", "type");

-- CreateIndex
CREATE INDEX "PhotoURL_auction_no_idx" ON "PhotoURL"("auction_no");

-- CreateIndex
CREATE UNIQUE INDEX "PhotoURL_auction_no_photo_index_key" ON "PhotoURL"("auction_no", "photo_index");

-- CreateIndex
CREATE INDEX "SimilarSale_auction_no_idx" ON "SimilarSale"("auction_no");

-- CreateIndex
CREATE UNIQUE INDEX "SimilarSale_auction_no_period_key" ON "SimilarSale"("auction_no", "period");

-- AddForeignKey
ALTER TABLE "AuctionDetailInfo" ADD CONSTRAINT "AuctionDetailInfo_auction_no_fkey" FOREIGN KEY ("auction_no") REFERENCES "AuctionBaseInfo"("auction_no") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "DateHistory" ADD CONSTRAINT "DateHistory_auction_no_fkey" FOREIGN KEY ("auction_no") REFERENCES "AuctionBaseInfo"("auction_no") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "PhotoURL" ADD CONSTRAINT "PhotoURL_auction_no_fkey" FOREIGN KEY ("auction_no") REFERENCES "AuctionBaseInfo"("auction_no") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "SimilarSale" ADD CONSTRAINT "SimilarSale_auction_no_fkey" FOREIGN KEY ("auction_no") REFERENCES "AuctionBaseInfo"("auction_no") ON DELETE CASCADE ON UPDATE CASCADE;
