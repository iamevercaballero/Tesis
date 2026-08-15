#!/usr/bin/env python3
"""
Exporta logs desde Elasticsearch a CSV con features derivadas.
Soporta datasets grandes con la Scroll API (>10k registros).

Uso:
  python scripts/export_to_csv.py
  python scripts/export_to_csv.py --index "logs-*" --output datasets/processed/logs.csv
"""

import argparse
from pathlib import Path

import pandas as pd
from elasticsearch import Elasticsearch

ES_HOST = "http://localhost:9200"
DEFAULT_INDEX = "logs-*"
DEFAULT_OUTPUT = "datasets/processed/logs.csv"
SCROLL_SIZE = 2000
SCROLL_TTL = "2m"


def fetch_all(es: Elasticsearch, index: str) -> list:
    """Descarga todos los documentos usando Scroll API."""
    resp = es.search(
        index=index,
        body={"query": {"match_all": {}}, "sort": [{"@timestamp": "asc"}]},
        size=SCROLL_SIZE,
        scroll=SCROLL_TTL,
    )
    scroll_id = resp["_scroll_id"]
    docs = [hit["_source"] for hit in resp["hits"]["hits"]]
    total = resp["hits"]["total"]["value"]
    print(f"Total en Elasticsearch: {total:,} documentos")

    while True:
        resp = es.scroll(scroll_id=scroll_id, scroll=SCROLL_TTL)
        hits = resp["hits"]["hits"]
        if not hits:
            break
        docs.extend(hit["_source"] for hit in hits)
        print(f"  Descargados: {len(docs):,} / {total:,}", end="\r")

    es.clear_scroll(scroll_id=scroll_id)
    print(f"\nDescarga completa: {len(docs):,} registros")
    return docs


def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    # Preferir @timestamp (Filebeat/ES) sobre timestamp (campo del generador)
    for ts_col in ["@timestamp", "timestamp", "event_timestamp"]:
        if ts_col in df.columns:
            parsed = pd.to_datetime(df[ts_col], utc=True, errors="coerce")
            valid = parsed.notna().sum()
            if valid > 0:
                df["timestamp_dt"] = parsed
                break
    else:
        df["timestamp_dt"] = pd.NaT

    # Rellenar los NaT restantes con now() para no perder filas
    n_missing = df["timestamp_dt"].isna().sum()
    if n_missing:
        print(f"  Advertencia: {n_missing} timestamps inválidos, se completarán con valor interpolado")
        df["timestamp_dt"] = df["timestamp_dt"].fillna(method="ffill").fillna(pd.Timestamp.now(tz="UTC"))

    df = df.sort_values("timestamp_dt").reset_index(drop=True)
    df["hour"]        = df["timestamp_dt"].dt.hour
    df["day_of_week"] = df["timestamp_dt"].dt.dayofweek
    df["is_weekend"]  = (df["day_of_week"] >= 5).astype(int)
    return df


def add_error_flags(df: pd.DataFrame) -> pd.DataFrame:
    for col in ["status_code", "response_time_ms", "bytes_sent"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    if "status_code" in df.columns:
        df["is_error"]        = (df["status_code"] >= 400).astype(int)
        df["is_server_error"] = (df["status_code"] >= 500).astype(int)
        df["is_client_error"] = ((df["status_code"] >= 400) & (df["status_code"] < 500)).astype(int)

    if "message" in df.columns and "log_length" not in df.columns:
        df["log_length"] = df["message"].astype(str).str.len()
    elif "log_length" not in df.columns:
        df["log_length"] = 0

    return df


def add_window_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Features de ventana deslizante de 5 minutos por IP.
    Estas son las features más importantes para detectar ataques.
    """
    # Unificar columna IP: puede venir como 'ip' o 'ip_address' según la fuente
    if "ip" in df.columns and "ip_address" not in df.columns:
        df["ip_address"] = df["ip"]
    elif "ip_address" not in df.columns:
        df["ip_address"] = "unknown"

    # Rellenar IPs vacías — sin esto groupby las descarta con dropna=True por defecto
    df["ip_address"] = df["ip_address"].fillna("unknown").astype(str)

    df = df.set_index("timestamp_dt")
    window = "5min"
    parts = []

    # dropna=False para no perder filas cuya IP quedó como NaN antes del fillna
    for ip_val, grp in df.groupby("ip_address", dropna=False):
        grp = grp.sort_index()

        grp["event_count_window"] = (
            grp["status_code"].rolling(window).count().fillna(1)
        )
        grp["error_count_window"] = (
            grp["is_error"].rolling(window).sum().fillna(0)
        )

        if "endpoint" in grp.columns:
            login_fail = (
                (grp["endpoint"].fillna("") == "/login") & (grp["status_code"] == 401)
            ).astype(int)
            grp["failed_login_count"] = login_fail.rolling(window).sum().fillna(0)
        else:
            grp["failed_login_count"] = 0.0

        parts.append(grp)

    df = pd.concat(parts).sort_index().reset_index()
    # reset_index devuelve la columna con el nombre original del índice
    if "timestamp_dt" not in df.columns and "index" in df.columns:
        df = df.rename(columns={"index": "timestamp_dt"})
    return df


def build_dataframe(docs: list) -> pd.DataFrame:
    df = pd.DataFrame(docs)
    df = add_time_features(df)
    df = add_error_flags(df)
    df = add_window_features(df)
    return df


def print_summary(df: pd.DataFrame):
    print(f"\nDataset: {len(df):,} filas × {len(df.columns)} columnas")

    if "label" in df.columns:
        print("\nDistribución de labels:")
        counts = df["label"].value_counts()
        for label, n in counts.items():
            pct = n / len(df) * 100
            print(f"  {label:<25} {n:>6,}  ({pct:.1f}%)")

    if "scenario" in df.columns:
        print("\nDistribución de escenarios:")
        for sc, n in df["scenario"].value_counts().items():
            print(f"  {sc:<30} {n:>6,}")

    print(f"\nColumnas: {list(df.columns)}")


def main(index: str, output: str):
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)

    es = Elasticsearch(ES_HOST)
    if not es.ping():
        print(f"ERROR: No se puede conectar a Elasticsearch en {ES_HOST}")
        print("Asegurate de que el stack esté levantado con: make up")
        return

    docs = fetch_all(es, index)
    if not docs:
        print("No se encontraron documentos. Verificá que Filebeat esté enviando logs.")
        return

    df = build_dataframe(docs)
    df.to_csv(out, index=False)
    print(f"\nGuardado: {out}")
    print_summary(df)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Exporta logs de ES a CSV")
    parser.add_argument("--index",  default=DEFAULT_INDEX,  help="Índice de Elasticsearch")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Ruta del CSV de salida")
    args = parser.parse_args()
    main(args.index, args.output)
