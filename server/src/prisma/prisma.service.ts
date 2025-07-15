import { Injectable, OnModuleInit, OnModuleDestroy, Logger } from '@nestjs/common';
import { PrismaClient } from '@prisma/client';

@Injectable()
export class PrismaService extends PrismaClient implements OnModuleInit, OnModuleDestroy {
  private readonly logger = new Logger(PrismaService.name);
  private readonly maxRetries = 5;
  private readonly retryDelay = 5000; // 5 seconds

  constructor() {
    super({
      log: process.env.NODE_ENV === 'development' 
        ? ['query', 'info', 'warn', 'error'] 
        : ['warn', 'error'],
      errorFormat: 'pretty',
    });
  }

  async onModuleInit(): Promise<void> {
    await this.connectWithRetry();
  }

  async onModuleDestroy(): Promise<void> {
    await this.$disconnect();
    this.logger.log('Prisma Client Disconnected');
  }

  private async connectWithRetry(attempt = 1): Promise<void> {
    try {
      await this.$connect();
      this.logger.log('✅ Prisma Client Connected Successfully');
      
      // 연결 상태 확인을 위한 간단한 쿼리
      await this.$queryRaw`SELECT 1`;
      this.logger.log('✅ Database connection verified');
      
    } catch (error) {
      this.logger.error(
        `❌ Failed to connect to database (attempt ${attempt}/${this.maxRetries})`,
        error instanceof Error ? error.message : String(error)
      );

      if (attempt < this.maxRetries) {
        this.logger.log(`⏳ Retrying connection in ${this.retryDelay / 1000}s...`);
        
        await new Promise(resolve => setTimeout(resolve, this.retryDelay));
        return this.connectWithRetry(attempt + 1);
      } else {
        this.logger.fatal('💀 Failed to connect to database after maximum retries');
        
        // 프로덕션 환경에서는 프로세스 종료
        if (process.env.NODE_ENV === 'production') {
          process.exit(1);
        }
        
        throw new Error('Database connection failed');
      }
    }
  }

  // 헬스체크용 메서드
  async healthCheck(): Promise<{ status: string; timestamp: Date }> {
    try {
      await this.$queryRaw`SELECT 1`;
      return {
        status: 'healthy',
        timestamp: new Date()
      };
    } catch (error) {
      this.logger.error('Database health check failed', error);
      throw new Error('Database is unhealthy');
    }
  }

  // 트랜잭션 헬퍼 메서드
  async executeTransaction<T>(
    operations: (tx: Omit<PrismaClient, '$on' | '$connect' | '$disconnect' | '$use' | '$transaction' | '$extends'>) => Promise<T>
  ): Promise<T> {
    return this.$transaction(async (tx) => {
      return operations(tx);
    });
  }
} 