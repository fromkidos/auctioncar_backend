/*
  Warnings:

  - Added the required column `region` to the `court_infos` table without a default value. This is not possible if the table is not empty.

*/
-- AlterTable
ALTER TABLE "court_infos" ADD COLUMN     "region" TEXT NOT NULL;
