import { IsString, MinLength, MaxLength, IsEnum, IsNotEmpty } from 'class-validator';

// 클라이언트에서 전송할 provider 값과 일치하는 Enum
export enum SocialProviderClientDto {
  GOOGLE = "GOOGLE",
  KAKAO = "KAKAO",
  NAVER = "NAVER",
}

export class SignupDto {
  @IsEnum(SocialProviderClientDto, { message: 'Provider must be one of: GOOGLE, KAKAO, NAVER' })
  @IsNotEmpty({ message: 'Provider cannot be empty' })
  provider: SocialProviderClientDto;

  @IsString()
  @IsNotEmpty({ message: 'Social token cannot be empty' })
  socialToken: string;

  @IsString()
  @MinLength(2, { message: 'Nickname must be at least 2 characters long' })
  @MaxLength(10, { message: 'Nickname cannot be longer than 10 characters' })
  @IsNotEmpty({ message: 'Nickname cannot be empty' })
  nickname: string;
} 