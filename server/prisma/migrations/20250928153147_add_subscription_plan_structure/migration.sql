/*
  Warnings:

  - A unique constraint covering the columns `[productId,planId]` on the table `ProductInfo` will be added. If there are existing duplicate values, this will fail.

*/
-- DropIndex
DROP INDEX "ProductInfo_productId_key";

-- AlterTable
ALTER TABLE "ProductInfo" ADD COLUMN     "features" JSONB,
ADD COLUMN     "planId" TEXT,
ADD COLUMN     "planTier" TEXT;

-- CreateIndex
CREATE INDEX "ProductInfo_planTier_idx" ON "ProductInfo"("planTier");

-- CreateIndex
CREATE UNIQUE INDEX "ProductInfo_productId_planId_key" ON "ProductInfo"("productId", "planId");
