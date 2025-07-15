/*
  Warnings:

  - Changed the type of `type` on the `PointTransaction` table. No cast exists, the column would be dropped and recreated, which cannot be done if there is data, since the column is required.
  - Changed the type of `provider` on the `User` table. No cast exists, the column would be dropped and recreated, which cannot be done if there is data, since the column is required.

*/
-- CreateEnum
CREATE TYPE "SocialLoginProvider" AS ENUM ('GOOGLE', 'KAKAO', 'NAVER');

-- CreateEnum
CREATE TYPE "PointTransactionType" AS ENUM ('CHARGE', 'SPEND_ANALYSIS', 'REFUND', 'ADMIN_GRANT', 'PROMOTION');

-- AlterTable
ALTER TABLE "PointTransaction" DROP COLUMN "type",
ADD COLUMN     "type" "PointTransactionType" NOT NULL;

-- AlterTable
ALTER TABLE "User" DROP COLUMN "provider",
ADD COLUMN     "provider" "SocialLoginProvider" NOT NULL;

-- CreateIndex
CREATE INDEX "PointTransaction_type_idx" ON "PointTransaction"("type");

-- CreateIndex
CREATE UNIQUE INDEX "User_provider_providerId_key" ON "User"("provider", "providerId");
