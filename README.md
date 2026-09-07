# Tennis Fantasy — Estancia de Investigación (ITAM Sports Lab)

Modelo de predicción de partidos ATP/WTA (Elo/Glicko-2) que alimenta una aplicación de
fantasy tennis: los precios de los jugadores y las probabilidades de triunfo se generan
directamente a partir del modelo.

## Estructura del repo

```
tennis-fantasy/
├── pipeline/
│ ├── load_and_clean.py # Etapa 1.1 — descarga y limpieza de datos
│ └── requirements.txt
├── model/
│ ├── score_parser.py # Etapa 1.3 — parseo de marcador (margen de victoria)
│ ├── glicko2.py # Etapa 1.3 — álgebra Glicko-2 (Glickman)
│ ├── elo_engine.py # Etapa 1.3 — motor completo (rating general + superficie)
│ ├── eda.py # Etapa 1.2 — análisis exploratorio
│ ├── eda_outputs/ # gráficas + reporte_eda.md
│ ├── backtest.py # Etapa 1.4 — validación / backtesting
│ └── backtest_outputs/ # gráficas + reporte_backtesting.md
├── data/
│ ├── sackmann_mirror/ # datos crudos (se descargan solos, no se versiona en git)
│ └── processed/ # datos limpios en Parquet
├── frontend/ # app Expo (web ahora, iOS más adelante) — Etapa 3
└── .gitignore
```


## Estado actual: Etapa 1 casi completa (falta solo 1.5, documentación)

### 1.1 — Datos (`pipeline/load_and_clean.py`)
Descarga el historial de partidos ATP/WTA (1990–2026, ~216k partidos), limpia fechas,
estandariza superficies, marca retiros/walkovers, y ordena todo cronológicamente
(crítico para Elo/Glicko, que actualiza en orden). Guarda en `data/processed/`.

### 1.2 — Análisis exploratorio (`model/eda.py`)
Hallazgos clave:
- El ranking oficial ya es bastante predictivo: el favorito gana ~73-75% cuando la
  diferencia de ranking es grande (90+ puestos) — este es el piso que el modelo Elo/Glicko
  tiene que superar.
- La tasa de upset **no baja** en semifinal/final — lo que cambia ahí es que casi siempre
  son dos jugadores de elite con brecha de ranking chica, no que el resultado sea más
  caótico.
- Confirma que vale la pena mantener ratings **separados por superficie**.

### 1.3 — Motor Elo/Glicko-2 (`model/glicko2.py` + `model/score_parser.py` + `model/elo_engine.py`)
Cada jugador tiene un rating **general** y uno por **superficie** (Hard/Clay/Grass),
actualizados con el algoritmo Glicko-2 completo (validado contra el ejemplo numérico
oficial del paper de Glickman). Detalles de diseño:
- **Predicción** = mezcla ponderada por experiencia: `w·rating_superficie + (1-w)·rating_general`,
  con `w = n_partidos_superficie / (n_partidos_superficie + 150)` (calibrado por backtesting).
- **Peso de cada partido** según nivel de torneo (Slam > Masters/Premier > tour regular),
  retiro (peso 0.5), y margen de victoria (multiplicador ±15% máx.).
- **Copa Davis/Fed Cup se excluye** del motor: son grupos zonales con calidad muy dispareja
  y rivales sin ranking, que inflaban artificialmente algunos ratings (mismo criterio que
  usa FiveThirtyEight).
- **Regresión de temporada**: 20% hacia el promedio de carrera al cierre de cada año,
  excepto cuando eso contradice la trayectoria esperada por edad (no se empuja hacia
  arriba a un jugador en declive por edad, ni hacia abajo a uno en desarrollo).
- Corre en ~60s para ambos tours. Salida: `model/ratings_output/{tour}_final_ratings.csv`
  (snapshot final por jugador) y `{tour}_predictions.parquet` (predicción pre-partido de
  cada partido histórico — insumo del backtesting).

### 1.4 — Validación (`model/backtest.py`)
Periodo de prueba: 2016–2026 (fuera de muestra). Resultados (ATP):

| Modelo | Accuracy | Log-loss | Brier |
|---|---|---|---|
| Elo/Glicko (mezclado por superficie) | 64.3% | 0.6253 | 0.2183 |
| Baseline: solo ranking oficial | 64.0% | 0.6625 | 0.2326 |

- La mejora en accuracy pura es chica, pero en **log-loss/Brier es ~5-6% mejor** — el
  modelo da probabilidades más honestas, que es lo que de verdad importa para el
  simulador Monte Carlo y el motor de precios (Etapa 2).
- 64% está en línea con la literatura académica: un estudio de 2026 que compara Elo, ML
  clásico, y redes neuronales profundas sobre 133k partidos encontró que todos los
  enfoques caen dentro de 1.65 puntos porcentuales entre sí (~65-66%), por debajo del
  70-72% que logran las casas de apuestas.
- Desglosado por confianza: en partidos donde el modelo tiene ≥70% de confianza, acierta
  76.6% de las veces. ~35% de los partidos son esencialmente volados (<60% de confianza)
  para cualquier modelo — el agregado mezcla ambos mundos.
- Calibración sólida en ambos tours (curva cercana a la diagonal).

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

python pipeline/load_and_clean.py    # Etapa 1.1 — descarga + limpia (~140MB, un par de min. la 1a vez)
python model/eda.py                   # Etapa 1.2 — genera model/eda_outputs/
python model/elo_engine.py            # Etapa 1.3 — genera model/ratings_output/ (~60s)
python model/backtest.py              # Etapa 1.4 — genera model/backtest_outputs/
```

Cada script depende del anterior (usan los Parquet que va dejando el anterior), así que
hay que correrlos en ese orden la primera vez. `data/sackmann_mirror/` no se sube a git
(está en `.gitignore`) — cada quien lo regenera corriendo `load_and_clean.py`.

## Roadmap (ver Plan de Trabajo)

- [x] Etapa 1.1 — Recolección y limpieza de datos históricos
- [x] Etapa 1.2 — Análisis exploratorio de datos
- [x] Etapa 1.3 — Motor de calificación Elo/Glicko-2
- [x] Etapa 1.4 — Validación (backtesting)
- [ ] Etapa 1.5 — Documentación de metodología
- [ ] Etapa 2 — Simulador de torneos (Monte Carlo) y motor de precios
- [ ] Etapa 3 — Backend (Supabase), frontend (Expo), lanzamiento