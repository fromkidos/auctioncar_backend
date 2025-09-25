import { Injectable, Logger, HttpException, HttpStatus, OnModuleInit } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { PrismaService } from '../prisma/prisma.service';
import { VerifyPurchaseDto } from './dto/verify-purchase.dto';
import { User } from '@prisma/client';
import { GoogleAuth } from 'google-auth-library';
import { androidpublisher_v3, google } from 'googleapis';
import * as fs from 'fs';
import * as path from 'path';
import { RtdnPayload, PubSubMessage, NotificationType } from './dto/rtdn.dto';

@Injectable()
export class BillingService implements OnModuleInit {
  private readonly logger = new Logger(BillingService.name);
  private androidPublisher: androidpublisher_v3.Androidpublisher;
  private packageName: string;
  private googleAuth: GoogleAuth;

  constructor(
    private readonly prisma: PrismaService,
    private readonly configService: ConfigService,
  ) {
    const keyFilePath = this.configService.get<string>('GOOGLE_APPLICATION_CREDENTIALS');
    if (!keyFilePath || !fs.existsSync(keyFilePath)) {
      this.logger.error('Google Service Account Key file not found. Skipping GoogleAuth initialization.');
      return;
    }
    
    this.googleAuth = new GoogleAuth({
      keyFilename: keyFilePath,
      scopes: ['https://www.googleapis.com/auth/androidpublisher'],
    });

    this.packageName = this.configService.get<string>('ANDROID_PACKAGE_NAME', '');
  }

  async onModuleInit() {
    if (!this.googleAuth) {
      this.logger.error('GoogleAuth was not initialized. Billing service will not be able to verify purchases.');
      return;
    }
    this.androidPublisher = google.androidpublisher({
      version: 'v3',
      auth: this.googleAuth,
    });
  }

  private async _verifyWithGoogle(purchaseDto: VerifyPurchaseDto): Promise<boolean> {
    if (!this.androidPublisher) {
      this.logger.error('Android Publisher client is not initialized. Cannot verify purchase.');
      // 실제 프로덕션에서는 이 경우에 어떻게 처리할지 정책 결정이 필요 (예: 에러를 던지거나, false 반환)
      return false;
    }
    try {
      this.logger.log(`Verifying with Google: ${purchaseDto.productId}, ${purchaseDto.purchaseToken}`);
      
      const response = await this.androidPublisher.purchases.products.get({
        packageName: this.packageName,
        productId: purchaseDto.productId,
        token: purchaseDto.purchaseToken,
      });

      if (response.status === 200 && response.data.purchaseState === 0) {
        // purchaseState === 0 means PURCHASED
        this.logger.log('Google verification successful.');
        return true;
      } else {
        this.logger.warn(`Google verification failed. Status: ${response.status}, Data: ${JSON.stringify(response.data)}`);
        return false;
      }
    } catch (error) {
      this.logger.error('Error verifying purchase with Google.', error.stack);
      // Google API가 4xx 에러를 반환하면 (예: 토큰이 유효하지 않음) 예외가 발생합니다.
      return false;
    }
  }

  private async _verifySubscriptionWithGoogle(
    purchaseDto: VerifyPurchaseDto,
  ): Promise<androidpublisher_v3.Schema$SubscriptionPurchase | null> {
    try {
      this.logger.log(`Verifying SUBSCRIPTION with Google: ${purchaseDto.productId}, ${purchaseDto.purchaseToken}`);
      const response = await this.androidPublisher.purchases.subscriptions.get({
        packageName: this.packageName,
        subscriptionId: purchaseDto.productId,
        token: purchaseDto.purchaseToken,
      });

      if (response.status === 200 && response.data) {
        this.logger.log('Google subscription verification successful.');
        return response.data;
      } else {
        this.logger.warn(`Google subscription verification failed. Status: ${response.status}, Data: ${JSON.stringify(response.data)}`);
        return null;
      }
    } catch (error) {
      this.logger.error('Error verifying subscription with Google.', error.stack);
      return null;
    }
  }

  async verifyPurchase(user: User, purchaseDto: VerifyPurchaseDto) {
    this.logger.log(`Verifying purchase for user ${user.id}, product ${purchaseDto.productId}`);

    // --- 구독 상품 처리 ---
    if (purchaseDto.productId === 'subscription_monthly') {
      const subscriptionDetails = await this._verifySubscriptionWithGoogle(purchaseDto);
      if (!subscriptionDetails) {
        throw new HttpException('Invalid subscription receipt', HttpStatus.BAD_REQUEST);
      }

      // UNIX 타임스탬프(ms)를 Date 객체로 변환
      const startTime = new Date(parseInt(subscriptionDetails.startTimeMillis || '0', 10));
      const expiryTime = new Date(parseInt(subscriptionDetails.expiryTimeMillis || '0', 10));

      const updatedSubscription = await this.prisma.subscription.upsert({
        where: { userId: user.id },
        update: {
          productId: purchaseDto.productId,
          latestPurchaseToken: purchaseDto.purchaseToken,
          startTime: startTime,
          expiryTime: expiryTime,
          status: 'ACTIVE', // 또는 subscriptionDetails에서 상태를 가져옴
          autoRenewing: subscriptionDetails.autoRenewing ?? false,
        },
        create: {
          userId: user.id,
          productId: purchaseDto.productId,
          originalPurchaseToken: purchaseDto.purchaseToken, // 최초 생성 시에는 동일
          latestPurchaseToken: purchaseDto.purchaseToken,
          startTime: startTime,
          expiryTime: expiryTime,
          status: 'ACTIVE',
          autoRenewing: subscriptionDetails.autoRenewing ?? false,
        },
      });

      this.logger.log(`Subscription for user ${user.id} is now ${updatedSubscription.status}.`);
      return updatedSubscription;
    }

    // --- 소모품(포인트) 처리 ---
    const isGoogleVerified = await this._verifyWithGoogle(purchaseDto);
    if (!isGoogleVerified) {
      throw new HttpException('Invalid receipt', HttpStatus.BAD_REQUEST);
    }

    const existingPurchase = await this.prisma.purchase.findUnique({
      where: { purchaseToken: purchaseDto.purchaseToken },
    });

    if (existingPurchase) {
      this.logger.warn(`Purchase token ${purchaseDto.purchaseToken} has already been processed.`);
      return existingPurchase;
    }

    const newPurchase = await this.prisma.purchase.create({
      data: {
        userId: user.id,
        productId: purchaseDto.productId,
        purchaseToken: purchaseDto.purchaseToken,
        orderId: purchaseDto.orderId,
        purchaseTime: new Date(purchaseDto.purchaseTime),
        signature: purchaseDto.signature,
        originalJson: JSON.parse(purchaseDto.originalJson),
      },
    });
    
    this.logger.log(`New purchase ${newPurchase.id} for user ${user.id} saved.`);

    if (purchaseDto.productId === 'point_100') {
      await this.prisma.user.update({
        where: { id: user.id },
        data: { points: { increment: 100 } },
      });
      this.logger.log(`Granted 100 points to user ${user.id}.`);
    }

    // TODO: Google API 연동 후, 소비(consume) 로직 구현

    return newPurchase;
  }

  async handleRtdn(notification: PubSubMessage) {
    this.logger.log('Received RTDN notification.');

    // 1. Base64 디코딩
    const decodedData = Buffer.from(notification.message.data, 'base64').toString('utf-8');
    const payload = JSON.parse(decodedData) as RtdnPayload;

    this.logger.log(`RTDN Payload: ${JSON.stringify(payload)}`);

    // 테스트 알림 처리
    if (payload.testNotification) {
      this.logger.log('Received test notification from Google Play. Verification successful.');
      return;
    }

    // 구독 알림 처리
    if (!payload.subscriptionNotification) {
      this.logger.warn('Received a notification without a subscription payload.');
      return;
    }
    const subNotification = payload.subscriptionNotification;

    // 2. 알림 타입에 따른 분기 처리 (예시)
    switch (subNotification.notificationType) {
      case NotificationType.SUBSCRIPTION_RENEWED:
      case NotificationType.SUBSCRIPTION_RECOVERED:
      case NotificationType.SUBSCRIPTION_PURCHASED:
        this.logger.log(`Handling subscription update for token: ${subNotification.purchaseToken}`);
        await this._updateSubscriptionStatusFromGoogle(
          subNotification.subscriptionId,
          subNotification.purchaseToken,
        );
        break;
      case NotificationType.SUBSCRIPTION_CANCELED:
      case NotificationType.SUBSCRIPTION_EXPIRED:
      case NotificationType.SUBSCRIPTION_ON_HOLD:
        this.logger.log(`Handling subscription cancellation/expiry for token: ${subNotification.purchaseToken}`);
        await this._updateSubscriptionStatusFromGoogle(
          subNotification.subscriptionId,
          subNotification.purchaseToken,
        );
        break;
      // TODO: 다른 알림 타입에 대한 처리 로직 추가
      default:
        this.logger.log(`Unhandled notification type: ${subNotification.notificationType}`);
    }
  }

  // Google에서 최신 구독 정보를 가져와 DB에 업데이트하는 헬퍼 메서드
  private async _updateSubscriptionStatusFromGoogle(productId: string, purchaseToken: string) {
    try {
      const response = await this.androidPublisher.purchases.subscriptions.get({
        packageName: this.packageName,
        subscriptionId: productId,
        token: purchaseToken,
      });

      if (response.status !== 200 || !response.data) {
        this.logger.error(`Failed to get subscription details from Google for token: ${purchaseToken}`);
        return;
      }
      
      const subDetails = response.data;
      
      // originalPurchaseToken을 기준으로 구독 정보를 찾아야 함
      // 이 예제에서는 purchaseToken이 originalPurchaseToken이라고 가정하지만,
      // 실제로는 DB에서 originalPurchaseToken을 찾아야 할 수 있음.
      const subscription = await this.prisma.subscription.findFirst({
        where: { OR: [
          { originalPurchaseToken: purchaseToken },
          { latestPurchaseToken: purchaseToken },
        ]}
      });

      if (!subscription) {
        this.logger.warn(`Subscription not found in DB for token: ${purchaseToken}. It might be a new subscription not yet recorded.`);
        // TODO: 이 경우 새로운 구독으로 처리하는 로직을 추가하거나,
        // 최초 구매는 verifyPurchase를 통해서만 이루어진다고 가정하고 넘어갈 수 있음.
        return;
      }

      const expiryTime = new Date(parseInt(subDetails.expiryTimeMillis || '0', 10));
      
      let status = 'UNKNOWN';
      if (subDetails.expiryTimeMillis && expiryTime > new Date()) {
          status = 'ACTIVE';
      } else {
          status = 'EXPIRED';
      }
      if (subDetails.cancelReason != null) {
          status = 'CANCELED';
      }
      // TODO: 더 상세한 상태 매핑 로직 추가 (예: ON_HOLD, PAUSED)

      await this.prisma.subscription.update({
        where: { id: subscription.id },
        data: {
          latestPurchaseToken: purchaseToken,
          expiryTime: expiryTime,
          autoRenewing: subDetails.autoRenewing ?? false,
          status: status,
          latestNotificationType: NotificationType[subDetails.acknowledgementState ?? NotificationType.SUBSCRIPTION_RENEWED], // 예시, 실제 타입 매핑 필요
          latestNotificationJson: subDetails as any,
        },
      });

      this.logger.log(`Successfully updated subscription ${subscription.id} to status ${status}`);

    } catch (error) {
      this.logger.error(`Error updating subscription status from Google for token ${purchaseToken}`, error.stack);
    }
  }

  public getLogger() {
    return this.logger;
  }
}
