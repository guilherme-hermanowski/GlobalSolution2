#!/usr/bin/env bash
# Sobe backend + painel web em modo demonstração (sem hardware). Uso: bash scripts/start_demo.sh
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/src/backend"
[ -d .venv ] || python -m venv .venv
source .venv/bin/activate 2>/dev/null || source .venv/Scripts/activate
pip install -q -r requirements.txt
[ -f .env ] || cp .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 8000 &
BACK=$!
cd "$ROOT/src/web" && npm install --silent && npm run dev &
WEB=$!
echo "Backend: http://localhost:8000/docs | Painel: http://localhost:5173"
echo "Opcional: python src/iot/simulator/iot_simulator.py --scenario progressivo"
trap "kill $BACK $WEB" EXIT
wait
