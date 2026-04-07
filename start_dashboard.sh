#!/bin/bash
cd /home/work/.openclaw/workspace/snn
exec .venv/bin/streamlit run frontend/app.py --server.port 8501 --server.headless true --server.address 0.0.0.0
