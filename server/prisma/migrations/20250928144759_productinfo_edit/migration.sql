/*
  Warnings:

  - Added the required column `name` to the `ProductInfo` table without a default value. This is not possible if the table is not empty.

*/
-- AlterEnum
ALTER TYPE "ProductType" ADD VALUE 'SUBSCRIPTION';

-- AlterTable
ALTER TABLE "ProductInfo" ADD COLUMN     "description" TEXT,
ADD COLUMN     "name" TEXT NOT NULL;
