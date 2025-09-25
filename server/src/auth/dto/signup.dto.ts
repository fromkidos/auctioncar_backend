// auth/dto/social-signup.dto.ts
import { Transform } from 'class-transformer';
import { IsEnum, IsOptional, IsString, MinLength, MaxLength, ValidateIf } from 'class-validator';
import { SocialLoginProvider } from '@prisma/client';

export class SocialSignupDto {
  @IsEnum(SocialLoginProvider, { message: 'Invalid provider' })
  provider: SocialLoginProvider;

  @IsString()
  @MinLength(10, { message: 'Invalid social token' }) // 필요 시 규칙 조정
  socialToken: string;

  // 1) 빈 문자열이면 undefined로 변환
  @Transform(({ value }) => (typeof value === 'string' && value.trim() === '' ? undefined : value))
  // 2) 값이 있을 때만 아래 검증 실행
  @ValidateIf(o => o.nickname !== undefined)
  @IsString({ message: 'Nickname must be a string' })
  @MinLength(2, { message: 'Nickname must be at least 2 characters long' })
  @MaxLength(30, { message: 'Nickname must be at most 30 characters long' })
  nickname?: string;
}


// import { IsString, MinLength, MaxLength, IsEnum, IsNotEmpty } from 'class-validator';

// // 클라이언트에서 전송할 provider 값과 일치하는 Enum
// export enum SocialProviderClientDto {
//   GOOGLE = "GOOGLE",
//   KAKAO = "KAKAO",
//   NAVER = "NAVER",
// }

// export class SignupDto {
//   @IsEnum(SocialProviderClientDto, { message: 'Provider must be one of: GOOGLE, KAKAO, NAVER' })
//   @IsNotEmpty({ message: 'Provider cannot be empty' })
//   provider: SocialProviderClientDto;

//   @IsString()
//   @IsNotEmpty({ message: 'Social token cannot be empty' })
//   socialToken: string;

//   @IsString()
//   @MinLength(2, { message: 'Nickname must be at least 2 characters long' })
//   @MaxLength(10, { message: 'Nickname cannot be longer than 10 characters' })
//   @IsNotEmpty({ message: 'Nickname cannot be empty' })
//   nickname: string;
// } 