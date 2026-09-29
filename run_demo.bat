@echo off
REM AI RADAR demo mode (Windows). No keys, no network needed.
pip install -r requirements.txt
python -m engine.main --demo
echo.
echo Open dashboard\index.html in your browser to preview.
pause
