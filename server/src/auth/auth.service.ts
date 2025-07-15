import { Injectable, BadRequestException, UnauthorizedException, ConflictException, InternalServerErrorException } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';
import { SocialLoginProvider, User } from '@prisma/client'; // Prisma Enum 및 User 타입 import
import { JwtService } from '@nestjs/jwt'; // JwtService import 추가

// 소셜 프로필 정보 인터페이스 (실제로는 각 소셜 SDK 응답에 맞게 정의)
interface VerifiedSocialProfile {
  providerId: string; // 소셜 플랫폼에서의 고유 ID
  email?: string;
  profileImageUrl?: string;
  // name?: string; // 소셜 프로필 이름은 사용자가 입력한 nickname으로 대체
}

// --- 실제 소셜 토큰 검증 함수 (반드시 각 플랫폼 SDK로 구현해야 함) ---
// 이 함수들은 예시이며, 실제로는 보안적으로 안전하게 토큰을 검증해야 합니다.
async function verifySocialToken(
  provider: SocialLoginProvider, // Prisma Enum 사용
  token: string
): Promise<VerifiedSocialProfile | null> {
  console.log(`[AuthService] Verifying token for ${provider} (token: ${token.substring(0,10)}...)`);
  // !!!! IMPORTANT: This is a placeholder. Replace with actual SDK calls. !!!!
  // 예: Google Sign-In, Kakao SDK, Naver SDK
  if (provider === SocialLoginProvider.GOOGLE && token === "valid_test_token_google") { // 클라이언트에서 보내는 "valid_test_token_google"과 일치하도록 수정
    return { 
      providerId: "google_test_1746840385443", // 제공해주신 고정 providerId
      email: "google_test_user@example.com",    // 제공해주신 고정 이메일
      profileImageUrl: "http://example.com/google_profile.jpg" 
    };
  } else if (provider === SocialLoginProvider.KAKAO && token === "valid_test_token_kakao") {
    return { providerId: `kakao_test_${Date.now()}`, email: "kakao_test_user@example.com" };
  }
  // ... 기타 provider ...
  console.error(`[AuthService] Token verification failed for ${provider}. Invalid test token.`);
  return null; // 검증 실패
}
// --- 실제 소셜 토큰 검증 함수 끝 ---

@Injectable()
export class AuthService {
  constructor(
    private readonly prisma: PrismaService,
    private readonly jwtService: JwtService, // JwtService 주입
  ) {}

  private generateJwt(user: User): string {
    const payload = { sub: user.id, email: user.email, provider: user.provider }; // 토큰에 포함될 정보
    return this.jwtService.sign(payload);
  }

  async signupSocial(
    provider: SocialLoginProvider,
    socialToken: string,
    nickname: string,
  ) {
    console.log('[AuthService] signupSocial called. Provider:', provider, 'Nickname:', nickname, 'Token:', socialToken.substring(0, 10) + '...');

    console.log('[AuthService] Calling verifySocialToken...');
    const verifiedProfile = await verifySocialToken(provider, socialToken);
    console.log('[AuthService] verifySocialToken returned:', JSON.stringify(verifiedProfile));

    if (!verifiedProfile) {
      console.error('[AuthService] Social token verification failed or profile not found.');
      throw new UnauthorizedException('Invalid social token or failed to retrieve profile.');
    }

    const { providerId, email, profileImageUrl } = verifiedProfile;
    console.log('[AuthService] Profile details - ProviderId:', providerId, 'Email:', email);

    // 2. 기존 사용자 확인
    console.log('[AuthService] Checking for existing user with provider:', provider, 'providerId:', providerId);
    let user = await this.prisma.user.findUnique({
      where: { provider_providerId: { provider, providerId } },
    });
    console.log('[AuthService] Existing user check result:', user ? JSON.stringify(user) : 'null');

    let isNewUser = false;
    if (user) {
      console.log('[AuthService] User exists. Checking if nickname update is needed. Current:', user.displayName, 'New:', nickname);
      // 기존 사용자일 경우, displayName 업데이트 (선택적)
      if (user.displayName !== nickname) {
        console.log('[AuthService] Updating existing user\'s nickname...');
        user = await this.prisma.user.update({
          where: { id: user.id },
          data: { displayName: nickname },
        });
        console.log('[AuthService] User nickname updated:', JSON.stringify(user));
      }
    } else {
      console.log('[AuthService] New user. Checking for email conflict if email exists:', email);
      // 3. (선택사항) 이메일 중복 확인 (신규 가입 시에만)
      if (email) {
        const userByEmail = await this.prisma.user.findUnique({ where: { email } });
        if (userByEmail) {
          console.error('[AuthService] Email conflict. Email:', email, 'is already associated with another account.');
          throw new ConflictException(`This email (${email}) is already associated with another account.`);
        }
        console.log('[AuthService] No email conflict found for:', email);
      }

      // 4. 새 사용자 생성
      console.log('[AuthService] Creating new user with providerId:', providerId, 'nickname:', nickname, 'email:', email);
      try {
        user = await this.prisma.user.create({
          data: {
            provider,
            providerId,
            displayName: nickname,
            email: email,
            profileImageUrl: profileImageUrl,
          },
        });
        isNewUser = true;
        console.log('[AuthService] New user created:', JSON.stringify(user));
      } catch (error: any) {
        console.error('[AuthService] Error during new user creation.');
        if (error.code === 'P2002') {
          console.error('[AuthService] Prisma Error P2002: Unique constraint failed.');
          throw new ConflictException('A user with these details already exists.');
        }
        console.error('[AuthService] Unexpected error details:', error.message);
        throw new InternalServerErrorException('Could not create user due to an server error.');
      }
    }
    
    // 5. JWT 토큰 생성
    console.log('[AuthService] Generating JWT for user:', user.id);
    const accessToken = this.generateJwt(user);
    console.log('[AuthService] JWT generated. Returning result.');

    return { user, isNewUser, accessToken };
  }
}
