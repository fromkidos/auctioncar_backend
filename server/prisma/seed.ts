// prisma/seed.ts
import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

async function main() {
  // 예시: User 테이블에 초기값 삽입
  await prisma.courtInfo.createMany({
    data: [
      {
        court_name: '강릉지원',
        region: '강원',
        address: '강원 강릉시 동해대로 3288-18',
        latitude: 37.785482,
        longitude: 128.875976,
      },

      {
        court_name: '경주지원',
        region: '경북',
        address: '경북 경주시 화랑로 89',
        latitude: 35.84533,
        longitude: 129.210595,
      },

      {
        court_name: '고양지원',
        region: '경기',
        address: '경기 고양시 일산동구 장백로 209',
        latitude: 37.653336,
        longitude: 126.774922,
      },

      {
        court_name: '공주지원',
        region: '충남',
        address: '충남 공주시 한적2길 34-15',
        latitude: 36.477872,
        longitude: 127.141764,
      },

      {
        court_name: '광주지방법원',
        region: '광주',
        address: '광주 동구 준법로 7-12',
        latitude: 35.149624,
        longitude: 126.93511,
      },

      {
        court_name: '군산지원',
        region: '전북',
        address: '전북 군산시 법원로 68',
        latitude: 35.968105,
        longitude: 126.741117,
      },

      {
        court_name: '김천지원',
        region: '경북',
        address: '경북 김천시 물망골길 39',
        latitude: 36.144373,
        longitude: 128.096402,
      },

      {
        court_name: '남양주지원',
        region: '경기',
        address: '경기 남양주시 다산중앙로82번안길 161',
        latitude: 37.613846,
        longitude: 127.16868,
      },

      {
        court_name: '논산지원',
        region: '충남',
        address: '충남 논산시 강경읍 계백로 99',
        latitude: 36.154791,
        longitude: 127.012387,
      },


      {
        court_name: '대구서부지원',
        region: '대구',
        address: '대구 달서구 장산남로 30',
        latitude: 35.852861,
        longitude: 128.527533,
      },

      {
        court_name: '대구지방법원',
        region: '대구',
        address: '대구 수성구 동대구로 364',
        latitude: 35.862064,
        longitude: 128.628456,
      },

      {
        court_name: '대전지방법원',
        region: '대전',
        address: '대전 서구 둔산중로78번길 45',
        latitude: 36.354699,
        longitude: 127.389278,
      },

      {
        court_name: '동부지원',
        region: '부산',
        address: '부산 해운대구 재반로112번길 20',
        latitude: 35.189121,
        longitude: 129.129631,
      },

      {
        court_name: '마산지원',
        region: '경남',
        address: '경남 창원시 마산합포구 완월동7길 16',
        latitude: 35.19784,
        longitude: 128.566367,
      },

      {
        court_name: '목포지원',
        region: '전남',
        address: '전남 목포시 정의로 29',
        latitude: 34.813538,
        longitude: 126.446028,
      },

      {
        court_name: '밀양지원',
        region: '경남',
        address: '경남 밀양시 밀양대로 1993-20',
        latitude: 35.501442,
        longitude: 128.739461,
      },

      {
        court_name: '부산서부지원',
        region: '부산',
        address: '부산 강서구 명지국제7로 77',
        latitude: 35.097167,
        longitude: 128.90979,
      },

      {
        court_name: '부산지방법원',
        region: '부산',
        address: '부산 연제구 법원로 31',
        latitude: 35.192422,
        longitude: 129.073474,
      },

      {
        court_name: '부천지원',
        region: '경기',
        address: '경기 부천시 원미구 상일로 129',
        latitude: 37.491768,
        longitude: 126.757691,
      },

      {
        court_name: '상주지원',
        region: '경북',
        address: '경북 상주시 북천로 17-9',
        latitude: 36.427584,
        longitude: 128.15331,
      },

      {
        court_name: '서산지원',
        region: '충남',
        address: '충남 서산시 공림4로 24',
        latitude: 36.772876,
        longitude: 126.433378,
      },

      {
        court_name: '서울남부지방법원',
        region: '서울',
        address: '서울 양천구 신월로 386',
        latitude: 37.5215,
        longitude: 126.863728,
      },

      {
        court_name: '서울동부지방법원',
        region: '서울',
        address: '서울 송파구 법원로 101',
        latitude: 37.483246,
        longitude: 127.119544,
      },

      {
        court_name: '서울북부지방법원',
        region: '서울',
        address: '서울 도봉구 마들로 749',
        latitude: 37.677259,
        longitude: 127.047117,
      },

      {
        court_name: '서울중앙지방법원',
        region: '서울',
        address: '서울 서초구 서초중앙로 157',
        latitude: 37.496888,
        longitude: 127.011186,
      },

      {
        court_name: '성남지원',
        region: '경기',
        address: '경기 광주시 행정타운로 49-15',
        latitude: 37.453247,
        longitude: 127.159166,
      },

      {
        court_name: '속초지원',
        region: '강원',
        address: '강원 속초시 법대로 15',
        latitude: 38.213315,
        longitude: 128.592558,
      },

      {
        court_name: '수원지방법원',
        region: '경기',
        address: '경기 수원시 영통구 법조로 105',
        latitude: 37.290345,
        longitude: 127.069176,
      },

      {
        court_name: '순천지원',
        region: '전남',
        address: '전남 순천시 왕지로 21',
        latitude: 34.970932,
        longitude: 127.52509,
      },

      {
        court_name: '안동지원',
        region: '경북',
        address: '경북 안동시 강남로 304',
        latitude: 36.552574,
        longitude: 128.734246,
      },

      {
        court_name: '안산지원',
        region: '경기',
        address: '경기 안산시 단원구 광덕서로 75',
        latitude: 37.311781,
        longitude: 126.826316,
      },

      {
        court_name: '안양지원',
        region: '경기',
        address: '경기 안양시 동안구 관평로212번길 70',
        latitude: 37.396479,
        longitude: 126.96277,
      },

      {
        court_name: '여주지원',
        region: '경기',
        address: '경기 여주시 현암로 21-12',
        latitude: 37.313489,
        longitude: 127.633908,
      },

      {
        court_name: '영덕지원',
        region: '경북',
        address: '경북 영덕군 영덕읍 경동로 8337',
        latitude: 36.420001,
        longitude: 129.366366,
      },

      {
        court_name: '영월지원',
        region: '강원',
        address: '강원 영월군 영월읍 영월향교1길 53',
        latitude: 37.186835,
        longitude: 128.474111,
      },

      {
        court_name: '울산지방법원',
        region: '울산',
        address: '울산 남구 법대로 55',
        latitude: 35.539347,
        longitude: 129.287406,
      },

      {
        court_name: '의성지원',
        region: '경북',
        address: '경북 의성군 의성읍 군청길 67',
        latitude: 36.352776,
        longitude: 128.701013,
      },

      {
        court_name: '의정부지방법원',
        region: '경기',
        address: '경기 의정부시 녹양로34번길 23',
        latitude: 37.754717,
        longitude: 127.03409,
      },

      {
        court_name: '인천지방법원',
        region: '인천',
        address: '인천 미추홀구 소성로163번길 17',
        latitude: 37.442889,
        longitude: 126.667617,
      },

      {
        court_name: '전주지방법원',
        region: '전북',
        address: '전북 전주시 덕진구 가인로 33',
        latitude: 35.842492,
        longitude: 127.074703,
      },

      {
        court_name: '정읍지원',
        region: '전북',
        address: '전북 정읍시 수성6로 29',
        latitude: 35.585687,
        longitude: 126.86122,
      },


      {
        court_name: '제주지방법원',
        region: '제주',
        address: '제주 제주시 남광북5길 3',
        latitude: 33.494205,
        longitude: 126.535586,
      },

      
      {
        court_name: '제천지원',
        region: '충북',
        address: '충북 제천시 칠성로 53',
        latitude: 37.144453,
        longitude: 128.211387,
      },

      {
        court_name: '진주지원',
        region: '경남',
        address: '경남 진주시 진양호로 303',
        latitude: 35.181166,
        longitude: 128.064675,
      },


      {
        court_name: '창원지방법원',
        region: '창원',
        address: '경남 창원시 성산구 창이대로 681',
        latitude: 35.22408,
        longitude: 128.700883,
      },

      {
        court_name: '천안지원',
        region: '충남',
        address: '충남 천안시 동남구 청수14로 77',
        latitude: 36.785661,
        longitude: 127.154668,
      },


      {
        court_name: '청주지방법원',
        region: '청주',
        address: '충북 충주시 계명대로 103',
        latitude: 36.614091,
        longitude: 127.467829,
      },


      {
        court_name: '춘천지방법원',
        region: '춘천',
        address: '강원 춘천시 공지로 284',
        latitude: 37.867361,
        longitude: 127.734698,
      },
      {
        court_name: '충주지원',
        region: '충북',
        address: '충북 충주시 계명대로 103',
        latitude: 36.982905,
        longitude: 127.925992,
      },
      {
        court_name: '통영지원',
        region: '경남',
        address: '경남 통영시 용남면 동달안길 67',
        latitude: 34.865095,
        longitude: 128.446,
      },


      {
        court_name: '평택지원',
        region: '경기',
        address: '경기 평택시 평남로 1036',
        latitude: 37.010432,
        longitude: 127.096775,
      },


      {
        court_name: '포항지원',
        region: '경북',
        address: '경북 포항시 북구 법원로 181',
        latitude: 36.091785,
        longitude: 129.388809,
      },
      {
        court_name: '해남지원',
        region: '전남',
        address: '전남 해남군 해남읍 중앙1로 330',
        latitude: 34.575798,
        longitude: 126.591099,
      },
      {
        court_name: '홍성지원',
        region: '충남',
        address: '충남 홍성군 홍성읍 법원로 38',
        latitude: 36.600228,
        longitude: 126.649233,
      },
      
    ],
    skipDuplicates: true, // 중복 방지
  });

  // ProductInfo 테이블 초기화 (포인트 상품)
  await prisma.productInfo.createMany({
    data: [
      {
        productId: 'point_100',
        type: 'POINT',
        name: '100 포인트',
        description: '기본 포인트 팩 - 100 포인트를 추가합니다.',
        value: 100,
      },
      {
        productId: 'point_500',
        type: 'POINT',
        name: '500 포인트',
        description: '인기 포인트 팩 - 500 포인트를 추가합니다.',
        value: 500,
      },
      {
        productId: 'point_1000',
        type: 'POINT',
        name: '1,000 포인트',
        description: '추천 포인트 팩 - 1,000 포인트를 추가합니다.',
        value: 1000,
      },
      {
        productId: 'point_5000',
        type: 'POINT',
        name: '5,000 포인트',
        description: '프리미엄 포인트 팩 - 5,000 포인트 + 5%추가 포인트.',
        value: 5250,
      },
      {
        productId: 'point_10000',
        type: 'POINT',
        name: '10,000 포인트',
        description: '프리미엄 포인트 팩 - 10,000 포인트 + 10%추가 포인트.',
        value: 11000,
      },
      // 정기구독 상품들 - 월간 구독
      {
        productId: 'subscription_monthly',
        type: 'SUBSCRIPTION',
        name: '베이직 월간',
        description: '광고 제거',
        value: 2900, // 월 2,900원
        planId: 'monthly-plan',
        planTier: 'BASIC',
        features: ['광고 제거'],
      },
      {
        productId: 'subscription_monthly',
        type: 'SUBSCRIPTION',
        name: '플러스 월간',
        description: '광고 제거 + 모델 별 최근 낙찰 정보 제공',
        value: 3900, // 월 3,900원
        planId: 'monthly-plan-plus',
        planTier: 'PLUS',
        features: ['광고 제거', '모델 별 최근 낙찰 정보 제공'],
      },
      // 정기구독 상품들 - 연간 구독

    ],
    skipDuplicates: true, // 중복 방지
  });

  console.log('✅ ProductInfo seeded: point and subscription products created');

  // 다른 테이블도 이어서 초기화 가능
}

main()
  .then(() => {
    console.log('🌱 Seed completed');
    return prisma.$disconnect();
  })
  .catch((e) => {
    console.error('❌ Seed error', e);
    return prisma.$disconnect().finally(() => process.exit(1));
  });
