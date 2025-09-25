import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';
import { ValidationPipe, Logger } from '@nestjs/common';
import { DocumentBuilder, SwaggerModule } from '@nestjs/swagger';
import { NestExpressApplication } from '@nestjs/platform-express';
import { Request, Response, NextFunction } from 'express';
import { join } from 'path';
import helmet from 'helmet';
import { GlobalExceptionFilter } from './common/filters/global-exception.filter';
import { ConfigService } from '@nestjs/config';

// BigInt serialization fix
(BigInt.prototype as any).toJSON = function () {
  return this.toString();
};

async function bootstrap() {
  const app = await NestFactory.create<NestExpressApplication>(AppModule);
  const configService = app.get(ConfigService);
  const logger = new Logger('Bootstrap');

  /**
   * Cloudflare Tunnel 뒤에서 동작하므로 프록시 신뢰
   * - X-Forwarded-For / CF-Connecting-IP 를 통해 클라이언트 IP 확인 가능
   */
  app.set('trust proxy', 1);

  /**
   * 보안 헤더 설정 (Swagger/정적자원과 충돌 최소화)
   * - CSP는 최소한으로 설정 (특히 'connectSrc'는 같은 오리진 + https 허용)
   */
  app.use(
    helmet({
      contentSecurityPolicy: {
        useDefaults: true,
        directives: {
          defaultSrc: ["'self'"],
          styleSrc: ["'self'", "'unsafe-inline'"],
          scriptSrc: ["'self'"],
          imgSrc: ["'self'", "data:", "https:"],
          connectSrc: ["'self'", "https:"],
          fontSrc: ["'self'"],
          objectSrc: ["'none'"],
          mediaSrc: ["'self'"],
          frameSrc: ["'none'"],
        },
      },
      crossOriginEmbedderPolicy: false, // Swagger/CORS 충돌 방지
    })
  );

  // Request logging (development only)
  if (process.env.NODE_ENV !== 'production') {
    app.use((req: Request, _res: Response, next: NextFunction) => {
      // cf-connecting-ip 헤더가 있으면 그걸 우선 로깅
      const realIp =
        (req.headers['cf-connecting-ip'] as string) ||
        (req.headers['x-forwarded-for'] as string) ||
        req.ip;
      logger.debug(`${req.method} ${req.originalUrl} - ip:${realIp}`);
      next();
    });
  }

  // 글로벌 에러 필터
  app.useGlobalFilters(new GlobalExceptionFilter());

  // 정적 파일 (예: /static/uploads/...)
  const staticAssetsPath = join(process.cwd(), '..', '..', 'public');
  logger.log(`Serving static files from: ${staticAssetsPath}`);
  app.useStaticAssets(staticAssetsPath, {
    prefix: '/static/',
    setHeaders: (res) => {
      res.setHeader('Cache-Control', 'public, max-age=31536000, immutable');
      res.setHeader('Accept-Ranges', 'bytes');
    },
  });
  

  /**
   * CORS
   * - 프로덕션: 기본 오리진 목록에 api.pitchmstudio.com 포함 (쉼표 구분 ENV 허용)
   * - 개발: any(true)
   */
  const defaultAllowedOrigins =
    ['https://api.pitchmstudio.com']
      .concat(
        (configService.get<string>('ALLOWED_ORIGINS', '') || '')
          .split(',')
          .map((s) => s.trim())
          .filter(Boolean)
      )
      // 중복 제거
      .filter((v, i, arr) => arr.indexOf(v) === i);

  app.enableCors({
    origin:
      process.env.NODE_ENV === 'production' ? defaultAllowedOrigins : true,
    methods: ['GET', 'HEAD', 'PUT', 'PATCH', 'POST', 'DELETE', 'OPTIONS'],
    credentials: true,
    allowedHeaders: ['Content-Type', 'Authorization'],
    exposedHeaders: [],
  });

  // 글로벌 파이프
  app.useGlobalPipes(
    new ValidationPipe({
      whitelist: true,
      forbidNonWhitelisted: true,
      transform: true,
      transformOptions: {
        enableImplicitConversion: true,
      },
    })
  );

  // Swagger (개발에서만)
  if (process.env.NODE_ENV !== 'production') {
    const swaggerConfig = new DocumentBuilder()
      .setTitle('Courtauction Car API')
      .setDescription('법원 경매 차량 정보 API 문서입니다.')
      .setVersion('1.0')
      .addBearerAuth()
      .build();
    const document = SwaggerModule.createDocument(app, swaggerConfig);
    SwaggerModule.setup('api-docs', app, document);
  }

  // (선택) 헬스 체크 핸들러: 터널/도메인/SSL 확인용
  try {
    const http = app.getHttpAdapter().getInstance();
    http.get('/health', (_req: Request, res: Response) => {
      res.json({ ok: true, ts: Date.now() });
    });
  } catch {
    // Express가 아닐 경우 무시
  }

  // 서버는 내부 HTTP만 리슨 (cloudflared에서 :3000으로 프록시)
  const port = parseInt(configService.get<string>('PORT', '3000'), 10);
  const host = configService.get<string>('HOST', '0.0.0.0');
  await app.listen(port, host);

  // 로그 표시용 베이스 URL
  const serverBaseUrl =
    configService.get<string>('SERVER_BASE_URL') || `http://${host}:${port}`;
  logger.log(`🚀 Server running on ${serverBaseUrl}`);
  if (process.env.NODE_ENV !== 'production') {
    logger.log(`📚 Swagger UI: ${serverBaseUrl}/api-docs`);
  }
  logger.log(`📁 Static files: ${serverBaseUrl}/static`);
}

bootstrap().catch((error) => {
  const logger = new Logger('Bootstrap');
  logger.error('Failed to start server', error);
  process.exit(1);
});
