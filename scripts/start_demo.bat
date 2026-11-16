@echo off
REM Demo no Windows: abre backend e painel web em janelas separadas
cd /d %~dp0\..\src\backend
if not exist .venv python -m venv .venv
call .venv\Scripts\activate
pip install -q -r requirements.txt
if not exist .env copy .env.example .env
start "AquaGuard API" cmd /k "uvicorn app.main:app --host 0.0.0.0 --port 8000"
cd ..\web
start "AquaGuard Painel" cmd /k "npm install && npm run dev"
echo Backend: http://localhost:8000/docs  ^|  Painel: http://localhost:5173
