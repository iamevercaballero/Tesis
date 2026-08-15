#!/usr/bin/env python3
"""
Generador de logs para tesis: Detección de anomalías con Data Mining.

Uso:
  python log_generator.py run --duration 120 --anomaly-ratio 0.08
  python log_generator.py normal
  python log_generator.py brute-force
  python log_generator.py server-errors
  python log_generator.py ddos
  python log_generator.py scan
  python log_generator.py restart
  python log_generator.py all-anomalies
"""

import argparse
import json
import random
import sys
import time
from datetime import datetime
from pathlib import Path

LOG_DIR = Path(__file__).parent.parent / "logs" / "app"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "app.log"

# ── IPs ────────────────────────────────────────────────────────────────────────
NORMAL_IPS = [f"192.168.1.{i}" for i in range(10, 40)] + \
             [f"10.0.0.{i}" for i in range(1, 25)]
ATTACKER_IP = "203.0.113.99"
BOT_IPS = [f"45.33.{i}.{j}" for i in range(1, 6) for j in range(1, 12)]

# ── Endpoints ──────────────────────────────────────────────────────────────────
NORMAL_ENDPOINTS = ["/", "/login", "/api/data", "/api/users", "/health", "/static/app.js"]
SCAN_PATHS = [
    "/admin", "/wp-admin", "/.env", "/config.php", "/backup.zip",
    "/.git/config", "/etc/passwd", "/api/v1/users", "/phpmyadmin",
    "/shell.php", "/debug", "/metrics", "/actuator/env", "/.htaccess",
    "/server-status", "/web.config", "/credentials.json",
]

# ── User agents ────────────────────────────────────────────────────────────────
UA_BROWSERS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Safari/537",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Firefox/121",
]
UA_BOT = "python-requests/2.28.0"
UA_SCANNER = "Nikto/2.1.6"


# ── Helpers ────────────────────────────────────────────────────────────────────
def now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def write(entry: dict):
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


def base(scenario: str, label: str) -> dict:
    return {
        "timestamp": now(),
        "service": random.choice(["api", "auth", "webapp"]),
        "host": "server01",
        "scenario": scenario,
        "label": label,
    }


# ── Escenario 1: Tráfico normal ────────────────────────────────────────────────
def gen_normal():
    entry = base("normal_traffic", "normal")
    status = random.choices(
        [200, 200, 301, 304, 404],
        weights=[70, 10, 8, 7, 5]
    )[0]
    entry.update({
        "ip": random.choice(NORMAL_IPS),
        "method": random.choices(["GET", "POST", "PUT"], weights=[75, 20, 5])[0],
        "endpoint": random.choice(NORMAL_ENDPOINTS),
        "status_code": status,
        "response_time_ms": random.randint(20, 300),
        "bytes_sent": random.randint(512, 8192),
        "severity": "info",
        "user_agent": random.choice(UA_BROWSERS),
    })
    write(entry)


# ── Escenario 2: Brute force de login ──────────────────────────────────────────
def gen_brute_force(burst: int = 40):
    """Múltiples 401 desde la misma IP en corto tiempo → anomalía clásica."""
    print(f"  [brute-force] {burst} intentos desde {ATTACKER_IP}")
    for _ in range(burst):
        entry = base("brute_force", "anomaly")
        entry.update({
            "ip": ATTACKER_IP,
            "method": "POST",
            "endpoint": "/login",
            "status_code": 401,
            "response_time_ms": random.randint(5, 45),
            "bytes_sent": 128,
            "severity": "warning",
            "user_agent": UA_BOT,
            "failed_reason": "invalid_credentials",
        })
        write(entry)
        time.sleep(0.02)


# ── Escenario 3: Pico de errores 500 ──────────────────────────────────────────
def gen_server_errors(count: int = 25):
    """Errores internos con response_time alto → degradación del servicio."""
    print(f"  [server-errors] {count} errores 500")
    for _ in range(count):
        entry = base("server_error_spike", "anomaly")
        entry.update({
            "ip": random.choice(NORMAL_IPS),
            "method": random.choice(["GET", "POST"]),
            "endpoint": random.choice(["/api/data", "/api/users", "/login"]),
            "status_code": 500,
            "response_time_ms": random.randint(3000, 12000),
            "bytes_sent": 256,
            "severity": "error",
            "user_agent": random.choice(UA_BROWSERS),
            "error_msg": "Internal Server Error",
        })
        write(entry)


# ── Escenario 4: DDoS simulado ─────────────────────────────────────────────────
def gen_ddos(count: int = 120):
    """Flood desde muchas IPs distintas, respuestas rápidas o 429/503."""
    print(f"  [ddos] {count} requests de flood desde {len(BOT_IPS)} IPs")
    for _ in range(count):
        entry = base("ddos_flood", "anomaly")
        entry.update({
            "ip": random.choice(BOT_IPS),
            "method": "GET",
            "endpoint": "/",
            "status_code": random.choices([200, 429, 503], weights=[40, 35, 25])[0],
            "response_time_ms": random.randint(1, 25),
            "bytes_sent": random.randint(64, 256),
            "severity": "warning",
            "user_agent": UA_BOT,
        })
        write(entry)


# ── Escenario 5: Escaneo de rutas ──────────────────────────────────────────────
def gen_path_scan():
    """Scanner probando rutas sensibles → muchos 404/403 secuenciales."""
    print(f"  [scan] {len(SCAN_PATHS)} rutas escaneadas desde {ATTACKER_IP}")
    for path in SCAN_PATHS:
        entry = base("path_scan", "anomaly")
        entry.update({
            "ip": ATTACKER_IP,
            "method": "GET",
            "endpoint": path,
            "status_code": random.choices([404, 403, 200], weights=[70, 25, 5])[0],
            "response_time_ms": random.randint(5, 60),
            "bytes_sent": 128,
            "severity": "warning",
            "user_agent": UA_SCANNER,
        })
        write(entry)
        time.sleep(0.05)


# ── Escenario 6: Caída y reinicio de contenedor ────────────────────────────────
def gen_container_restart():
    """Simula logs de sistema ante un crash y reinicio del servicio."""
    print("  [restart] Simulando caída y reinicio de contenedor")
    events = [
        ("container_stopping", "critical", "Container received SIGTERM signal"),
        ("container_stopped",  "critical", "Container exited with code 137 (OOMKilled)"),
        ("container_starting", "info",     "Starting container api-service v1.4.2"),
        ("healthcheck_fail",   "warning",  "Healthcheck failed, retrying (1/3)"),
        ("healthcheck_fail",   "warning",  "Healthcheck failed, retrying (2/3)"),
        ("container_ready",    "info",     "Container healthy, accepting connections"),
    ]
    for event_type, severity, msg in events:
        label = "anomaly" if severity in ("critical", "warning") else "normal"
        entry = base("container_restart", label)
        entry.update({
            "ip": "127.0.0.1",
            "method": "SYSTEM",
            "endpoint": "/internal",
            "status_code": 0,
            "response_time_ms": 0,
            "bytes_sent": 0,
            "severity": severity,
            "event_type": event_type,
            "error_msg": msg,
        })
        write(entry)
        time.sleep(0.1)


# ── Modo continuo ──────────────────────────────────────────────────────────────
def run_continuous(duration_seconds: int = 60, anomaly_ratio: float = 0.05):
    """
    Genera logs de forma continua mezclando tráfico normal con anomalías.
    Útil para simular un entorno real durante el tiempo que necesites.
    """
    print(f"Generando logs por {duration_seconds}s | ratio anomalías: {anomaly_ratio:.0%}")
    print(f"Archivo destino: {LOG_FILE}\n")

    end_time = time.time() + duration_seconds
    total = 0
    anomalies = 0

    while time.time() < end_time:
        if random.random() < anomaly_ratio:
            scenario = random.choice(["brute", "error", "ddos", "scan", "restart"])
            if scenario == "brute":
                gen_brute_force(burst=random.randint(8, 20))
                anomalies += 1
            elif scenario == "error":
                gen_server_errors(count=random.randint(5, 15))
                anomalies += 1
            elif scenario == "ddos":
                gen_ddos(count=random.randint(15, 40))
                anomalies += 1
            elif scenario == "scan":
                gen_path_scan()
                anomalies += 1
            elif scenario == "restart":
                gen_container_restart()
                anomalies += 1
        else:
            gen_normal()

        total += 1
        remaining = int(end_time - time.time())
        if total % 50 == 0:
            print(f"  {total} eventos | {anomalies} ráfagas anómalas | {remaining}s restantes")
        time.sleep(random.uniform(0.005, 0.05))

    print(f"\nFinalizado: ~{total} eventos en {LOG_FILE}")


# ── CLI ────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Generador de logs para tesis de detección de anomalías"
    )
    sub = parser.add_subparsers(dest="command", metavar="COMANDO")

    p_run = sub.add_parser("run", help="Genera logs mezclados continuamente")
    p_run.add_argument("--duration", type=int, default=60,
                       help="Duración en segundos (default: 60)")
    p_run.add_argument("--anomaly-ratio", type=float, default=0.05,
                       help="Proporción de ráfagas anómalas 0.0-1.0 (default: 0.05)")

    sub.add_parser("normal",        help="Genera 200 logs normales")
    sub.add_parser("brute-force",   help="Simula ataque brute force al login")
    sub.add_parser("server-errors", help="Simula pico de errores 500")
    sub.add_parser("ddos",          help="Simula flood de requests")
    sub.add_parser("scan",          help="Simula escaneo de rutas sensibles")
    sub.add_parser("restart",       help="Simula caída y reinicio de contenedor")
    sub.add_parser("all-anomalies", help="Ejecuta todos los escenarios anómalos")

    args = parser.parse_args()

    if args.command == "run":
        run_continuous(args.duration, args.anomaly_ratio)

    elif args.command == "normal":
        for _ in range(200):
            gen_normal()
        print(f"200 logs normales → {LOG_FILE}")

    elif args.command == "brute-force":
        gen_brute_force(50)

    elif args.command == "server-errors":
        gen_server_errors(30)

    elif args.command == "ddos":
        gen_ddos(150)

    elif args.command == "scan":
        gen_path_scan()

    elif args.command == "restart":
        gen_container_restart()

    elif args.command == "all-anomalies":
        print("Ejecutando todos los escenarios anómalos...\n")
        gen_brute_force(50)
        gen_server_errors(30)
        gen_ddos(150)
        gen_path_scan()
        gen_container_restart()
        print(f"\nTodos los escenarios ejecutados → {LOG_FILE}")

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
