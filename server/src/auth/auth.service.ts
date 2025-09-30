// auth.service.ts
import {
  Injectable,
  UnauthorizedException,
  ConflictException,
  InternalServerErrorException,
} from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';
import { SocialLoginProvider, User } from '@prisma/client';
import { JwtService } from '@nestjs/jwt';
import { OAuth2Client } from 'google-auth-library';

interface VerifiedSocialProfile {
  providerId: string;
  email?: string;
  profileImageUrl?: string;
  name?: string;
}

@Injectable()
export class AuthService {
  private readonly googleClient: OAuth2Client | null;

  constructor(
    private readonly prisma: PrismaService,
    private readonly jwtService: JwtService,
  ) {
    this.googleClient = process.env.GOOGLE_CLIENT_ID
      ? new OAuth2Client(process.env.GOOGLE_CLIENT_ID)
      : null;

    if (!this.googleClient) {
      // 운영환경에서는 warn 정도로만 남기세요.
      console.warn('[AuthService] GOOGLE_CLIENT_ID is not set. Google login will fail.');
    }
  }

  private generateJwt(user: Pick<User, 'id' | 'email' | 'provider'>): string {
    const payload = { sub: user.id, email: user.email, provider: user.provider };
    return this.jwtService.sign(payload);
  }

  private trimOrUndefined(v?: string | null): string | undefined {
    if (typeof v !== 'string') return undefined;
    const t = v.trim();
    return t.length ? t : undefined;
  }

  private maskToken(token: string): string {
    return token ? token.slice(0, 10) + '…' : '';
  }

  /**
   * 소셜 토큰 검증 (플랫폼별 분기)
   */
  private async verifySocialToken(
    provider: SocialLoginProvider,
    token: string,
  ): Promise<VerifiedSocialProfile | null> {
    try {
      if (provider === SocialLoginProvider.GOOGLE) {
        if (!this.googleClient) return null;

        const ticket = await this.googleClient.verifyIdToken({
          idToken: token,
          audience: process.env.GOOGLE_CLIENT_ID,
        });
        const payload = ticket.getPayload();
        if (!payload || !payload.sub) return null;

        return {
          providerId: payload.sub,
          email: payload.email || undefined,
          name: payload.name || undefined,
          profileImageUrl: payload.picture || undefined,
        };
      }

      // TODO: 다른 프로바이더 추가 시 여기에 분기 추가
      return null;
    } catch (err) {
      console.error(`[AuthService] Token verification error for ${provider}:`, err);
      return null;
    }
  }

  /**
   * 소셜 회원가입/로그인(자동 가입)
   */
  async signupSocial(
    provider: SocialLoginProvider,
    socialToken: string,
    nickname: string, // 컨트롤러/DTO에서 transform + optional 검증 적용됨
  ) {
    console.log(
      '[AuthService] signupSocial:',
      `provider=${provider}, token=${this.maskToken(socialToken)}, nicknameLen=${nickname?.length ?? 0}`,
    );

    // 1) 소셜 토큰 검증
    const verifiedProfile = await this.verifySocialToken(provider, socialToken);
    if (!verifiedProfile) {
      throw new UnauthorizedException('Invalid social token or failed to retrieve profile.');
    }

    const providerId = verifiedProfile.providerId;
    const email = this.trimOrUndefined(verifiedProfile.email);
    const profileImageUrl = this.trimOrUndefined(verifiedProfile.profileImageUrl);
    const socialName = this.trimOrUndefined(verifiedProfile.name);

    // 2) 기존 사용자 조회 (민감 정보 최소화 select)
    let user = await this.prisma.user.findUnique({
      where: { provider_providerId: { provider, providerId } },
      select: {
        id: true,
        provider: true,
        providerId: true,
        displayName: true,
        email: true,
        profileImageUrl: true,
        points: true,
        experiencePoints: true,
        createdAt: true,
        updatedAt: true,
      },
    });

    let isNewUser = false;

    if (user) {
      // 2-1) 기존 사용자 닉네임 업데이트(선택)
      const trimmedNickname = this.trimOrUndefined(nickname);
      if (trimmedNickname && trimmedNickname !== user.displayName) {
        user = await this.prisma.user.update({
          where: { id: user.id },
          data: { displayName: trimmedNickname },
          select: {
            id: true,
            provider: true,
            providerId: true,
            displayName: true,
            email: true,
            profileImageUrl: true,
            points: true,
            experiencePoints: true,
            createdAt: true,
            updatedAt: true,
          },
        });
      }
    } else {
      // 3) 신규 가입: 이메일 충돌 검사(선택)
      if (email) {
        const userByEmail = await this.prisma.user.findUnique({
          where: { email },
          select: { id: true },
        });
        if (userByEmail) {
          throw new ConflictException(
            `This email (${email}) is already associated with another account.`,
          );
        }
      }

      // 4) 최종 닉네임 결정: 요청 닉네임 → 소셜 프로필 이름 → fallback
      const finalNickname =
        this.trimOrUndefined(nickname) ||
        this.trimOrUndefined(socialName) ||
        `user_${Date.now()}`;

      try {
        user = await this.prisma.user.create({
          data: {
            provider,
            providerId,
            displayName: finalNickname,
            email: email ?? undefined,
            profileImageUrl: profileImageUrl ?? null,
          },
          select: {
            id: true,
            provider: true,
            providerId: true,
            displayName: true,
            email: true,
            profileImageUrl: true,
            points: true,
            experiencePoints: true,
            createdAt: true,
            updatedAt: true,
          },
        });
        isNewUser = true;
      } catch (error: any) {
        if (error?.code === 'P2002') {
          // Unique constraint failed
          throw new ConflictException('A user with these details already exists.');
        }
        console.error('[AuthService] Unexpected create error:', error);
        throw new InternalServerErrorException('Could not create user due to a server error.');
      }
    }

    // 5) JWT 발급
    const accessToken = this.generateJwt({
      id: user.id,
      email: user.email ?? null,
      provider: user.provider,  // 이제 undefined 가능
    });

    return { user, isNewUser, accessToken };
  }
}
