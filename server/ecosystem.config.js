module.exports = {
  apps: [
    {
      name: 'courtauction-server',
      script: 'dist/main.js',
      instances: 2, // CPU 코어 수에 맞게 조정
      exec_mode: 'cluster',
      
      // 환경 설정
      env: {
        NODE_ENV: 'production',
        PORT: 3000,
      },
      
      // 재시작 정책
      watch: false,
      max_memory_restart: '1G',
      restart_delay: 4000,
      
      // 로그 설정
      log_file: './logs/combined.log',
      out_file: './logs/out.log',
      error_file: './logs/error.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      
      // 자동 재시작 설정
      autorestart: true,
      max_restarts: 10,
      min_uptime: '10s',
      
      // 환경변수 파일 로드
      env_file: '.env',
      
      // 시간 설정
      time: true,
      
      // 인스턴스 간 로드 밸런싱
      instance_var: 'INSTANCE_ID',
      
      // 크론 작업 (옵션)
      cron_restart: '0 2 * * *', // 매일 새벽 2시 재시작
      
      // 메모리 사용량 모니터링
      pmx: {
        enabled: true,
        network: true,
        ports: true
      }
    }
  ],

  deploy: {
    production: {
      user: 'administrator',
      host: 'localhost',
      ref: 'origin/main',
      repo: 'git@github.com:your-username/courtauction.git',
      path: 'C:/courtauction',
      'pre-deploy-local': '',
      'post-deploy': 'cd backend/server && npm install && npm run build && pm2 reload ecosystem.config.js --env production',
      'pre-setup': ''
    }
  }
}; 