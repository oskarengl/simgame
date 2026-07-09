@echo off
echo Activating virtual environment and starting GPU simulation...
call .venv\Scripts\activate.bat
python main_gpu.py
pause

