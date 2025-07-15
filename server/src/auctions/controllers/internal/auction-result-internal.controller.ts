import { Controller, Post, Body, UseGuards, Logger, Inject, CanActivate, ExecutionContext, UnauthorizedException, InternalServerErrorException } from '@nestjs/common';
import { AuctionResultService } from '../../services/auction-result.service';
import { UpdateAuctionResultDto } from '../../dto/update-auction-result.dto';
import { ApiTags, ApiOperation, ApiResponse, ApiBody, ApiSecurity } from '@nestjs/swagger';
import { ConfigService } from '@nestjs/config';

// @Injectable() // CanActivate를 구현하는 클래스는 Injectable일 필요는 없음 (모듈에 providers로 등록 안 할 경우)
class ApiKeyAuthGuard implements CanActivate { // AuthGuard 상속 제거, CanActivate 직접 구현
  constructor(@Inject(ConfigService) private configService: ConfigService) {}

  canActivate(context: ExecutionContext): boolean {
    const request = context.switchToHttp().getRequest();
    const apiKey = request.headers['x-api-key'];
    const validApiKey = this.configService.get<string>('INTERNAL_API_KEY');

    if (!validApiKey) {
      // .env에 INTERNAL_API_KEY가 설정되지 않은 경우, 프로덕션에서는 에러를 발생시키거나 로깅 후 false 반환
      this.logger.error('INTERNAL_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.');
      throw new InternalServerErrorException('서버 설정 오류'); // 또는 false 반환하여 403 Forbidden
    }

    if (apiKey === validApiKey) {
      return true;
    }
    // API 키가 유효하지 않으면 UnauthorizedException 발생 (401 Unauthorized)
    // 또는 그냥 false를 반환하여 403 Forbidden을 발생시킬 수도 있습니다.
    // NestJS는 false를 반환하면 기본적으로 403 Forbidden을 응답합니다.
    // 명시적으로 401을 원하면 예외를 던지는 것이 좋습니다.
    throw new UnauthorizedException('유효하지 않은 API 키입니다.');
  }
  // Logger를 사용하려면 클래스 멤버로 선언 필요
  private readonly logger = new Logger(ApiKeyAuthGuard.name);
}

@ApiTags('internal-auctions')
// @ApiSecurity('ApiKeyAuth') // Swagger 설정은 passport 연동 시 더 의미있음, 필요시 유지 또는 다른 방식 설정
@Controller('internal/auctions')
export class AuctionResultInternalController {
  private readonly logger = new Logger(AuctionResultInternalController.name);

  constructor(
    private readonly auctionResultService: AuctionResultService,
    // ConfigService는 ApiKeyAuthGuard가 직접 주입받으므로 컨트롤러에서는 제거됨
    ) {}

  @Post('result')
  @UseGuards(ApiKeyAuthGuard) 
  @ApiOperation({ summary: '낙찰 결과 업데이트 (내부용)', description: 'Python 크롤러가 호출하여 경매 낙찰 결과를 업데이트합니다.' })
  @ApiBody({ type: UpdateAuctionResultDto })
  @ApiResponse({ status: 201, description: '낙찰 결과 성공적으로 업데이트됨.' })
  @ApiResponse({ status: 400, description: '잘못된 요청 데이터입니다.' })
  @ApiResponse({ status: 401, description: 'API 키 인증 실패 (잘못된 키).', type: UnauthorizedException })
  @ApiResponse({ status: 500, description: '서버 내부 오류 (API 키 미설정 등).', type: InternalServerErrorException })
  async updateAuctionResult(@Body() updateAuctionResultDto: UpdateAuctionResultDto) {
    this.logger.log(
      `[${updateAuctionResultDto.auction_no}] 낙찰 결과 업데이트 요청 수신.`,
    );
    // 서비스 호출 로직은 동일
    try {
      const resultFromService = await this.auctionResultService.updateAuctionResult(
        updateAuctionResultDto,
      );
      this.logger.log(
        `[${updateAuctionResultDto.auction_no}] 낙찰 결과 처리 완료.`,
      );

      // BigInt 필드를 문자열로 변환
      // AuctionResult 타입에 BigInt 필드가 더 있다면 여기에 추가해야 합니다.
      // 예를 들어, Prisma 스키마에서 AuctionResult 모델의 appraisal_value, min_bid_price, sale_price 등이 BigInt일 경우.
      const cleanedResult = resultFromService ? {
        ...resultFromService,
        // appraisal_value, min_bid_price, sale_price 등이 BigInt 타입이라고 가정
        // 실제 AuctionResult 타입 정의를 보고 BigInt인 필드들을 변환해야 합니다.
        ...(resultFromService.appraisal_value !== undefined && resultFromService.appraisal_value !== null
          ? { appraisal_value: resultFromService.appraisal_value.toString() }
          : { appraisal_value: null }),
        ...(resultFromService.min_bid_price !== undefined && resultFromService.min_bid_price !== null
          ? { min_bid_price: resultFromService.min_bid_price.toString() }
          : { min_bid_price: null }),
        ...(resultFromService.sale_price !== undefined && resultFromService.sale_price !== null
          ? { sale_price: resultFromService.sale_price.toString() }
          : { sale_price: null }),
        // 만약 다른 BigInt 필드가 있다면 여기에 추가
        // 예: some_other_bigint_field: resultFromService.some_other_bigint_field ? resultFromService.some_other_bigint_field.toString() : null,
      } : null;

      return { message: 'Auction result updated successfully', data: cleanedResult };
    } catch (error) {
      this.logger.error(
        `[${updateAuctionResultDto.auction_no}] 낙찰 결과 처리 중 오류: ${error.message}`,
        error.stack,
      );
      throw error; 
    }
  }
} 