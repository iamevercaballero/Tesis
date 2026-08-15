# Manual del Proyecto de Tesis
## Plataforma de Análisis de Logs con Data Mining para Detección de Anomalías

**Autor:** Ever Caballero  
**Carrera:** Ingeniería en Informática  
**Tipo de trabajo:** Tesis de grado

---

## Índice

1. [Qué hace este proyecto](#1-qué-hace-este-proyecto)
2. [Arquitectura general](#2-arquitectura-general)
3. [Estructura de carpetas y archivos](#3-estructura-de-carpetas-y-archivos)
4. [Técnicas utilizadas — explicación conceptual](#4-técnicas-utilizadas--explicación-conceptual)
5. [Flujo completo de datos](#5-flujo-completo-de-datos)
6. [Cómo correr el sistema desde cero](#6-cómo-correr-el-sistema-desde-cero)
7. [Cómo probar cada componente](#7-cómo-probar-cada-componente)
8. [Resultados obtenidos](#8-resultados-obtenidos)
9. [Glosario técnico](#9-glosario-técnico)

---

## 1. Qué hace este proyecto

Este sistema recolecta automáticamente logs generados por una infraestructura informática, los procesa para extraer características relevantes, y aplica algoritmos de **Data Mining no supervisado** para detectar comportamientos anómalos sin necesidad de etiquetas previas.

### Problema que resuelve

En sistemas informáticos reales, los logs son la principal fuente de evidencia ante incidentes. El problema es que se generan miles de registros por hora y analizarlos manualmente es inviable. Este proyecto demuestra que es posible automatizar esa detección usando Machine Learning.

### Qué detecta

| Escenario anómalo | Ejemplo real |
|---|---|
| Brute force de login | 50 intentos fallidos desde la misma IP en 5 minutos |
| Pico de errores 500 | El servidor falla repetidamente — posible caída de servicio |
| DDoS (flood de requests) | Cientos de peticiones por segundo desde múltiples IPs |
| Escaneo de rutas | Un bot prueba URLs sensibles: `/admin`, `/.env`, `/config.php` |
| Reinicio de contenedor | Un contenedor cae por OOM (falta de memoria) y se reinicia |

---

## 2. Arquitectura general

```
┌─────────────────────────────────────────────────────────┐
│                    INFRAESTRUCTURA LOCAL                 │
│                                                         │
│  ┌──────────────┐    ┌─────────────────────────────┐   │
│  │   log_       │    │   Nginx (servidor web)       │   │
│  │  generator   │    │   logs/nginx/access.log      │   │
│  │  .py         │    │   logs/nginx/error.log       │   │
│  └──────┬───────┘    └───────────┬─────────────────┘   │
│         │                        │                      │
│         ▼                        ▼                      │
│      logs/app/app.log       (archivos de log)           │
│              │                   │                      │
│              └─────────┬─────────┘                      │
│                        ▼                                │
│                ┌───────────────┐                        │
│                │   Filebeat    │  lee archivos de log   │
│                └───────┬───────┘  y los envía a ES     │
│                        │                                │
│                        ▼                                │
│                ┌───────────────┐                        │
│                │ Elasticsearch │  almacena y permite    │
│                │  (puerto 9200)│  consultas sobre logs  │
│                └───────┬───────┘                        │
│                        │                                │
│              ┌─────────┴──────────┐                    │
│              ▼                    ▼                     │
│        ┌──────────┐        ┌────────────────┐          │
│        │  Kibana  │        │ export_to_csv  │          │
│        │  :5601   │        │    .py         │          │
│        │dashboard │        └───────┬────────┘          │
│        └──────────┘                │                   │
│                                    ▼                   │
│                            logs.csv / features.csv      │
│                                    │                   │
│                                    ▼                   │
│                    ┌───────────────────────────┐       │
│                    │     Notebooks Jupyter      │       │
│                    │  01 EDA / 02 Features /    │       │
│                    │  03 Modelos ML             │       │
│                    └───────────────────────────┘       │
└─────────────────────────────────────────────────────────┘
```

### Componentes y su rol

| Componente | Tecnología | Función |
|---|---|---|
| Generador de logs | Python | Simula tráfico normal y ataques controlados |
| Nginx | Docker | Servidor web real que genera access logs |
| Filebeat | Docker / Elastic | Agente que lee archivos de log y los envía a ES |
| Elasticsearch | Docker / Elastic | Base de datos de búsqueda optimizada para logs |
| Kibana | Docker / Elastic | Interfaz visual para explorar logs en tiempo real |
| Logstash | Docker / Elastic | Procesador de logs (disponible, actualmente bypass) |
| export_to_csv.py | Python | Extrae datos de ES y construye el dataset con features |
| Notebooks Jupyter | Python | EDA, ingeniería de features y modelos ML |

---

## 3. Estructura de carpetas y archivos

```
tesis-log-anomaly/
│
├── docker-compose.yml              ← define y levanta toda la infraestructura
├── Makefile                        ← atajos para comandos frecuentes
├── requirements.txt                ← dependencias Python del proyecto
├── .gitignore                      ← archivos excluidos del control de versiones
│
├── app/
│   └── log_generator.py            ← generador de logs (corazón del laboratorio)
│
├── filebeat/
│   └── filebeat.yml                ← configuración del agente de recolección
│
├── logstash/
│   └── pipeline/
│       └── logstash.conf           ← pipeline de procesamiento (disponible)
│
├── nginx/
│   └── nginx.conf                  ← configuración del servidor web de prueba
│
├── logs/                           ← carpeta donde caen los logs en tiempo real
│   ├── app/
│   │   └── app.log                 ← logs generados por log_generator.py
│   └── nginx/
│       ├── access.log              ← peticiones HTTP al servidor Nginx
│       └── error.log               ← errores de Nginx
│
├── scripts/
│   └── export_to_csv.py            ← exporta logs de Elasticsearch a CSV
│
├── notebooks/
│   ├── 01_exploration.ipynb        ← análisis exploratorio del dataset (EDA)
│   ├── 02_feature_engineering.ipynb ← construcción y preparación de features
│   └── 03_models.ipynb             ← entrenamiento y evaluación de modelos ML
│
├── datasets/
│   ├── raw/                        ← datasets académicos (HDFS, BGL) — sin procesar
│   └── processed/
│       ├── logs.csv                ← dataset completo exportado de ES (22.844 filas)
│       ├── features.csv            ← dataset preparado para ML (18 features + label)
│       ├── model_comparison.csv    ← tabla de métricas comparativas
│       └── contamination_sensitivity.csv ← métricas de Isolation Forest variando contamination
│
├── models/
│   ├── isolation_forest.pkl        ← modelo Isolation Forest entrenado
│   ├── kmeans.pkl                  ← modelo K-Means entrenado
│   └── dbscan.pkl                  ← modelo DBSCAN entrenado
│
└── docs/
    └── figures/                    ← 17 gráficos generados por los notebooks
        ├── label_distribution.png  ← distribución normal vs anomalía
        ├── events_over_time.png    ← línea de tiempo de eventos
        ├── response_time.png       ← distribución de tiempos de respuesta
        ├── status_codes.png        ← frecuencia de códigos HTTP
        ├── top_ips.png             ← IPs más activas
        ├── correlation_heatmap.png ← correlación entre features
        ├── pca_2d.png              ← separabilidad en espacio reducido (PCA)
        ├── if_scores.png           ← distribución del anomaly score
        ├── roc_if.png              ← curva ROC de Isolation Forest
        ├── if_contamination_sensitivity.png ← sensibilidad de IF al parámetro contamination
        ├── kmeans_elbow.png        ← método del codo para elegir k
        ├── kmeans_clusters.png     ← clusters en espacio PCA
        ├── dbscan_kdistance.png    ← gráfico k-distance para elegir eps
        ├── confusion_matrices.png  ← matrices de confusión (IF y K-Means)
        ├── model_comparison_pca.png ← los 3 modelos en espacio PCA
        └── metrics_comparison.png  ← barras comparativas de métricas
```

---

## 4. Técnicas utilizadas — explicación conceptual

### 4.1 Recolección de logs — Filebeat

Filebeat es un agente ligero que **vigila archivos de log en disco** y los envía a Elasticsearch. Funciona como un "tail -f" inteligente: detecta cada línea nueva que se escribe en el archivo y la transmite sin perder eventos, incluso si el sistema se reinicia.

En este proyecto, Filebeat lee dos fuentes:
- `logs/app/app.log` — logs JSON generados por nuestro script
- `logs/nginx/access.log` — logs de acceso HTTP reales del servidor Nginx

**Por qué no usamos Logstash en producción:** Logstash es más potente para transformaciones complejas, pero presentó un problema de protocolo con Filebeat 8.x en Docker. Para el laboratorio, Filebeat envía directamente a Elasticsearch, que es la arquitectura más usada en entornos modernos.

---

### 4.2 Almacenamiento — Elasticsearch

Elasticsearch es una **base de datos de búsqueda distribuida** basada en Apache Lucene. A diferencia de una base de datos relacional, Elasticsearch indexa el contenido completo de cada documento, permitiendo búsquedas de texto completo en milisegundos sobre millones de registros.

Características relevantes para este proyecto:
- **Índice por fecha:** los logs se guardan en índices `logs-2026.05.06`, `logs-2026.05.07`, etc.
- **Scroll API:** permite descargar millones de registros en páginas sin saturar la memoria
- **Aggregations:** permite contar, agrupar y estadísticas sin exportar los datos

---

### 4.3 Parsing de logs — JSON estructurado

Los logs del generador se escriben directamente en formato **JSON** (un registro por línea), lo que elimina la necesidad de parsing con regex. Ejemplo de un log anómalo:

```json
{
  "timestamp": "2026-05-07T01:15:43Z",
  "service": "auth",
  "host": "server01",
  "scenario": "brute_force",
  "label": "anomaly",
  "ip": "203.0.113.99",
  "method": "POST",
  "endpoint": "/login",
  "status_code": 401,
  "response_time_ms": 23,
  "bytes_sent": 128,
  "severity": "warning"
}
```

Para los logs de Nginx (formato texto), se usa **Grok** en Logstash — un sistema de expresiones regulares nombradas que convierte una línea como:
```
192.168.1.10 - - [07/May/2026:01:15:43 +0000] "GET /login HTTP/1.1" 200 512
```
en campos estructurados: `ip_address`, `timestamp`, `request_method`, `endpoint`, `status_code`, `bytes_sent`.

---

### 4.4 Ingeniería de features

El dataset final tiene **18 features numéricas** que el modelo usa para detectar anomalías. Se dividen en tres grupos:

#### Features directas del log
| Feature | Descripción | Por qué detecta anomalías |
|---|---|---|
| `status_code` | Código HTTP (200, 401, 500...) | Los ataques generan muchos 401 y 500 |
| `response_time_ms` | Tiempo de respuesta en ms | Los errores 500 tienen tiempos muy altos |
| `bytes_sent` | Tamaño de la respuesta | Respuestas anómalas tienen tamaños distintos |
| `log_length` | Longitud del mensaje de log | Los mensajes de error son más largos |
| `severity_enc` | Severidad codificada (0=info, 3=critical) | Anomalías tienen severity alto |

#### Features de tiempo
| Feature | Descripción | Por qué detecta anomalías |
|---|---|---|
| `hour` | Hora del día (0-23) | Ataques pueden ocurrir de madrugada |
| `day_of_week` | Día de la semana (0=lunes) | Comportamiento distinto fin de semana |
| `is_weekend` | 1 si es sábado o domingo | Poco tráfico en fin de semana es normal |

#### Features de ventana temporal (las más importantes)
Estas features calculan el comportamiento de cada IP en una **ventana deslizante de 5 minutos**. Son la razón por la que el modelo detecta ataques: un solo 401 no es anómalo, pero 50 en 5 minutos desde la misma IP sí lo es.

| Feature | Descripción | Qué detecta |
|---|---|---|
| `event_count_window` | Cantidad de eventos de esa IP en 5 min | DDoS, flood |
| `error_count_window` | Cantidad de errores (4xx/5xx) en 5 min | Ataques, fallos |
| `failed_login_count` | Intentos fallidos de login en 5 min | Brute force |

#### Features binarias derivadas
| Feature | Descripción |
|---|---|
| `is_error` | 1 si status_code >= 400 |
| `is_server_error` | 1 si status_code >= 500 |
| `request_method_POST` | 1 si el método es POST |
| `source_type_nginx` | 1 si el log viene de Nginx |

---

### 4.5 Preprocesamiento

Antes de alimentar los modelos, las features pasan por dos transformaciones:

**Encoding de categóricas:** Variables como `severity` (info/warning/error/critical) se convierten a números (0/1/2/3). Variables como `request_method` (GET/POST/PUT) se convierten con one-hot encoding: una columna por cada valor posible.

**StandardScaler:** Cada feature numérica se normaliza para que tenga media=0 y desviación estándar=1. Esto es necesario porque `response_time_ms` puede valer 10.000 mientras que `is_weekend` vale 0 o 1. Sin escalar, los modelos de distancia (K-Means, DBSCAN) se sesgan hacia las variables con mayor magnitud.

---

### 4.6 Reducción de dimensionalidad — PCA

**PCA (Análisis de Componentes Principales)** transforma las 18 features en 2 dimensiones visualizables, conservando la mayor varianza posible. Se usa únicamente para **visualizar** si los datos son separables: si en el gráfico PCA 2D los puntos azules (normal) y rojos (anomalía) forman grupos distintos, los algoritmos tienen potencial para separarlos.

No reemplaza a los modelos — solo sirve para entender los datos.

---

### 4.7 Isolation Forest (algoritmo principal)

**Concepto:** un árbol de decisión aleatorio hace cortes en el espacio de features. Los puntos que se aíslan con muy pocos cortes son raros — y eso los hace anómalos.

**Analogía:** si tenés una sala llena de personas y querés aislar a alguien haciéndole preguntas de sí/no (¿tiene más de 30 años? ¿mide más de 1.70m?), aislar a una persona común requiere muchas preguntas. Aislar a la persona que es un enano de 2.50m solo requiere 2 preguntas. Esa persona es un outlier.

**Parámetro clave — `contamination`:** le dice al modelo qué proporción del dataset espera que sea anómala. Usar el porcentaje real de anomalías (calculado desde el label) sería fuga de información hacia un modelo que se supone no supervisado — en producción ese dato no existe. Por eso se usa `contamination=0.05`, un valor conservador estimado a priori (rango recomendado en la literatura: 0.05–0.10).

Un análisis de sensibilidad —variando `contamination` de 0.03 a 0.30 y recalculando métricas— muestra que el F1 del modelo mejora de forma casi monótona cuanto más se acerca ese parámetro al 26.9% real de anomalías del dataset. Es decir, el resultado "bueno" (F1≈0.60) solo aparece si se hace trampa con la etiqueta; el resultado honesto es más modesto pero es el que se sostiene ante un jurado. Ver `datasets/processed/contamination_sensitivity.csv` y `docs/figures/if_contamination_sensitivity.png`.

**Salida:** un `anomaly_score` continuo por cada registro. Cuanto más negativo, más anómalo. El umbral se fija según la contamination.

**Por qué es el algoritmo principal:** es eficiente en dimensiones altas, no asume distribución de los datos, y produce un score continuo útil para priorizar alertas (no solo binario).

---

### 4.8 K-Means

**Concepto:** divide el dataset en k grupos (clusters), donde cada punto pertenece al cluster cuyo centroide (punto medio) le queda más cerca. Es un algoritmo de **partición**.

**Cómo se usa para detectar anomalías:** se asume que las anomalías formarán el cluster más pequeño o más alejado del centroide. En este proyecto, con k=2, el algoritmo aprendió automáticamente que hay dos "modos" del sistema: tráfico normal y tráfico anómalo.

**Elbow method:** para elegir el valor de k óptimo, se grafica la inercia (suma de distancias al centroide) para distintos valores de k. El punto donde la curva deja de bajar bruscamente (el "codo") indica el k óptimo.

**Resultado:** F1=0.860, el mejor de los tres algoritmos en este dataset. Funciona bien porque las anomalías tienen valores muy distintos (status 401/500, response_time alto) que forman un cluster compacto y separado.

---

### 4.9 DBSCAN

**Concepto:** agrupa puntos que están en regiones densas del espacio de features. Los puntos que no pertenecen a ninguna región densa se marcan como **ruido** — y ese ruido son las anomalías.

**Parámetros clave:**
- `eps`: radio de vecindad — qué tan cerca deben estar dos puntos para considerarse vecinos
- `min_samples`: mínimo de puntos para que una región sea considerada densa

**Por qué falla en este dataset (F1=0.051):** los ataques DDoS (579 eventos de 55 IPs distintas) y los brute force (380 eventos de una IP) forman clusters densos por sí mismos — no son puntos de ruido dispersos. DBSCAN los clasifica como clusters normales porque tienen densidad alta. Este es un **hallazgo negativo con valor académico**: DBSCAN es apto para anomalías dispersas, no para ataques volumétricos.

---

### 4.10 Métricas de evaluación

| Métrica | Definición | Cuándo importa |
|---|---|---|
| **Precision** | De los que marcó como anómalos, ¿cuántos realmente lo son? | Cuando las falsas alarmas son costosas |
| **Recall** | De todos los anómalos reales, ¿cuántos detectó? | Cuando no detectar un ataque es grave |
| **F1-Score** | Media armónica de precision y recall | Balance general del modelo |
| **ROC-AUC** | Capacidad del score de ordenar correctamente normal vs anómalo | Evaluación del score continuo, independiente del umbral |

**Confusion Matrix:**
```
                 Predicho normal   Predicho anomalía
Real normal            TN                FP          ← Falsas alarmas
Real anomalía          FN                TP          ← Detecciones correctas
```

---

## 5. Flujo completo de datos

```
[1] log_generator.py
    Genera logs JSON → logs/app/app.log
    6 escenarios: normal, brute_force, server_error,
                  ddos, path_scan, container_restart

         ↓ Filebeat lee el archivo en tiempo real

[2] Elasticsearch
    Almacena cada línea como documento JSON
    Índice: logs-2026.05.07
    Total actual: 22.844 documentos

         ↓ Kibana (visualización) + export_to_csv.py (ML)

[3] export_to_csv.py
    Descarga todos los documentos con Scroll API
    Agrega features derivadas:
    - Parsea timestamps → hour, day_of_week, is_weekend
    - Calcula is_error, is_server_error
    - Calcula ventanas de 5 min por IP: event_count_window,
      error_count_window, failed_login_count
    Guarda: datasets/processed/logs.csv (22.844 filas × 46 columnas)

         ↓ notebook 02_feature_engineering.ipynb

[4] Feature Engineering
    Selecciona 18 features relevantes
    Encoding de categóricas (severity, request_method, source_type)
    StandardScaler → media=0, std=1
    Guarda: datasets/processed/features.csv (22.844 filas × 19 cols)

         ↓ notebook 03_models.ipynb

[5] Modelos de Data Mining
    Isolation Forest  → contamination=0.05 (honesto, sin fuga) → F1=0.258, ROC-AUC=0.887
    K-Means (k=2)     → F1=0.860 (mejor F1 del trabajo)
    DBSCAN (eps=0.3)  → F1=0.051 (no apto para este tipo de dato)
    Guarda: models/*.pkl + datasets/processed/model_comparison.csv + contamination_sensitivity.csv

         ↓ docs/figures/

[6] Visualizaciones (17 gráficos)
    Distribución de labels, timeline, scores, ROC, PCA,
    confusion matrices, comparación de métricas
```

---

## 6. Cómo correr el sistema desde cero

### Paso 1 — Requisitos
- Docker Desktop instalado y corriendo
- Python 3.9+

### Paso 2 — Instalar dependencias Python (una sola vez)
```bash
cd ~/Desktop/tesis-log-anomaly
pip3 install -r requirements.txt
```

### Paso 3 — Levantar la infraestructura
```bash
docker compose up -d
```
Esperar 2 minutos. Verificar:
```bash
docker compose ps
# elasticsearch debe decir: (healthy)
```

### Paso 4 — Generar logs
```bash
# Modo recomendado: tráfico mixto durante 5 minutos
python3 app/log_generator.py run --duration 300 --anomaly-ratio 0.05
```

### Paso 5 — Exportar a CSV
```bash
python3 scripts/export_to_csv.py
```

### Paso 6 — Abrir Jupyter y ejecutar notebooks
```bash
/Users/ever/Library/Python/3.9/bin/jupyter notebook --notebook-dir=.
```
Abrir en el browser y ejecutar en orden:
1. `notebooks/02_feature_engineering.ipynb` (Kernel → Restart & Run All)
2. `notebooks/03_models.ipynb` (Kernel → Restart & Run All)

### Paso 7 — Ver resultados
```bash
cat datasets/processed/model_comparison.csv
open docs/figures/metrics_comparison.png
open docs/figures/model_comparison_pca.png
```

### Paso 8 — Apagar
```bash
docker compose down          # apaga, conserva datos
docker compose down -v       # apaga y borra todos los datos (reset)
```

---

## 7. Cómo probar cada componente

### Verificar Elasticsearch
```bash
curl http://localhost:9200/_cluster/health
# Debe responder: "status":"yellow" (normal en nodo único)

curl http://localhost:9200/_cat/indices?v
# Muestra los índices logs-* con cantidad de documentos
```

### Verificar que Filebeat envía datos
```bash
docker logs --tail 20 filebeat
# No debe mostrar errores de conexión recientes

curl http://localhost:9200/logs-*/_count
# Debe incrementarse cada vez que se generan logs
```

### Verificar Kibana
Abrir `http://localhost:5601` en el browser.
- Ir a Discover → seleccionar data view `logs-*`
- Ajustar el filtro de tiempo a "Last 24 hours"
- Deben verse los registros con todos sus campos

### Verificar el generador de logs
```bash
python3 app/log_generator.py normal
# Debe imprimir: "200 logs normales → .../logs/app/app.log"

tail -1 logs/app/app.log | python3 -m json.tool
# Debe mostrar un JSON válido con todos los campos
```

### Verificar los modelos
```bash
python3 << 'EOF'
import joblib, pandas as pd
feat = pd.read_csv('datasets/processed/features.csv')
X = feat.drop(columns=['label'])
iso = joblib.load('models/isolation_forest.pkl')
scores = iso.decision_function(X)
print(f"Score mínimo (más anómalo): {scores.min():.4f}")
print(f"Score máximo (más normal):  {scores.max():.4f}")
print(f"Anomalías detectadas: {(iso.predict(X)==-1).sum()}")
EOF
```

---

## 8. Resultados obtenidos

### Dataset

| Característica | Valor |
|---|---|
| Total de registros | 22.844 logs |
| Registros normales | 16.699 (73.1%) |
| Registros anómalos | 6.145 (26.9%) |
| Features para ML | 18 features numéricas |
| Período de captura | Laboratorio controlado |

### Distribución por escenario

| Escenario | Registros | Label |
|---|---|---|
| Tráfico normal | 16.523 | normal |
| DDoS flood | 2.123 | anomaly |
| Escaneo de rutas | 1.615 | anomaly |
| Brute force login | 1.217 | anomaly |
| Errores 500 | 834 | anomaly |
| Reinicio de contenedor | 528 | anomaly |

### Métricas de los modelos

| Algoritmo | Precision | Recall | F1-Score | ROC-AUC |
|---|---|---|---|---|
| Isolation Forest (contamination=0.05) | 0.823 | 0.153 | 0.258 | **0.887** |
| K-Means (k=2) | **0.903** | **0.822** | **0.860** | — |
| DBSCAN (eps=0.3) | 0.611 | 0.027 | 0.051 | — |

*Nota de reproducibilidad: hasta el 6 de mayo se reportaba Isolation Forest con `contamination=0.27` (F1=0.574), calculado a partir del % real de anomalías del dataset — una fuga de información hacia un modelo que se supone no supervisado. Los valores de esta tabla usan `contamination=0.05`, estimado a priori sin consultar el label. K-Means y DBSCAN no se ven afectados por este cambio.*

### Interpretación de resultados

**Isolation Forest** sigue siendo el algoritmo conceptualmente más riguroso porque:
- Su **ROC-AUC de 0.887** indica que el score continuo separa correctamente casi el 89% de los pares. Esta métrica no depende del umbral ni de `contamination`, y es la más relevante para evaluar detección de anomalías no supervisada.
- Opera completamente sin etiquetas durante el entrenamiento — a diferencia del `contamination=0.27` usado en versiones anteriores, que sí consultaba el label real.
- El análisis de sensibilidad muestra el trade-off del umbral explícitamente: con `contamination=0.05` prioriza precisión (0.823) sobre cobertura (recall 0.153); subir `contamination` sube el recall pero también las falsas alarmas.

**K-Means** obtuvo el mejor F1 (0.860) y, con `contamination` corregido, es el modelo con mejor desempeño global del trabajo. La explicación es directa: con k=2 el algoritmo aprende dos "modos" del sistema, y funciona bien porque las anomalías generadas tienen características numéricas muy distintas (códigos 401/500, tiempos de respuesta altos) que forman un cluster compacto y separado — a diferencia de Isolation Forest, no depende de asumir una tasa de contaminación. Su limitación es que necesita conocer k de antemano y es sensible a la inicialización.

**DBSCAN** obtuvo F1=0.051, lo cual es un **hallazgo negativo con valor académico**: los ataques volumétricos (DDoS, brute force) forman grupos densos en el espacio de features y no son "puntos de ruido", que es exactamente lo que DBSCAN busca. Esto demuestra que la elección del algoritmo debe considerar la naturaleza de la anomalía que se quiere detectar.

---

## 9. Glosario técnico

| Término | Definición simple |
|---|---|
| **Log** | Registro cronológico de eventos generado por un sistema informático |
| **Anomalía** | Evento que se desvía significativamente del comportamiento normal esperado |
| **Data Mining** | Proceso de descubrir patrones en grandes volúmenes de datos |
| **Aprendizaje no supervisado** | El modelo aprende sin etiquetas previas, solo con la estructura de los datos |
| **Feature** | Variable o característica numérica que describe un registro |
| **Feature engineering** | Proceso de construir y transformar variables para mejorar los modelos |
| **Elasticsearch** | Base de datos distribuida optimizada para búsqueda de texto en tiempo real |
| **Filebeat** | Agente ligero que recolecta logs de archivos y los envía a Elasticsearch |
| **Kibana** | Interfaz visual para explorar datos almacenados en Elasticsearch |
| **Isolation Forest** | Algoritmo que detecta anomalías aislando puntos con árboles de decisión aleatorios |
| **K-Means** | Algoritmo que agrupa datos en k clusters según distancia al centroide |
| **DBSCAN** | Algoritmo que agrupa datos por densidad; los puntos aislados son anomalías |
| **PCA** | Técnica que reduce dimensiones conservando la mayor varianza posible |
| **StandardScaler** | Transforma variables para que tengan media=0 y desviación estándar=1 |
| **Contamination** | Parámetro que indica al modelo qué fracción del dataset se espera que sea anómala |
| **ROC-AUC** | Métrica que mide la capacidad discriminativa de un score continuo (1=perfecto, 0.5=aleatorio) |
| **F1-Score** | Media armónica entre precision y recall; balance entre detectar bien y no generar falsas alarmas |
| **Ventana deslizante** | Agrupación de eventos dentro de un intervalo de tiempo que se mueve con el tiempo |
| **One-hot encoding** | Convierte una variable categórica en múltiples columnas binarias (0 o 1) |
| **Docker** | Plataforma que empaqueta aplicaciones en contenedores aislados y reproducibles |
| **Docker Compose** | Herramienta para definir y levantar múltiples contenedores Docker con un solo comando |
