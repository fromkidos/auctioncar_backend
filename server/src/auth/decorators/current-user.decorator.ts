import { createParamDecorator, ExecutionContext } from '@nestjs/common';
import { User } from '@prisma/client'; // User 타입 import 경로는 실제 User 모델 위치에 따라 조정될 수 있습니다.

export const CurrentUser = createParamDecorator(
  (data: unknown, ctx: ExecutionContext): User => {
    const request = ctx.switchToHttp().getRequest();
    return request.user; // Passport는 인증된 사용자 정보를 request.user에 저장합니다.
  },
); 