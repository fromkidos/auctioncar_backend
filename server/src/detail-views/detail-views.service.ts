import { Injectable, BadRequestException, ForbiddenException } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';

@Injectable()
export class DetailViewsService {
  constructor(private readonly prisma: PrismaService) {}

  async getStatus(userId: string) {
    const [user, subscription] = await Promise.all([
      this.prisma.user.findUnique({
        where: { id: userId },
        select: { detailViewCredits: true },
      }),
      this.prisma.subscription.findFirst({
        where: {
          userId,
          productId: 'subscription_monthly',
          status: 'ACTIVE',
          expiryTime: { gt: new Date() },
        },
        select: { id: true },
      }),
    ]);

    if (!user) throw new BadRequestException('User not found');
    return { credits: user.detailViewCredits, isSubscribed: !!subscription };
  }

  async consume(userId: string, amount = 1) {
    if (amount <= 0) throw new BadRequestException('Invalid amount');

    // 구독자는 소모 없음
    const hasSubscription = await this.prisma.subscription.findFirst({
      where: {
        userId,
        productId: 'subscription_monthly',
        status: 'ACTIVE',
        expiryTime: { gt: new Date() },
      },
    });
    if (hasSubscription) {
      const user = await this.prisma.user.findUnique({
        where: { id: userId },
        select: { detailViewCredits: true },
      });
      return { credits: user?.detailViewCredits ?? 0, isSubscribed: true, consumed: false };
    }

    const updated = await this.prisma.user.update({
      where: { id: userId },
      data: {
        detailViewCredits: {
          decrement: amount,
        },
      },
      select: { detailViewCredits: true },
    }).catch(() => null);

    // 부족 시 롤백 및 에러
    if (!updated) throw new ForbiddenException('Failed to consume credits');
    if (updated.detailViewCredits < 0) {
      // 되돌리기
      await this.prisma.user.update({
        where: { id: userId },
        data: { detailViewCredits: { increment: amount } },
      });
      throw new ForbiddenException('Not enough credits');
    }

    return { credits: updated.detailViewCredits, isSubscribed: false, consumed: true };
  }

  async reward(userId: string, views = 5) {
    if (views <= 0) throw new BadRequestException('Invalid views');
    const updated = await this.prisma.user.update({
      where: { id: userId },
      data: { detailViewCredits: { increment: views } },
      select: { detailViewCredits: true },
    });
    return { credits: updated.detailViewCredits };
  }

  async purchaseWithPoints(userId: string, costPoints = 10, addViews = 10) {
    if (costPoints <= 0 || addViews <= 0) throw new BadRequestException('Invalid purchase params');

    return await this.prisma.$transaction(async (tx) => {
      const user = await tx.user.findUnique({ where: { id: userId }, select: { points: true } });
      if (!user) throw new BadRequestException('User not found');
      if (user.points < costPoints) throw new ForbiddenException('Not enough points');

      const updated = await tx.user.update({
        where: { id: userId },
        data: {
          points: { decrement: costPoints },
          detailViewCredits: { increment: addViews },
        },
        select: { points: true, detailViewCredits: true },
      });

      await tx.pointTransaction.create({
        data: {
          userId,
          amount: -costPoints,
          balanceAfter: updated.points,
          description: `Detail view credits +${addViews} for ${costPoints} points`,
          type: 'SPEND_ANALYSIS',
        },
      });

      return { credits: updated.detailViewCredits, points: updated.points };
    });
  }
}


