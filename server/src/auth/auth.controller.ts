import { Controller, Post, Body, HttpStatus, HttpCode, BadRequestException, UnauthorizedException, ConflictException, InternalServerErrorException, Get, UseGuards, Request } from '@nestjs/common';
import { AuthService } from './auth.service';
import { SignupDto } from './dto/signup.dto'; // DTO (Data Transfer Object) 사용
import { SocialLoginProvider, User } from '@prisma/client'; // Prisma Enum 및 User 타입 import
import { JwtAuthGuard } from './guards/jwt-auth.guard'; // JwtAuthGuard import

@Controller('auth') // 라우트 경로: /auth
export class AuthController {
  constructor(private readonly authService: AuthService) {}

  @Post('signup')
  @HttpCode(HttpStatus.CREATED)
  async signup(@Body() signupDto: SignupDto) { // @Body 데코레이터로 요청 본문을 DTO에 바인딩
    console.log('[AuthController] Signup request received. Body:', JSON.stringify(signupDto)); // 요청 본문 로깅

    try {
      // DTO에서 provider 값을 Prisma Enum 타입으로 변환
      const providerEnum = signupDto.provider as unknown as SocialLoginProvider;
      if (!Object.values(SocialLoginProvider).includes(providerEnum)) {
        console.warn('[AuthController] Invalid provider:', signupDto.provider); // 잘못된 provider 로깅
        throw new BadRequestException('Invalid provider specified.');
      }

      console.log('[AuthController] Calling authService.signupSocial with provider:', providerEnum, 'nickname:', signupDto.nickname); // 서비스 호출 전 로깅
      const result = await this.authService.signupSocial(
        providerEnum,
        signupDto.socialToken,
        signupDto.nickname,
      );
      console.log('[AuthController] authService.signupSocial successful. Result:', JSON.stringify(result)); // 서비스 호출 성공 로깅
      return {
        message: 'Signup successful!',
        user: result.user,
        accessToken: result.accessToken, // 필요시 JWT 토큰
      };
    } catch (error) {
      if (error instanceof BadRequestException || error instanceof UnauthorizedException) {
        throw error;
      }
      if (error.code === 'P2002' || error instanceof ConflictException) { // Prisma 고유 제약 조건 또는 서비스 로직상 충돌
        throw new ConflictException(error.message || 'User with given details already exists.');
      }
      console.error('[Signup Controller Error]', error);
      throw new InternalServerErrorException('An internal server error occurred.');
    }
  }

  @UseGuards(JwtAuthGuard)
  @Get('me')
  async getMe(@Request() req): Promise<User> {
    // JwtStrategy의 validate에서 반환된 사용자 객체 (민감 정보 제외됨)
    return req.user;
  }
}
