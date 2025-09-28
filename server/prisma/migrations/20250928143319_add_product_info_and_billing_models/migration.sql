-- CreateEnum
CREATE TYPE "ProductType" AS ENUM ('POINT');

-- CreateTable
CREATE TABLE "ProductInfo" (
    "id" TEXT NOT NULL,
    "productId" TEXT NOT NULL,
    "type" "ProductType" NOT NULL,
    "value" INTEGER NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "ProductInfo_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "ProductInfo_productId_key" ON "ProductInfo"("productId");

-- CreateIndex
CREATE INDEX "ProductInfo_productId_idx" ON "ProductInfo"("productId");

-- CreateIndex
CREATE INDEX "ProductInfo_type_idx" ON "ProductInfo"("type");
