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
    this.packageName = this.configService.get<string>('ANDROID_PACKAGE_NAME', '');
    
    // 설정값 검증 및 상세 로깅
    this.logger.log('=== Billing Service Configuration ===');
    this.logger.log(`Key file path: ${keyFilePath || '(not set)'}`);
    this.logger.log(`Package name: ${this.packageName || '(not set)'}`);
    this.logger.log(`Key file exists: ${keyFilePath ? fs.existsSync(keyFilePath) : false}`);
    
    if (!keyFilePath) {
      this.logger.error('GOOGLE_APPLICATION_CREDENTIALS environment variable is not set');
      return;
    }
    
    if (!fs.existsSync(keyFilePath)) {
      this.logger.error(`Google Service Account Key file not found at: ${keyFilePath}`);
      return;
    }
    
    if (!this.packageName) {
      this.logger.warn('ANDROID_PACKAGE_NAME is not set - this may cause issues with verification');
    }
    
    try {
      this.googleAuth = new GoogleAuth({
        keyFilename: keyFilePath,
        scopes: ['https://www.googleapis.com/auth/androidpublisher'],
      });
      this.logger.log('GoogleAuth initialized successfully');
    } catch (error) {
      this.logger.error('Failed to initialize GoogleAuth:', error.message);
    }
  }

  async onModuleInit() {
    this.logger.log('=== Billing Service Module Initialization ===');
    
    if (!this.googleAuth) {
      this.logger.error('GoogleAuth was not initialized. Billing service will not be able to verify purchases.');
      this.logger.error('This usually means:');
      this.logger.error('1. GOOGLE_APPLICATION_CREDENTIALS is not set');
      this.logger.error('2. Service account key file is missing');
      this.logger.error('3. Service account key file has invalid format');
      return;
    }
    
    try {
      this.androidPublisher = google.androidpublisher({
        version: 'v3',
        auth: this.googleAuth,
      });
      this.logger.log('Android Publisher API client initialized successfully');
      
      // API 연결 테스트 (선택적)
      await this.testGoogleApiConnection();
      
    } catch (error: any) {
      this.logger.error('Failed to initialize Android Publisher API client:', error.message);
      this.logger.error('Error stack:', error.stack);
    }
  }

  private async testGoogleApiConnection() {
    try {
      this.logger.log('Testing Google API connection...');
      
      // 서비스 계정 정보에서 프로젝트 ID 확인
      const keyFilePath = this.configService.get<string>('GOOGLE_APPLICATION_CREDENTIALS');
      if (keyFilePath && fs.existsSync(keyFilePath)) {
        const keyFileContent = JSON.parse(fs.readFileSync(keyFilePath, 'utf8'));
        this.logger.log(`Service account project_id: ${keyFileContent.project_id}`);
        this.logger.log(`Service account client_email: ${keyFileContent.client_email}`);
        
        if (keyFileContent.project_id !== 'digitalhospice') {
          this.logger.warn(`Unexpected project_id in service account: ${keyFileContent.project_id}`);
        }
      }
    } catch (error: any) {
      this.logger.warn('Google API connection test failed (this may be normal if no test purchases exist)');
      this.logger.warn(`Test error: ${error.message}`);
    }
  }

  private async _verifyWithGoogle(purchaseDto: VerifyPurchaseDto): Promise<boolean> {
    if (!this.androidPublisher) {
      this.logger.error('Android Publisher client is not initialized. Cannot verify purchase.');
      // 실제 프로덕션에서는 이 경우에 어떻게 처리할지 정책 결정이 필요 (예: 에러를 던지거나, false 반환)
      return false;
    }
    try {
      // 클라이언트에서 받은 packageName 우선 사용, 없으면 서버 설정값 사용
      const packageNameToUse = purchaseDto.packageName || this.packageName;
      this.logger.log(`Verifying with Google: ${purchaseDto.productId}, ${purchaseDto.purchaseToken}, packageName: ${packageNameToUse}`);
      
      const response = await this.androidPublisher.purchases.products.get({
        packageName: packageNameToUse,
        productId: purchaseDto.productId,
        token: purchaseDto.purchaseToken,
      });

      if (response.status === 200 && response.data.purchaseState === 0) {
        // purchaseState === 0 means PURCHASED
        this.logger.log('Google verification successful.');
        this.logger.log(`Purchase details: ${JSON.stringify({
          consumptionState: response.data.consumptionState,
          developerPayload: response.data.developerPayload,
          kind: response.data.kind,
          purchaseTimeMillis: response.data.purchaseTimeMillis,
          purchaseState: response.data.purchaseState
        })}`);
        return true;
      } else {
        this.logger.warn(`Google verification failed. Status: ${response.status}, Data: ${JSON.stringify(response.data)}`);
        return false;
      }
    } catch (error: any) {
      this.logger.error('=== Google API Error Details ===');
      this.logger.error(`Error message: ${error.message}`);
      this.logger.error(`Error code: ${error.code || 'N/A'}`);
      this.logger.error(`Error status: ${error.status || 'N/A'}`);
      
      if (error.response) {
        this.logger.error(`Response status: ${error.response.status}`);
        this.logger.error(`Response data: ${JSON.stringify(error.response.data)}`);
      }
      
      // 특정 에러에 대한 해결 방법 제시
      if (error.message.includes('androidpublisher.googleapis.com')) {
        this.logger.error('SOLUTION: Enable Google Play Android Publisher API at: https://console.developers.google.com/apis/api/androidpublisher.googleapis.com/overview');
      }
      
      if (error.message.includes('Service account')) {
        this.logger.error('SOLUTION: Check service account permissions and key file');
      }
      
      this.logger.error('Full error stack:', error.stack);
      return false;
    }
  }

  private async _verifySubscriptionWithGoogle(
    purchaseDto: VerifyPurchaseDto,
  ): Promise<androidpublisher_v3.Schema$SubscriptionPurchase | null> {
    try {
      // 클라이언트에서 받은 packageName 우선 사용, 없으면 서버 설정값 사용
      const packageNameToUse = purchaseDto.packageName || this.packageName;
      this.logger.log(`Verifying SUBSCRIPTION with Google: ${purchaseDto.productId}, ${purchaseDto.purchaseToken}, packageName: ${packageNameToUse}`);
      const response = await this.androidPublisher.purchases.subscriptions.get({
        packageName: packageNameToUse,
        subscriptionId: purchaseDto.productId,
        token: purchaseDto.purchaseToken,
      });

      if (response.status === 200 && response.data) {
        this.logger.log('Google subscription verification successful.');
        this.logger.log(`Subscription details: ${JSON.stringify({
          startTimeMillis: response.data.startTimeMillis,
          expiryTimeMillis: response.data.expiryTimeMillis,
          autoRenewing: response.data.autoRenewing,
          priceCurrencyCode: response.data.priceCurrencyCode,
          priceAmountMicros: response.data.priceAmountMicros,
          countryCode: response.data.countryCode
        })}`);
        return response.data;
      } else {
        this.logger.warn(`Google subscription verification failed. Status: ${response.status}, Data: ${JSON.stringify(response.data)}`);
        return null;
      }
    } catch (error: any) {
      this.logger.error('=== Google Subscription API Error Details ===');
      this.logger.error(`Error message: ${error.message}`);
      this.logger.error(`Error code: ${error.code || 'N/A'}`);
      this.logger.error(`Error status: ${error.status || 'N/A'}`);
      
      if (error.response) {
        this.logger.error(`Response status: ${error.response.status}`);
        this.logger.error(`Response data: ${JSON.stringify(error.response.data)}`);
      }
      
      // 특정 에러에 대한 해결 방법 제시
      if (error.message.includes('androidpublisher.googleapis.com')) {
        this.logger.error('SOLUTION: Enable Google Play Android Publisher API at: https://console.developers.google.com/apis/api/androidpublisher.googleapis.com/overview');
      }
      
      this.logger.error('Full subscription error stack:', error.stack);
      return null;
    }
  }

  async verifyPurchase(user: User, purchaseDto: VerifyPurchaseDto) {
    const logDetails = [
      `user: ${user.id}`,
      `product: ${purchaseDto.productId}`,
      purchaseDto.planId ? `plan: ${purchaseDto.planId}` : null,
      `package: ${purchaseDto.packageName || 'not provided'}`
    ].filter(Boolean).join(', ');
    
    this.logger.log(`Verifying purchase - ${logDetails}`);
    
    // packageName 검증 (클라이언트에서 보낸 값과 서버 설정 비교)
    if (purchaseDto.packageName && purchaseDto.packageName !== this.packageName) {
      this.logger.warn(`Package name mismatch. Expected: ${this.packageName}, Received: ${purchaseDto.packageName}`);
      throw new HttpException('Invalid package name', HttpStatus.BAD_REQUEST);
    }

    // 상품 정보 조회 (구독과 포인트 모두)
    let productInfo;
    if (purchaseDto.planId) {
      // 구독 상품인 경우 productId + planId 조합으로 조회
      productInfo = await this.prisma.productInfo.findUnique({
        where: { 
          productId_planId: { 
            productId: purchaseDto.productId, 
            planId: purchaseDto.planId 
          } 
        },
      });
    } else {
      // 포인트 상품인 경우 productId만으로 조회
      productInfo = await this.prisma.productInfo.findFirst({
        where: { 
          productId: purchaseDto.productId,
          planId: null 
        },
      });
    }

    if (!productInfo) {
      const notFoundDetails = purchaseDto.planId 
        ? `productId: ${purchaseDto.productId}, planId: ${purchaseDto.planId}`
        : `productId: ${purchaseDto.productId}`;
      this.logger.warn(`Product info not found for ${notFoundDetails}`);
      throw new HttpException('Product not found', HttpStatus.BAD_REQUEST);
    }

    // --- 구독 상품 처리 ---
    if (productInfo.type === 'SUBSCRIPTION') {
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

      this.logger.log(`Subscription '${productInfo.name}' for user ${user.id} is now ${updatedSubscription.status}.`);
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

    // 포인트 지급 (이미 productInfo를 조회했으므로 재사용)
    if (productInfo.type === 'POINT') {
      await this.prisma.user.update({
        where: { id: user.id },
        data: { points: { increment: productInfo.value } },
      });
      this.logger.log(`Granted ${productInfo.value} points to user ${user.id} for product '${productInfo.name}'.`);
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

  // 상품 목록 조회
  async getProducts(type?: string, planTier?: string) {
    const whereClause: any = {};
    if (type) whereClause.type = type;
    if (planTier) whereClause.planTier = planTier;
    
    const products = await this.prisma.productInfo.findMany({
      where: whereClause,
      orderBy: [
        { type: 'asc' },      // 타입별로 먼저 정렬 (POINT -> SUBSCRIPTION)
        { planTier: 'asc' },  // 요금제별로 정렬 (BASIC -> PREMIUM)
        { value: 'asc' },     // 그 다음 가격순으로 정렬
      ],
    });
    
    const filterDesc = [
      type ? `type: ${type}` : null,
      planTier ? `planTier: ${planTier}` : null,
    ].filter(Boolean).join(', ');
    
    this.logger.log(`Retrieved ${products.length} products${filterDesc ? ` (${filterDesc})` : ''}`);
    return products;
  }

  public getLogger() {
    return this.logger;
  }

  // 디버깅을 위한 설정 정보 조회 메서드
  public getConfigInfo() {
    const keyFilePath = this.configService.get<string>('GOOGLE_APPLICATION_CREDENTIALS');
    return {
      keyFilePath: keyFilePath || '(not set)',
      keyFileExists: keyFilePath ? fs.existsSync(keyFilePath) : false,
      packageName: this.packageName || '(not set)',
      googleAuthInitialized: !!this.googleAuth,
      androidPublisherInitialized: !!this.androidPublisher,
      nodeEnv: process.env.NODE_ENV || 'development'
    };
  }
}
