-- DropForeignKey
ALTER TABLE "PhotoURL" DROP CONSTRAINT "PhotoURL_auction_no_fkey";

-- DropTable
DROP TABLE "PhotoURL";

-- AlterTable
ALTER TABLE "AuctionBaseInfo" DROP COLUMN "representative_photo_index";
