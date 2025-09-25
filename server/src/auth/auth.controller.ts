// auth.controller.ts
import {
  Controller,
  Post,
  Body,
  HttpStatus,
  HttpCode,
  BadRequestException,
  UnauthorizedException,
  ConflictException,
  InternalServerErrorException,
  Get,
  UseGuards,
  Request,
  UsePipes,
  ValidationPipe,
} from '@nestjs/common';
import { AuthService } from './auth.service';
import { SocialSignupDto } from './dto/signup.dto'; // ← DTO 경로/이름 일치
import { User } from '@prisma/client';
import { JwtAuthGuard } from './guards/jwt-auth.guard';

@Controller('auth')
export class AuthController {
  constructor(private readonly authService: AuthService) {}

  @Post('signup')
  @HttpCode(HttpStatus.CREATED)
  @UsePipes(
    new ValidationPipe({
      transform: true,      // DTO 타입/Transform 반영
      whitelist: true,      // DTO에 없는 필드 제거
      forbidNonWhitelisted: false,
      skipMissingProperties: false, // DTO에서 optional만 허용
    }),
  )
  async signup(@Body() signupDto: SocialSignupDto) {
    // 로깅: 토큰은 앞 10자만, 닉네임은 원본 출력 대신 길이만
    const tokenLog = typeof signupDto.socialToken === 'string'
      ? signupDto.socialToken.slice(0, 10) + '…'
      : '[no token]';
    const nickLog = typeof signupDto.nickname === 'string'
      ? `(len=${signupDto.nickname.length})`
      : '[undefined]';
    console.log(
      '[AuthController] Signup request received.',
      `provider=${signupDto.provider}, token=${tokenLog}, nickname=${nickLog}`,
    );

    try {
      // DTO에서 enum 검증이 끝났으므로 그대로 사용
      const provider = signupDto.provider;

      // 컨트롤러에서 한 번 더 공백 제거(서비스에서도 최종 기본값 처리함)
      const nickname = signupDto.nickname?.trim();

      const result = await this.authService.signupSocial(
        provider,
        signupDto.socialToken,
        nickname ?? '', // 빈 문자열/undefined 모두 서비스 기본값 로직으로 처리
      );

      console.log(
        '[AuthController] signupSocial OK.',
        `userId=${result.user?.id}, isNewUser=${result.isNewUser}`,
      );

      return {
        message: 'Signup successful!',
        user: result.user,           // 필요 시 select로 민감정보 제거
        isNewUser: result.isNewUser, // 새 가입 여부도 같이 반환
        accessToken: result.accessToken,
      };
    } catch (error: any) {
      // 서비스/파이프에서 올라온 표준 예외는 그대로 전달
      if (error instanceof BadRequestException || error instanceof UnauthorizedException) {
        throw error;
      }
      // Prisma 고유 제약
      if (error?.code === 'P2002' || error instanceof ConflictException) {
        throw new ConflictException(error.message || 'User with given details already exists.');
      }
      console.error('[AuthController][Signup] Unhandled error:', error);
      throw new InternalServerErrorException('An internal server error occurred.');
    }
  }

  @UseGuards(JwtAuthGuard)
  @Get('me')
  async getMe(@Request() req): Promise<User> {
    // JwtStrategy.validate 에서 반환한 sanitize된 user 객체
    return req.user;
  }
}
