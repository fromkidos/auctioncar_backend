import { Injectable, UnauthorizedException, InternalServerErrorException } from '@nestjs/common';
import { PassportStrategy } from '@nestjs/passport';
import { ExtractJwt, Strategy } from 'passport-jwt';
import { ConfigService } from '@nestjs/config';
import { PrismaService } from '../../prisma/prisma.service'; // PrismaService 경로 수정 필요 시 확인
import { User } from '@prisma/client'; // User 타입 경로 수정 필요 시 확인

@Injectable()
export class JwtStrategy extends PassportStrategy(Strategy) {
  constructor(
    private readonly configService: ConfigService,
    private readonly prisma: PrismaService,
  ) {
    const jwtSecret = configService.get<string>('JWT_SECRET');
    if (!jwtSecret) {
      // JWT_SECRET이 .env 파일에 없거나 로드되지 않은 경우, 서버 시작 시 명확한 에러를 발생시킵니다.
      throw new InternalServerErrorException('JWT_SECRET environment variable is not set.');
    }
    super({
      jwtFromRequest: ExtractJwt.fromAuthHeaderAsBearerToken(),
      ignoreExpiration: false,
      secretOrKey: jwtSecret, // 이제 jwtSecret은 확실히 string 타입입니다.
    });
  }

  async validate(payload: { sub: string; email: string }): Promise<User> {
    console.log('[JWT Strategy] Validating payload:', { sub: payload.sub, email: payload.email });
    
    const user = await this.prisma.user.findUnique({
      where: { id: payload.sub },
    });

    console.log('[JWT Strategy] User lookup result:', user ? `Found user ${user.id}` : 'User not found');

    if (!user) {
      console.log('[JWT Strategy] User not found, throwing UnauthorizedException');
      throw new UnauthorizedException('User not found or token is invalid.');
    }
    // 필요하다면 여기서 반환되는 사용자 정보에서 민감한 정보를 제거할 수 있습니다.
    // delete user.password; // 예시: User 모델에 password 필드가 있다면
    return user;
  }
} 