/*
  Warnings:

  - You are about to drop the `court_infos` table. If the table is not empty, all the data it contains will be lost.
  - You are about to drop the `vehicle_comprehensive_reports` table. If the table is not empty, all the data it contains will be lost.

*/
-- DropForeignKey
ALTER TABLE "vehicle_comprehensive_reports" DROP CONSTRAINT "vehicle_comprehensive_reports_auction_no_fkey";

-- DropTable
DROP TABLE "court_infos";

-- DropTable
DROP TABLE "vehicle_comprehensive_reports";

-- CreateTable
CREATE TABLE "VehicleComprehensiveReport" (
    "auction_no" TEXT NOT NULL,
    "car_reg_number" TEXT NOT NULL,
    "reportQueryDate" TEXT,
    "manufacturer" TEXT,
    "modelYear" INTEGER,
    "displacement" TEXT,
    "fuelType" TEXT,
    "detailModelName" TEXT,
    "bodyType" TEXT,
    "usageAndVehicleType" TEXT,
    "firstInsuranceDate" TEXT,
    "safetyFeaturesJson" JSONB,
    "summaryTotalLossCount" INTEGER,
    "summaryTheftCount" INTEGER,
    "summaryFloodDamage" TEXT,
    "summarySpecialUseHistory" TEXT,
    "summaryMyCarDamageCount" INTEGER,
    "summaryMyCarDamageAmount" BIGINT,
    "summaryOtherCarDamageCount" INTEGER,
    "summaryOtherCarDamageAmount" BIGINT,
    "summaryOwnerChangeCount" INTEGER,
    "summaryNumberChangeHistory" TEXT,
    "specialUsageRentalHistory" TEXT,
    "specialUsageBusinessUseHistory" TEXT,
    "specialUsageGovernmentUseHistory" TEXT,
    "ownerAndNumberChangesJson" JSONB,
    "specialAccidentsTotalLossDate" TEXT,
    "specialAccidentsTheftDate" TEXT,
    "specialAccidentsFloodDamageDate" TEXT,
    "insuranceAccidentsUninsuredPeriod" TEXT,
    "insuranceAccidentsDetailsJson" JSONB,
    "mileageHistoryJson" JSONB,
    "recallInfoJson" JSONB,
    "crawledAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "sourceHtmlPath" TEXT,
    "vehicleValueRangeMin" INTEGER,
    "vehicleValueRangeMax" INTEGER,
    "vehiclePredictedPriceJson" JSONB,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "VehicleComprehensiveReport_pkey" PRIMARY KEY ("auction_no")
);

-- CreateTable
CREATE TABLE "CourtInfo" (
    "court_name" TEXT NOT NULL,
    "address" TEXT,
    "region" TEXT NOT NULL,
    "latitude" DOUBLE PRECISION,
    "longitude" DOUBLE PRECISION,

    CONSTRAINT "CourtInfo_pkey" PRIMARY KEY ("court_name")
);

-- AddForeignKey
ALTER TABLE "VehicleComprehensiveReport" ADD CONSTRAINT "VehicleComprehensiveReport_auction_no_fkey" FOREIGN KEY ("auction_no") REFERENCES "AuctionBaseInfo"("auction_no") ON DELETE CASCADE ON UPDATE CASCADE;
