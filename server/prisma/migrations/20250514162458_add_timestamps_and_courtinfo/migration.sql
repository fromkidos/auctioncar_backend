/*
  Warnings:

  - You are about to drop the column `freeFloodCheckResult` on the `vehicle_comprehensive_reports` table. All the data in the column will be lost.
  - You are about to drop the column `freeScrapCheckResult` on the `vehicle_comprehensive_reports` table. All the data in the column will be lost.

*/
-- AlterTable
ALTER TABLE "AuctionBaseInfo" ADD COLUMN     "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
ADD COLUMN     "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP;

-- AlterTable
ALTER TABLE "vehicle_comprehensive_reports" DROP COLUMN "freeFloodCheckResult",
DROP COLUMN "freeScrapCheckResult";

-- CreateTable
CREATE TABLE "court_infos" (
    "court_name" TEXT NOT NULL,
    "address" TEXT,
    "latitude" DOUBLE PRECISION,
    "longitude" DOUBLE PRECISION,

    CONSTRAINT "court_infos_pkey" PRIMARY KEY ("court_name")
);
