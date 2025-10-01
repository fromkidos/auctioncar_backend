-- AlterTable
ALTER TABLE "Subscription" ADD COLUMN     "planId" TEXT,
ADD COLUMN     "planTier" TEXT;

-- CreateIndex
CREATE INDEX "Subscription_planTier_idx" ON "Subscription"("planTier");
