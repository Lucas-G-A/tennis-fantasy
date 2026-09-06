"""
eda.py
Etapa 1 · Actividad 2: Análisis exploratorio de datos
(desempeño por superficie, rankings, frecuencia de upsets)

Entrada:  data/processed/{atp,wta}_matches_clean.parquet
Salida:   model/eda_outputs/*.png
          model/eda_outputs/reporte_eda.md
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd

DATA_DIR = Path(__file__).parent.parent / "data" / "processed"
OUT_DIR = Path(__file__).parent / "eda_outputs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

ROUND_ORDER = ["R128", "R64", "R32", "R16", "QF", "SF", "F"]
SURFACE_ORDER = ["Hard", "Clay", "Grass", "Carpet"]

plt.rcParams.update({
    "figure.facecolor": "white", "axes.facecolor": "white",
    "font.size": 11, "axes.spines.top": False, "axes.spines.right": False,
})
COLORS = {"Hard": "#378ADD", "Clay": "#D85A30", "Grass": "#0F6E56", "Carpet": "#5F5E5A"}


def load(tour: str) -> pd.DataFrame:
    df = pd.read_parquet(DATA_DIR / f"{tour}_matches_clean.parquet")
    df["year"] = df["tourney_date"].dt.year
    df = df.dropna(subset=["winner_rank", "loser_rank"])
    df["rank_gap"] = (df["loser_rank"] - df["winner_rank"]).abs()
    # upset = ganó el jugador con peor ranking (número más alto)
    df["is_upset"] = df["winner_rank"] > df["loser_rank"]
    return df


# ---------------------------------------------------------------- gráficas


def plot_matches_by_surface_over_time(df: pd.DataFrame, tour: str):
    tab = df.groupby(["year", "surface"]).size().unstack(fill_value=0)
    tab = tab[[c for c in SURFACE_ORDER if c in tab.columns]]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    tab.plot(kind="area", stacked=True, ax=ax, color=[COLORS[c] for c in tab.columns], linewidth=0)
    ax.set_title(f"{tour.upper()}: partidos por superficie y año")
    ax.set_xlabel("Año"); ax.set_ylabel("Partidos")
    ax.legend(title=None, frameon=False)
    fig.tight_layout()
    fig.savefig(OUT_DIR / f"{tour}_matches_by_surface_year.png", dpi=140)
    plt.close(fig)


def plot_win_rate_vs_rank_gap(df: pd.DataFrame, tour: str):
    bins = [0, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 1000]
    labels = ["1", "2", "3", "4-5", "6-8", "9-13", "14-21", "22-34", "35-55", "56-89", "90+"]
    df = df.copy()
    df["gap_bucket"] = pd.cut(df["rank_gap"], bins=bins, labels=labels)
    fav_win_rate = 1 - df.groupby("gap_bucket", observed=True)["is_upset"].mean()
    counts = df.groupby("gap_bucket", observed=True).size()

    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.plot(labels, fav_win_rate.reindex(labels), marker="o", color="#378ADD", linewidth=2)
    ax.axhline(0.5, color="#999999", linestyle="--", linewidth=1)
    ax.set_ylim(0.45, 1.0)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0))
    ax.set_xlabel("Diferencia de ranking entre los dos jugadores")
    ax.set_ylabel("% de veces que gana el favorito")
    ax.set_title(f"{tour.upper()}: qué tan predictivo es el ranking")
    for i, lbl in enumerate(labels):
        if lbl in counts.index:
            ax.annotate(f"n={counts[lbl]:,}", (i, fav_win_rate.reindex(labels).iloc[i]),
                        textcoords="offset points", xytext=(0, 8), fontsize=8, ha="center", color="#666666")
    fig.tight_layout()
    fig.savefig(OUT_DIR / f"{tour}_winrate_vs_rankgap.png", dpi=140)
    plt.close(fig)
    return fav_win_rate, counts


def plot_upset_rate_by_round(df: pd.DataFrame, tour: str):
    tab = df[df["round"].isin(ROUND_ORDER)].groupby("round", observed=True)["is_upset"].mean()
    tab = tab.reindex(ROUND_ORDER)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar(ROUND_ORDER, tab.values, color="#D85A30")
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0))
    ax.set_ylabel("% de partidos con upset")
    ax.set_title(f"{tour.upper()}: frecuencia de upsets por ronda")
    fig.tight_layout()
    fig.savefig(OUT_DIR / f"{tour}_upset_by_round.png", dpi=140)
    plt.close(fig)
    return tab


def plot_upset_rate_by_surface(df: pd.DataFrame, tour: str):
    tab = df[df["surface"].isin(SURFACE_ORDER)].groupby("surface", observed=True)["is_upset"].mean()
    tab = tab.reindex([s for s in SURFACE_ORDER if s in tab.index])
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.bar(tab.index, tab.values, color=[COLORS[s] for s in tab.index])
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0))
    ax.set_ylabel("% de partidos con upset")
    ax.set_title(f"{tour.upper()}: frecuencia de upsets por superficie")
    fig.tight_layout()
    fig.savefig(OUT_DIR / f"{tour}_upset_by_surface.png", dpi=140)
    plt.close(fig)
    return tab


def plot_upset_rate_over_time(df: pd.DataFrame, tour: str):
    tab = df.groupby("year")["is_upset"].mean()
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.plot(tab.index, tab.values, color="#534AB7", linewidth=2)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0))
    ax.set_xlabel("Año"); ax.set_ylabel("% de partidos con upset")
    ax.set_title(f"{tour.upper()}: frecuencia de upsets a lo largo del tiempo")
    fig.tight_layout()
    fig.savefig(OUT_DIR / f"{tour}_upset_over_time.png", dpi=140)
    plt.close(fig)
    return tab


# ---------------------------------------------------------------- reporte


def build_report():
    lines = ["# Reporte de análisis exploratorio\n",
             "Etapa 1 · Actividad 2 — datos ATP/WTA, 1990–2026\n"]

    for tour in ["atp", "wta"]:
        df = load(tour)
        plot_matches_by_surface_over_time(df, tour)
        fav_win_rate, counts = plot_win_rate_vs_rank_gap(df, tour)
        upset_by_round = plot_upset_rate_by_round(df, tour)
        upset_by_surface = plot_upset_rate_by_surface(df, tour)
        upset_over_time = plot_upset_rate_over_time(df, tour)

        overall_upset_rate = df["is_upset"].mean()

        lines.append(f"\n## {tour.upper()}\n")
        lines.append(f"- Partidos analizados (con ranking registrado en ambos lados): {len(df):,}\n")
        lines.append(f"- Tasa de upset general: {overall_upset_rate:.1%}\n")
        lines.append(f"- El favorito (mejor ranking) gana el {fav_win_rate.iloc[0]:.1%} de las veces "
                      f"cuando la diferencia de ranking es de solo 1 puesto, y el "
                      f"{fav_win_rate.iloc[-1]:.1%} cuando la diferencia es de 90+ puestos.\n")
        lines.append(f"- Ronda con más upsets: {upset_by_round.idxmax()} "
                      f"({upset_by_round.max():.1%}). Ronda con menos: {upset_by_round.idxmin()} "
                      f"({upset_by_round.min():.1%}).\n")
        lines.append(f"- Superficie con más upsets: {upset_by_surface.idxmax()} "
                      f"({upset_by_surface.max():.1%}). Con menos: {upset_by_surface.idxmin()} "
                      f"({upset_by_surface.min():.1%}).\n")
        lines.append(f"\n![matches by surface](eda_outputs/{tour}_matches_by_surface_year.png)\n")
        lines.append(f"![winrate vs rankgap](eda_outputs/{tour}_winrate_vs_rankgap.png)\n")
        lines.append(f"![upset by round](eda_outputs/{tour}_upset_by_round.png)\n")
        lines.append(f"![upset by surface](eda_outputs/{tour}_upset_by_surface.png)\n")
        lines.append(f"![upset over time](eda_outputs/{tour}_upset_over_time.png)\n")

    lines.append("\n## Implicaciones para el modelo Elo/Glicko-2\n")
    lines.append("- El ranking oficial ya es bastante predictivo, sobre todo con diferencias grandes: "
                  "esto da un piso (benchmark) claro que el modelo Elo/Glicko debe superar para justificar su uso.\n")
    lines.append("- La tasa de upset varía por superficie: confirma que vale la pena mantener ratings "
                  "**separados por superficie** en vez de un solo Elo general.\n")
    lines.append("- Contrario a la intuición inicial, la tasa de upset **no baja** en rondas tardías (semifinal "
                  "y final incluso muestran una tasa ligeramente más alta que octavos/cuartos). Esto no significa "
                  "que las finales sean más caóticas: lo que cambia es la composición de los partidos que llegan "
                  "ahí — en rondas tempranas hay más brechas de ranking grandes (top-10 vs. top-150), mientras que "
                  "en semifinal/final casi siempre son dos jugadores de elite con una brecha de ranking chica, "
                  "donde el ranking pesa mucho menos como señal. Esto refuerza que el modelo debe pesar la "
                  "**brecha de ranking real**, no la ronda en sí, y sugiere que el simulador de cuadros (Etapa 2) "
                  "va a necesitar más granularidad que 'favorito vs. no favorito' entre jugadores top.\n")

    with open(Path(__file__).parent / "eda_outputs" / "reporte_eda.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print("Reporte guardado en model/eda_outputs/reporte_eda.md")


if __name__ == "__main__":
    build_report()