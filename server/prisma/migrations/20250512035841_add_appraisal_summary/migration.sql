/*
  Warnings:

  - You are about to drop the column `summary_condition` on the `AuctionAppraisalSummary` table. All the data in the column will be lost.

*/
-- AlterTable
ALTER TABLE "AuctionAppraisalSummary" DROP COLUMN "summary_condition",
ADD COLUMN     "summary_inspection_validity" TEXT,
ADD COLUMN     "summary_management_status" TEXT;
