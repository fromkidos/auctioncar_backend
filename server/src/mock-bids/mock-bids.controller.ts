import {
  Controller,
  Post,
  Body,
  Get,
  Param,
  UseGuards,
  Req,
  Logger,
} from '@nestjs/common';
import { MockBidsService } from './mock-bids.service';
import { CreateMockBidDto } from './dto/create-mock-bid.dto';
import { ApiTags, ApiOperation, ApiResponse, ApiBearerAuth, ApiParam } from '@nestjs/swagger';
import { JwtAuthGuard } from '../auth/guards/jwt-auth.guard'; // 실제 JwtAuthGuard 경로로 수정
import { CurrentUser } from '../auth/decorators/current-user.decorator'; // 실제 CurrentUser 데코레이터 경로로 수정 (가정)
import { User } from '@prisma/client'; // Prisma User 모델 import

// 임시 JwtAuthGuard 및 CurrentUser 데코레이터 정의 제거
// export class JwtAuthGuard extends AuthGuard('jwt') {}
// export const CurrentUser = createParamDecorator(
//   (data: unknown, ctx: ExecutionContext) => {
//     const request = ctx.switchToHttp().getRequest();
//     return request.user;
//   },
// );

@ApiTags('mock-bids')
@ApiBearerAuth() // JWT 인증을 사용하는 API 임을 명시
@Controller('mock-bids')
export class MockBidsController {
  private readonly logger = new Logger(MockBidsController.name);

  constructor(private readonly mockBidsService: MockBidsService) {}

  @Post()
  @UseGuards(JwtAuthGuard)
  @ApiOperation({ summary: '모의 입찰 생성', description: '사용자가 특정 경매에 모의 입찰을 합니다.' })
  @ApiResponse({ status: 201, description: '모의 입찰 성공적으로 생성됨.' })
  @ApiResponse({ status: 400, description: '잘못된 요청 데이터입니다.' })
  @ApiResponse({ status: 401, description: '인증되지 않은 사용자입니다.' })
  @ApiResponse({ status: 403, description: '입찰 권한이 없거나 이미 입찰했습니다.' })
  @ApiResponse({ status: 404, description: '경매 정보를 찾을 수 없습니다.' })
  async createMockBid(
    @Body() createMockBidDto: CreateMockBidDto,
    @CurrentUser() user: User, // CurrentUser 데코레이터를 통해 인증된 사용자 정보 주입
  ) {
    this.logger.log(`User ${user.id} creating mock bid for auction ${createMockBidDto.auctionNo}`);
    return this.mockBidsService.createMockBid(createMockBidDto, user);
  }

  @Get('my-bids') // 경로를 /users/me/mock-bids 대신 /mock-bids/my-bids 로 변경 (선택)
  @UseGuards(JwtAuthGuard)
  @ApiOperation({ summary: '나의 모의 입찰 내역 조회', description: '현재 로그인한 사용자의 모든 모의 입찰 내역을 조회합니다.' })
  @ApiResponse({ status: 200, description: '모의 입찰 내역 조회 성공.' })
  @ApiResponse({ status: 401, description: '인증되지 않은 사용자입니다.' })
  async getMyMockBids(@CurrentUser() user: User) {
    this.logger.log(`Fetching mock bids for current user ${user.id}`);
    return this.mockBidsService.findMyMockBids(user.id);
  }

  // 특정 경매의 모의 입찰 목록 조회 (경로를 /auctions/:auctionNo/mock-bids 대신 /mock-bids/auction/:auctionNo 로 변경)
  @Get('auction/:auctionNo')
  // @UseGuards(JwtAuthGuard) // 이 API의 접근 제어 정책에 따라 주석 처리 또는 다른 Guard 사용
  @ApiOperation({ summary: '특정 경매의 모의 입찰 내역 조회', description: '특정 경매 번호에 해당하는 모든 모의 입찰 내역을 조회합니다. (필요시 관리자 권한)' })
  @ApiParam({ name: 'auctionNo', description: '경매 번호', example: '2024타경12345-1' })
  @ApiResponse({ status: 200, description: '모의 입찰 내역 조회 성공.' })
  @ApiResponse({ status: 404, description: '경매 정보를 찾을 수 없습니다.' })
  async getMockBidsByAuctionNo(@Param('auctionNo') auctionNo: string) {
    this.logger.log(`Fetching mock bids for auction ${auctionNo}`);
    return this.mockBidsService.getMockBidsByAuctionNo(auctionNo);
  }

  // 새로운 라우트 추가
  @Get('auction/:auctionNo/date/:saleDateStr')
  @ApiOperation({ summary: '특정 경매, 특정 매각기일의 모의 입찰 내역 조회', description: '특정 경매 번호와 매각기일에 해당하는 모든 모의 입찰 내역을 조회합니다.' })
  @ApiParam({ name: 'auctionNo', description: '경매 번호', example: '2024타경12345-1' })
  @ApiParam({ name: 'saleDateStr', description: '매각기일 (YYYY-MM-DD)', example: '2024-05-20' })
  @ApiResponse({ status: 200, description: '모의 입찰 내역 조회 성공.' })
  @ApiResponse({ status: 400, description: '잘못된 날짜 형식입니다.' })
  @ApiResponse({ status: 404, description: '경매 정보를 찾을 수 없습니다.' })
  async getMockBidsByAuctionNoAndSaleDate(
    @Param('auctionNo') auctionNo: string,
    @Param('saleDateStr') saleDateStr: string,
  ) {
    this.logger.log(
      `Fetching mock bids for auction ${auctionNo} on sale date ${saleDateStr}`,
    );
    const result = await this.mockBidsService.getMockBidsByAuctionNoAndSaleDate(
      auctionNo,
      saleDateStr,
    );
    this.logger.debug(`Data from service in controller before sending to client: ${JSON.stringify(result, (key, value) => typeof value === 'bigint' ? value.toString() : value)}`);
    return result;
  }
} 