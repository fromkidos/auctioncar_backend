// auth/strategies/jwt.strategy.ts
import { Injectable } from '@nestjs/common';
import { PassportStrategy } from '@nestjs/passport';
import { ExtractJwt, Strategy } from 'passport-jwt';
import { PrismaService } from '../../prisma/prisma.service';

@Injectable()
export class JwtStrategy extends PassportStrategy(Strategy) {
  constructor(private readonly prisma: PrismaService) {
    super({
      jwtFromRequest: ExtractJwt.fromAuthHeaderAsBearerToken(),
      secretOrKey: process.env.JWT_SECRET!,   // 동일 시크릿 사용
      ignoreExpiration: false,
      // ← 여기로 이동!
      jsonWebTokenOptions: {
        clockTolerance: 5, // 초 단위 (jsonwebtoken 옵션)
      },
    });
  }

  async validate(payload: { sub: string }) {
    const user = await this.prisma.user.findUnique({
      where: { id: payload.sub },
      select: {
        id: true,
        provider: true,
        displayName: true,
        email: true,
        profileImageUrl: true,
        points: true,
        experiencePoints: true,
      },
    });
    return user ?? null;
  }
}
