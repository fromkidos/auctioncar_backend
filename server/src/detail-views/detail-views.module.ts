import { Module } from '@nestjs/common';
import { DetailViewsService } from './detail-views.service';
import { DetailViewsController } from './detail-views.controller';
import { PrismaModule } from '../prisma/prisma.module';

@Module({
  imports: [PrismaModule],
  providers: [DetailViewsService],
  controllers: [DetailViewsController],
})
export class DetailViewsModule {}


