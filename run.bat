@echo off
REM AI RADAR local run (Windows). Installs deps, runs full pipeline.
pip install -r requirements.txt
python -m engine.main
pause
