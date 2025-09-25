// auth/guards/jwt-auth.guard.ts
import { ExecutionContext, Injectable, UnauthorizedException } from '@nestjs/common';
import { AuthGuard } from '@nestjs/passport';

@Injectable()
export class JwtAuthGuard extends AuthGuard('jwt') {
  handleRequest(err: any, user: any, info: any, context: ExecutionContext) {
    const req = context.switchToHttp().getRequest();
    const authz = req.headers?.authorization ?? '(none)';
    // info?.message는 passport-jwt의 실패 원인: 'No auth token', 'jwt expired', 'invalid signature', 'jwt malformed' 등
    if (err || !user) {
      console.warn('[JwtAuthGuard] Unauthorized', {
        path: req.originalUrl,
        authz,
        info: info?.message ?? info,
        err: err?.message ?? err,
      });
      throw err || new UnauthorizedException();
    }
    return user;
  }
}
