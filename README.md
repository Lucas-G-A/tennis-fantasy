# Tennis Fantasy — Estancia de Investigación (ITAM Sports Lab)

Modelo de predicción de partidos ATP/WTA (Elo/Glicko-2) que alimenta una aplicación de
fantasy tennis: los precios de los jugadores y las probabilidades de triunfo se generan
directamente a partir del modelo.

## Estructura del repo

```
tennis-fantasy/
├── pipeline/           # Scripts de datos: descarga, limpieza, y (más adelante)
│                        # el flujo automatizado que corre en GitHub Actions
│   ├── load_and_clean.py
│   └── requirements.txt
├── model/               # Motor Elo/Glicko-2, backtesting, simulador Monte Carlo
│                        # (vacío por ahora — Etapa 1, actividades 2 en adelante)
├── data/
│   ├── sackmann_mirror/ # Datos crudos (se descargan solos, no se versiona en git)
│   └── processed/       # Datos limpios en Parquet, lo que consume el resto del proyecto
├── frontend/            # App Expo (web ahora, iOS más adelante) — Etapa 3
└── .gitignore
```

## Qué hace cada archivo ahora mismo

- **`pipeline/load_and_clean.py`** — Etapa 1, Actividad 1. Descarga el historial de
  partidos ATP/WTA (1990–2026), lo limpia (fechas, superficies, retiros/walkovers,
  tipos numéricos), lo ordena cronológicamente y lo guarda en
  `data/processed/{atp,wta}_matches_clean.parquet` y `{atp,wta}_players.parquet`.
- **`data/processed/*.parquet`** — el resultado ya limpio. Cárgalo con
  `pd.read_parquet("data/processed/atp_matches_clean.parquet")`.

## Fuente de datos

Los datos son un mirror del repositorio de **Jeff Sackmann**
(`Aneeshers/tennis-sackmann-archive`), porque su repositorio original
(`JeffSackmann/tennis_atp` / `tennis_wta`) ya no está disponible públicamente en GitHub.
Mismo formato, misma licencia: **CC BY-NC-SA 4.0** (uso no comercial, atribución
requerida, redistribución bajo la misma licencia). Cítalo así en la documentación
técnica de la Etapa 1.

## Cómo correrlo en local (Cursor)

```bash
cd tennis-fantasy
python3 -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r pipeline/requirements.txt
python pipeline/load_and_clean.py
```

La primera corrida descarga ~140MB (tarda un par de minutos); las siguientes reusan lo
ya descargado en `data/sackmann_mirror/` (por eso está en `.gitignore` — no lo subas a
git, cada quien lo regenera corriendo el script).

## Roadmap (ver Plan de Trabajo)

- [x] Etapa 1.1 — Recolección y limpieza de datos históricos
- [ ] Etapa 1.2 — Análisis exploratorio de datos
- [ ] Etapa 1.3 — Motor de calificación Elo/Glicko-2
- [ ] Etapa 1.4 — Validación (backtesting)
- [ ] Etapa 1.5 — Documentación de metodología
- [ ] Etapa 2 — Simulador de torneos (Monte Carlo) y motor de precios
- [ ] Etapa 3 — Backend (Supabase), frontend (Expo), lanzamiento
