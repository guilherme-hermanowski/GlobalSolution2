"""Simulador virtual do ESP32 — envia o MESMO contrato JSON do firmware real.

Uso:
  python iot_simulator.py                                  # cenário normal, a cada 3s
  python iot_simulator.py --scenario chuva_moderada
  python iot_simulator.py --scenario transbordamento_critico --interval 2
  python iot_simulator.py --scenario progressivo            # normal -> moderada -> crítico (demo ao vivo)
Durante a execução, digite 1/2/3 + Enter para trocar o cenário ao vivo (q para sair).
Dependência: httpx (já está no requirements do backend)."""
import argparse
import random
import sys
import threading
import time
from datetime import datetime, timezone

import httpx

PROFILES = {
    "normal":                  {"river": (80, 140),  "rain": (0, 5)},
    "chuva_moderada":          {"river": (220, 280), "rain": (35, 60)},
    "transbordamento_critico": {"river": (340, 400), "rain": (80, 100)},
}
KEYS = {"1": "normal", "2": "chuva_moderada", "3": "transbordamento_critico"}
state = {"scenario": "normal", "level": 100.0, "running": True}


def next_reading() -> dict:
    """Random walk em direção à faixa do cenário — curva realista, sem saltos bruscos."""
    lo, hi = PROFILES[state["scenario"]]["river"]
    target = random.uniform(lo, hi)
    state["level"] += (target - state["level"]) * 0.35 + random.gauss(0, 2)
    rain = round(random.uniform(*PROFILES[state["scenario"]]["rain"]), 1)
    return {
        "device_id": "sim-esp32-01",
        "river_level_cm": round(max(0, state["level"]), 1),
        "rain_intensity": rain,
        "rain_detected": rain > 10,
        "battery_v": round(random.uniform(3.6, 4.1), 2),
        "rssi": random.randint(-80, -50),
        "lat": -23.5505 + random.uniform(-0.002, 0.002),
        "lon": -46.6333 + random.uniform(-0.002, 0.002),
        "source": "simulated",
        "scenario": state["scenario"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def keyboard():
    for line in sys.stdin:
        k = line.strip().lower()
        if k == "q":
            state["running"] = False
            break
        if k in KEYS:
            state["scenario"] = KEYS[k]
            print(f"\n>>> Cenário alterado para: {state['scenario']}\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8000/api/telemetry")
    ap.add_argument("--token", default="fiap-gs-2026")
    ap.add_argument("--scenario", default="normal", choices=[*PROFILES, "progressivo"])
    ap.add_argument("--interval", type=float, default=3.0)
    args = ap.parse_args()

    progressive = args.scenario == "progressivo"
    state["scenario"] = "normal" if progressive else args.scenario
    threading.Thread(target=keyboard, daemon=True).start()
    print(f"Simulador ESP32 -> {args.url} | teclas: 1=normal 2=chuva 3=crítico q=sair")

    tick = 0
    with httpx.Client(timeout=5) as client:
        while state["running"]:
            if progressive:  # 10 leituras por fase
                state["scenario"] = list(PROFILES)[min(tick // 10, 2)]
            payload = next_reading()
            try:
                r = client.post(args.url, json=payload, headers={"X-Device-Token": args.token})
                info = r.json() if r.status_code == 201 else r.text
                print(f"[{state['scenario']:<24}] rio={payload['river_level_cm']:>6} cm  "
                      f"chuva={payload['rain_intensity']:>5}%  -> {r.status_code} {info}")
            except httpx.HTTPError as exc:  # backend fora do ar: simulador não quebra
                print(f"[WARN] backend indisponível ({exc.__class__.__name__}); nova tentativa em {args.interval}s")
            tick += 1
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
