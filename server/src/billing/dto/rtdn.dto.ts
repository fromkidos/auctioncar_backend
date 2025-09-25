// Google Pub/Sub 메시지 구조
export interface PubSubMessage {
  message: {
    data: string; // Base64 인코딩된 RtdnPayload
    messageId: string;
    publishTime: string;
  };
  subscription: string;
}

// Base64 디코딩 후의 실제 알림 페이로드
export interface RtdnPayload {
  version: string;
  packageName: string;
  eventTimeMillis: string;
  subscriptionNotification?: SubscriptionNotification;
  testNotification?: TestNotification;
}

// 구독 관련 알림 상세
export interface SubscriptionNotification {
  notificationType: NotificationType;
  purchaseToken: string;
  subscriptionId: string;
}

// 테스트 알림 상세
export interface TestNotification {
  version: string;
}

// Google에서 정의한 알림 타입 Enum (필요한 것만 추가)
export enum NotificationType {
  SUBSCRIPTION_RECOVERED = 1,
  SUBSCRIPTION_RENEWED = 2,
  SUBSCRIPTION_CANCELED = 3,
  SUBSCRIPTION_PURCHASED = 4,
  SUBSCRIPTION_ON_HOLD = 5,
  SUBSCRIPTION_IN_GRACE_PERIOD = 6,
  SUBSCRIPTION_RESTARTED = 7,
  SUBSCRIPTION_PRICE_CHANGE_CONFIRMED = 8,
  SUBSCRIPTION_DEFERRED = 9,
  SUBSCRIPTION_PAUSED = 10,
  SUBSCRIPTION_PAUSE_SCHEDULE_CHANGED = 11,
  SUBSCRIPTION_REVOKED = 12,
  SUBSCRIPTION_EXPIRED = 13,
}
