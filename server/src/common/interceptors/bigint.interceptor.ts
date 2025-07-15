import {
  Injectable,
  NestInterceptor,
  ExecutionContext,
  CallHandler,
} from '@nestjs/common';
import { Observable } from 'rxjs';
import { map } from 'rxjs/operators';

@Injectable()
export class BigIntInterceptor implements NestInterceptor {
  intercept(context: ExecutionContext, next: CallHandler): Observable<any> {
    return next.handle().pipe(map(data => this.transformBigInt(data)));
  }

  private transformBigInt(data: any): any {
    if (data === null || data === undefined) {
      return data;
    }
    if (typeof data === 'bigint') {
      return data.toString(); // BigInt를 문자열로 변환
    }
    if (data instanceof Date) {
      return data.toISOString(); // Date를 ISO 문자열로 변환
    }
    if (Array.isArray(data)) {
      return data.map(item => this.transformBigInt(item));
    }
    if (typeof data === 'object') {
      const res = {};
      for (const key in data) {
        if (Object.prototype.hasOwnProperty.call(data, key)) {
          res[key] = this.transformBigInt(data[key]);
        }
      }
      return res;
    }
    return data;
  }
} 