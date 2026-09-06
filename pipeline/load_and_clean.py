"""
load_and_clean.py
Etapa 1 · Actividad 1: Recolección y limpieza de datos históricos de partidos ATP/WTA

Fuente: mirror de la base de datos de Jeff Sackmann (CC BY-NC-SA 4.0), que incluye
partidos ATP y WTA hasta 2026. El repositorio original de Sackmann (JeffSackmann/tennis_atp
y tennis_wta) ya no está disponible públicamente en GitHub; usamos un mirror mantenido
(Aneeshers/tennis-sackmann-archive) que conserva el mismo formato y licencia, con atribución
al autor original.

Salida:
  data/processed/atp_matches_clean.parquet
  data/processed/wta_matches_clean.parquet
  data/processed/atp_players.parquet
  data/processed/wta_players.parquet
"""

import io
import tarfile
import urllib.request
from pathlib import Path

import pandas as pd

RAW_DIR = Path(__file__).parent.parent / "data" / "sackmann_mirror"
OUT_DIR = Path(__file__).parent.parent / "data" / "processed"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Mirror del repositorio de Jeff Sackmann (el original, JeffSackmann/tennis_atp y
# tennis_wta, ya no es público en GitHub). Mismo formato, misma licencia CC BY-NC-SA 4.0.
MIRROR_TARBALL_URL = (
    "https://codeload.github.com/Aneeshers/tennis-sackmann-archive/tar.gz/refs/heads/main"
)


def download_raw_data_if_missing():
    """Descarga y extrae el mirror (~140MB) la primera vez que se corre el pipeline."""
    if RAW_DIR.exists() and any(RAW_DIR.glob("atp/atp_matches_2020.csv")):
        return
    print(f"Descargando datos crudos desde {MIRROR_TARBALL_URL} (~140MB, puede tardar)...")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(MIRROR_TARBALL_URL) as resp:
        raw_bytes = resp.read()
    with tarfile.open(fileobj=io.BytesIO(raw_bytes), mode="r:gz") as tar:
        for member in tar.getmembers():
            # el tarball trae un folder raíz tipo tennis-sackmann-archive-main/, lo quitamos
            parts = member.name.split("/", 1)
            if len(parts) == 2 and parts[1]:
                member.name = parts[1]
                tar.extract(member, path=RAW_DIR)
    print("Descarga completa.")

# Desde qué año cargar. 1990 en adelante da ~35 años de historia: suficiente para
# estabilizar ratings Elo/Glicko sin arrastrar datos de una era de juego muy distinta.
START_YEAR = 1990
END_YEAR = 2026

MATCH_COLS_KEEP = [
    "tourney_id", "tourney_name", "surface", "draw_size", "tourney_level", "tourney_date",
    "match_num", "round", "best_of", "minutes", "score",
    "winner_id", "winner_name", "winner_hand", "winner_ht", "winner_ioc", "winner_age",
    "winner_rank", "winner_rank_points",
    "loser_id", "loser_name", "loser_hand", "loser_ht", "loser_ioc", "loser_age",
    "loser_rank", "loser_rank_points",
    "w_ace", "w_df", "w_svpt", "w_1stIn", "w_1stWon", "w_2ndWon", "w_SvGms", "w_bpSaved", "w_bpFaced",
    "l_ace", "l_df", "l_svpt", "l_1stIn", "l_1stWon", "l_2ndWon", "l_SvGms", "l_bpSaved", "l_bpFaced",
]


def load_matches(tour: str) -> pd.DataFrame:
    """tour: 'atp' o 'wta'"""
    folder = RAW_DIR / tour
    frames = []
    for year in range(START_YEAR, END_YEAR + 1):
        fpath = folder / f"{tour}_matches_{year}.csv"
        if not fpath.exists():
            continue
        df = pd.read_csv(fpath, low_memory=False)
        frames.append(df)
    all_matches = pd.concat(frames, ignore_index=True)

    # Solo columnas relevantes para el modelo (descarta seed/entry, no usados en el rating)
    cols = [c for c in MATCH_COLS_KEEP if c in all_matches.columns]
    all_matches = all_matches[cols].copy()

    # --- Limpieza ---
    # 1. Fecha del torneo: viene como entero YYYYMMDD
    all_matches["tourney_date"] = pd.to_datetime(
        all_matches["tourney_date"], format="%Y%m%d", errors="coerce"
    )

    # 2. Marcar walkovers / retiros / descalificaciones a partir del score
    #    (no deben pesar igual que un partido jugado completo en el modelo de rating)
    score_str = all_matches["score"].astype(str)
    all_matches["is_walkover"] = score_str.str.contains("W/O", na=False)
    all_matches["is_retirement"] = score_str.str.contains("RET", na=False)
    all_matches["is_default"] = score_str.str.contains("DEF", na=False)
    all_matches["completed_normally"] = ~(
        all_matches["is_walkover"] | all_matches["is_retirement"] | all_matches["is_default"]
    )

    # 3. Estandarizar superficie
    all_matches["surface"] = all_matches["surface"].str.strip().str.title()
    all_matches.loc[~all_matches["surface"].isin(["Hard", "Clay", "Grass", "Carpet"]), "surface"] = "Unknown"

    # 4. Tipos numéricos (algunos vienen como texto si hay celdas vacías mezcladas)
    numeric_cols = [c for c in all_matches.columns if c not in
                    ["tourney_id", "tourney_name", "surface", "tourney_level", "round", "score",
                     "winner_name", "winner_hand", "winner_ioc",
                     "loser_name", "loser_hand", "loser_ioc",
                     "is_walkover", "is_retirement", "is_default", "completed_normally",
                     "tourney_date"]]
    for c in numeric_cols:
        all_matches[c] = pd.to_numeric(all_matches[c], errors="coerce")

    # 5. Quitar duplicados exactos y filas sin fecha o sin ganador/perdedor identificado
    all_matches = all_matches.drop_duplicates()
    all_matches = all_matches.dropna(subset=["tourney_date", "winner_id", "loser_id"])

    # 6. Ordenar cronológicamente (crítico: Elo/Glicko se actualizan en orden temporal)
    all_matches = all_matches.sort_values(["tourney_date", "tourney_id", "match_num"]).reset_index(drop=True)

    return all_matches


def load_players(tour: str) -> pd.DataFrame:
    fpath = RAW_DIR / tour / f"{tour}_players.csv"
    df = pd.read_csv(fpath, low_memory=False)
    df.columns = [c.strip() for c in df.columns]
    return df


def summarize(df: pd.DataFrame, tour: str):
    n = len(df)
    date_min, date_max = df["tourney_date"].min(), df["tourney_date"].max()
    n_players = pd.concat([df["winner_id"], df["loser_id"]]).nunique()
    surface_counts = df["surface"].value_counts(normalize=True).round(3).to_dict()
    pct_retired = df["is_retirement"].mean() * 100
    pct_walkover = df["is_walkover"].mean() * 100
    missing_rank = df["winner_rank"].isna().mean() * 100

    print(f"\n=== {tour.upper()} ===")
    print(f"Partidos: {n:,}")
    print(f"Rango de fechas: {date_min.date()} -> {date_max.date()}")
    print(f"Jugadores distintos: {n_players:,}")
    print(f"Superficies: {surface_counts}")
    print(f"% retiros: {pct_retired:.2f}%  |  % walkover: {pct_walkover:.2f}%")
    print(f"% sin ranking del ganador registrado: {missing_rank:.2f}%")


if __name__ == "__main__":
    download_raw_data_if_missing()

    for tour in ["atp", "wta"]:
        print(f"Cargando partidos {tour.upper()} ({START_YEAR}-{END_YEAR})...")
        matches = load_matches(tour)
        players = load_players(tour)

        matches.to_parquet(OUT_DIR / f"{tour}_matches_clean.parquet", index=False)
        players.to_parquet(OUT_DIR / f"{tour}_players.parquet", index=False)

        summarize(matches, tour)

    print(f"\nListo. Archivos limpios guardados en: {OUT_DIR}")
