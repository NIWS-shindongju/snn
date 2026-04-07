module.exports = {
  apps: [
    {
      name: "tracecheck-api",
      script: ".venv/bin/uvicorn",
      args: "tracecheck.api.main:app --host 0.0.0.0 --port 8000",
      cwd: "/home/work/.openclaw/workspace/snn",
      autorestart: true,
    },
    {
      name: "tracecheck-dashboard",
      script: ".venv/bin/streamlit",
      args: "run frontend/app.py --server.port 8501 --server.headless true --server.address 0.0.0.0",
      cwd: "/home/work/.openclaw/workspace/snn",
      autorestart: true,
    },
  ],
};
