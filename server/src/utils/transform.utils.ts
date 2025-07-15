import { ConfigService } from '@nestjs/config';

export function convertDataForClient(obj: any, visitedObjects = new WeakSet(), depth = 0): any {
  // 순환 참조 및 깊이 제한 보호
  if (depth > 10) {
    return '[Max depth reached]';
  }
  
  if (obj === null || obj === undefined) {
    return obj;
  }

  // 원시 타입은 그대로 반환
  if (typeof obj !== 'object') {
    return obj;
  }

  // 순환 참조 체크
  if (visitedObjects.has(obj)) {
    return '[Circular reference]';
  }

  try {
    // 방문한 객체 표시
    visitedObjects.add(obj);

    // Date 객체 처리
    if (obj instanceof Date) {
      return obj.toISOString();
    }

    // Array 처리
    if (Array.isArray(obj)) {
      return obj.map(item => convertDataForClient(item, visitedObjects, depth + 1));
    }

    // Object 처리
    const convertedObj: any = {};

    for (const [key, value] of Object.entries(obj)) {
      if (typeof value === 'bigint') {
        convertedObj[key] = value.toString();
      } else if (value instanceof Date) {
        convertedObj[key] = value.toISOString();
      } else if (value !== null && typeof value === 'object') {
        convertedObj[key] = convertDataForClient(value, visitedObjects, depth + 1);
      } else {
        convertedObj[key] = value;
      }
    }

    return convertedObj;
  } catch (error) {
    console.error('Error in convertDataForClient:', error);
    return '[Conversion error]';
  } finally {
    // 방문한 객체에서 제거 (다른 경로에서 재방문 가능하도록)
    visitedObjects.delete(obj);
  }
}

export function toWebImageUrl(dbFilePath: string | null | undefined, configService: ConfigService): string | null {
  try {
    const serverBaseUrl = configService.get<string>('SERVER_BASE_URL');
    
    if (!dbFilePath) {
      return null;
    }
    
    // 이미 완전한 URL인 경우 그대로 반환
    if (dbFilePath.startsWith('http://') || dbFilePath.startsWith('https://')) {
      return dbFilePath;
    }

    const staticPrefix = '/static';
    const imageBasePath = '/uploads/auction_images/';
    
    const filename = dbFilePath.includes('/') ? dbFilePath.substring(dbFilePath.lastIndexOf('/') + 1) : dbFilePath;

    if (!serverBaseUrl) {
      console.error('SERVER_BASE_URL is not defined in environment variables');
      return null;
    }

    const finalUrl = `${serverBaseUrl}${staticPrefix}${imageBasePath}${filename}`;
    return finalUrl;
  } catch (error) {
    console.error(`Error generating web URL for: ${dbFilePath}`, error);
    return null;
  }
} 