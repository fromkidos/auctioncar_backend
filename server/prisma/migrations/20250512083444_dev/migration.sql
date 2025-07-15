/*
  Warnings:

  - Added the required column `car_reg_number` to the `vehicle_comprehensive_reports` table without a default value. This is not possible if the table is not empty.

*/
-- AlterTable
ALTER TABLE "vehicle_comprehensive_reports" ADD COLUMN     "car_reg_number" TEXT NOT NULL;
