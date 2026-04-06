module.exports = {
  apps: [
    {
      name: 'tracecheck-api',
      script: 'python',
      args: '-m uvicorn tracecheck.api.main:app --host 0.0.0.0 --port 8000 --reload',
      cwd: '/home/user/webapp',
      env: {
        NODE_ENV: 'development',
        PYTHONPATH: '/home/user/webapp',
      },
      watch: false,
      instances: 1,
      exec_mode: 'fork',
      interpreter: 'none',
      autorestart: true,
      max_restarts: 5,
    },
    {
      name: 'tracecheck-dashboard',
      script: 'python',
      args: '-m streamlit run frontend/app.py --server.port=8501 --server.address=0.0.0.0 --server.headless=true --browser.gatherUsageStats=false',
      cwd: '/home/user/webapp',
      env: {
        NODE_ENV: 'development',
        PYTHONPATH: '/home/user/webapp',
        TRACECHECK_API_URL: 'http://localhost:8000',
      },
      watch: false,
      instances: 1,
      exec_mode: 'fork',
      interpreter: 'none',
      autorestart: true,
      max_restarts: 5,
    }
  ]
}
