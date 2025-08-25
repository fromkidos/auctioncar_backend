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

  // 보안 헤더 설정
  app.use(helmet({
    contentSecurityPolicy: {
      directives: {
        defaultSrc: ["'self'"],
        styleSrc: ["'self'", "'unsafe-inline'"],
        scriptSrc: ["'self'"],
        imgSrc: ["'self'", "data:", "https:"],
        connectSrc: ["'self'"],
        fontSrc: ["'self'"],
        objectSrc: ["'none'"],
        mediaSrc: ["'self'"],
        frameSrc: ["'none'"],
      },
    },
    crossOriginEmbedderPolicy: false, // CORS와 충돌 방지
  }));

  // Request logging middleware (only in development)
  if (process.env.NODE_ENV !== 'production') {
    app.use((req: Request, res: Response, next: NextFunction) => {
      logger.debug(`${req.method} ${req.originalUrl}`);
      next();
    });
  }

  // 글로벌 에러 필터 적용
  app.useGlobalFilters(new GlobalExceptionFilter());

  // 정적 파일 제공 설정
  const staticAssetsPath = join(process.cwd(), '..', '..', 'public');
  logger.log(`Serving static files from: ${staticAssetsPath}`);
  app.useStaticAssets(staticAssetsPath, {
    prefix: '/static/', 
  });

  // CORS 활성화
  app.enableCors({
    origin: process.env.NODE_ENV === 'production' 
      ? configService.get<string>('ALLOWED_ORIGINS', '').split(',')
      : true,
    methods: 'GET,HEAD,PUT,PATCH,POST,DELETE,OPTIONS',
    credentials: true,
  });

  app.useGlobalPipes(new ValidationPipe({
    whitelist: true,
    forbidNonWhitelisted: true,
    transform: true,
    transformOptions: {
      enableImplicitConversion: true,
    },
  }));

  // Swagger 설정 (개발 환경에서만)
  if (process.env.NODE_ENV !== 'production') {
    const config = new DocumentBuilder()
      .setTitle('Courtauction Car API')
      .setDescription('법원 경매 차량 정보 API 문서입니다.')
      .setVersion('1.0')
      .addBearerAuth()
      .build();
    const document = SwaggerModule.createDocument(app, config);
    SwaggerModule.setup('api-docs', app, document);
  }

  // BigIntInterceptor는 main.ts 상단의 전역 BigInt 처리 코드로 대체되었으므로 삭제합니다.
  // app.useGlobalInterceptors(new BigIntInterceptor());

  const port = parseInt(configService.get<string>('PORT', '4000'), 10);
  const host = configService.get<string>('HOST', '127.0.0.1');

  await app.listen(port, host);
  
  const serverBaseUrl = configService.get<string>('SERVER_BASE_URL') || `http://${host}:${port}`;
  
  logger.log(`🚀 Server running on ${serverBaseUrl}`);
  if (process.env.NODE_ENV !== 'production') {
    logger.log(`📚 Swagger UI available at ${serverBaseUrl}/api-docs`);
  }
  logger.log(`📁 Static files served at ${serverBaseUrl}/static`);
}

bootstrap().catch(error => {
  const logger = new Logger('Bootstrap');
  logger.error('Failed to start server', error);
  process.exit(1);
});
