import { Controller, Get } from '@nestjs/common';
import { AppService } from './app.service';
import { ApiTags, ApiOperation, ApiResponse } from '@nestjs/swagger';

@ApiTags('system')
@Controller()
export class AppController {
  constructor(private readonly appService: AppService) {}

  @Get()
  @ApiOperation({ summary: '기본 응답' })
  @ApiResponse({ status: 200, description: '성공' })
  getHello(): string {
    return this.appService.getHello();
  }

  @Get('health')
  @ApiOperation({ summary: '헬스체크' })
  @ApiResponse({ status: 200, description: '시스템 정상' })
  @ApiResponse({ status: 503, description: '시스템 오류' })
  async getHealth() {
    return this.appService.getHealthCheck();
  }
}
