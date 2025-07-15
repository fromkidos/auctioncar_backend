import { Injectable } from '@nestjs/common';
import { PrismaService } from './prisma/prisma.service';

@Injectable()
export class AppService {
  constructor(private readonly prisma: PrismaService) {}

  getHello(): string {
    return 'CourtAuction Car API Server is running! 🚗⚖️';
  }

  async getHealthCheck() {
    const timestamp = new Date().toISOString();
    
    try {
      // 데이터베이스 연결 상태 확인
      const dbHealth = await this.prisma.healthCheck();
      
      return {
        status: 'healthy',
        timestamp,
        uptime: process.uptime(),
        environment: process.env.NODE_ENV || 'development',
        version: process.env.npm_package_version || '1.0.0',
        database: dbHealth,
        memory: {
          used: Math.round(process.memoryUsage().heapUsed / 1024 / 1024) + 'MB',
          total: Math.round(process.memoryUsage().heapTotal / 1024 / 1024) + 'MB'
        }
      };
    } catch (error) {
      return {
        status: 'unhealthy',
        timestamp,
        uptime: process.uptime(),
        environment: process.env.NODE_ENV || 'development',
        error: error instanceof Error ? error.message : 'Unknown error',
        database: { status: 'unhealthy' }
      };
    }
  }
}
