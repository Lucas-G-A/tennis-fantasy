"""
backtest.py
Etapa 1 · Actividad 4: Validación (backtesting)

Todo lo que reporta esto es honesto out-of-sample para el motor Elo/Glicko: cada
predicción en {tour}_predictions.parquet se generó ANTES de aplicar el resultado de
ese partido (así está construido el motor, partido a partido, en orden cronológico).
No hay fuga de información hacia el pasado.

Comparaciones:
  1. Elo/Glicko vs. baseline de ranking oficial (regresión logística 1-variable,
     entrenada solo en el periodo de entrenamiento, evaluada en el periodo de prueba)
  2. Rating mezclado por superficie vs. rating general solo (¿la mezcla ayuda?)
  3. Curva de calibración: cuando el modelo dice X% de probabilidad, ¿gana X% de las veces?
  4. Accuracy según qué tan seguro estaba el modelo (¿el 64% agregado esconde partidos
     donde el modelo sí tiene una opinión clara vs. partidos genuinamente parejos?)

Ventana de prueba: 2016 en adelante (da ~26 años de calentamiento al modelo Elo/Glicko
antes de evaluarlo, y deja suficiente historia para entrenar el baseline).

Salida: model/backtest_outputs/*.png, model/backtest_outputs/reporte_backtesting.md
"""

from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss, brier_score_loss, accuracy_score

RATINGS_DIR = Path(__file__).parent / "ratings_output"
OUT_DIR = Path(__file__).parent / "backtest_outputs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

TEST_START_YEAR = 2016
EPS = 1e-6

plt.rcParams.update({
    "figure.facecolor": "white", "axes.facecolor": "white",
    "font.size": 11, "axes.spines.top": False, "axes.spines.right": False,
})


def add_favorite_columns(df: pd.DataFrame, prob_col: str = "prob_winner") -> pd.DataFrame:
    """
    A partir de prob_winner (probabilidad que el modelo le daba PRE-partido al que
    terminó ganando), reconstruye la vista 'favorito del modelo':
      favorite_prob  = probabilidad que el modelo daba a quien haya sido su favorito
      favorite_won   = 1 si el favorito del modelo ganó, 0 si hubo upset
    Esto es lo que hace falta para poder graficar una curva de calibración (si solo
    usamos prob_winner tal cual, por construcción "gana" el 100% de las veces).
    """
    df = df.copy()
    df["favorite_prob"] = np.maximum(df[prob_col], 1 - df[prob_col])
    df["favorite_won"] = (df[prob_col] >= 0.5).astype(int)
    return df


def build_symmetric_rank_dataset(df: pd.DataFrame) -> pd.DataFrame:
    """
    Reconstruye un dataset simétrico (sin fuga) para entrenar el baseline de ranking:
    player1/player2 asignados sin importar quién ganó, con rank_diff como única
    variable, y outcome=1 si player1 ganó.
    """
    df = df.dropna(subset=["winner_rank", "loser_rank"]).reset_index(drop=True)
    flip = np.arange(len(df)) % 2 == 0
    rank1 = np.where(flip, df["winner_rank"], df["loser_rank"])
    rank2 = np.where(flip, df["loser_rank"], df["winner_rank"])
    outcome = np.where(flip, 1, 0)
    # rank_diff positivo = player1 tiene mejor ranking (número más chico = mejor)
    rank_diff = rank2 - rank1
    return pd.DataFrame({"rank_diff": rank_diff, "outcome": outcome,
                          "year": df["tourney_date"].dt.year})


def evaluate(y_true, y_prob, label: str) -> dict:
    y_prob = np.clip(y_prob, EPS, 1 - EPS)
    return {
        "modelo": label,
        "n": len(y_true),
        "accuracy": accuracy_score(y_true, (y_prob >= 0.5).astype(int)),
        "log_loss": log_loss(y_true, y_prob, labels=[0, 1]),
        "brier": brier_score_loss(y_true, y_prob),
    }


def plot_calibration(df: pd.DataFrame, tour: str, prob_col: str, label: str, filename: str):
    bins = [0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1.0]
    d = df.copy()
    d["bucket"] = pd.cut(d[prob_col], bins=bins, include_lowest=True)
    tab = d.groupby("bucket", observed=True).agg(
        pred_media=(prob_col, "mean"), realizado=("favorite_won", "mean"), n=("favorite_won", "size"))

    fig, ax = plt.subplots(figsize=(6.5, 6.5))
    ax.plot([0.5, 1.0], [0.5, 1.0], "--", color="#999999", linewidth=1, label="Calibración perfecta")
    ax.plot(tab["pred_media"], tab["realizado"], marker="o", color="#378ADD", linewidth=2, label=label)
    for _, r in tab.iterrows():
        ax.annotate(f"n={int(r['n']):,}", (r["pred_media"], r["realizado"]),
                    textcoords="offset points", xytext=(6, -10), fontsize=8, color="#666666")
    ax.set_xlim(0.48, 1.0); ax.set_ylim(0.35, 1.0)
    ax.xaxis.set_major_formatter(mticker.PercentFormatter(1.0))
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0))
    ax.set_xlabel("Probabilidad promedio predicha por el modelo")
    ax.set_ylabel("% de veces que el favorito del modelo ganó en la realidad")
    ax.set_title(f"{tour.upper()}: calibración ({label})")
    ax.legend(frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(OUT_DIR / filename, dpi=140)
    plt.close(fig)
    return tab


def plot_metric_comparison(rows: list, tour: str):
    dfm = pd.DataFrame(rows)
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.2))
    for ax, metric, title, higher_better in zip(
        axes, ["accuracy", "log_loss", "brier"],
        ["Accuracy (más alto mejor)", "Log-loss (más bajo mejor)", "Brier score (más bajo mejor)"],
        [True, False, False]
    ):
        best_val = dfm[metric].max() if higher_better else dfm[metric].min()
        colors = ["#378ADD" if m == best_val else "#B8C4CE" for m in dfm[metric]]
        ax.barh(dfm["modelo"], dfm[metric], color=colors)
        lo, hi = dfm[metric].min(), dfm[metric].max()
        pad = max((hi - lo) * 0.8, hi * 0.02)
        ax.set_xlim(max(0, lo - pad), hi + pad)
        for i, v in enumerate(dfm[metric]):
            ax.annotate(f"{v:.4f}" if metric != "accuracy" else f"{v:.1%}",
                        (v, i), textcoords="offset points", xytext=(6, 0),
                        va="center", fontsize=9)
        ax.set_title(title, fontsize=10)
        ax.invert_yaxis()
    fig.suptitle(f"{tour.upper()}: comparación de modelos (periodo de prueba {TEST_START_YEAR}+)")
    fig.tight_layout(rect=[0, 0, 0.97, 0.94])
    fig.savefig(OUT_DIR / f"{tour}_model_comparison.png", dpi=140)
    plt.close(fig)


def plot_confidence_breakdown(df: pd.DataFrame, tour: str):
    """
    Accuracy real según qué tan seguro estaba el modelo. Responde la pregunta de
    fondo: ¿el 64% agregado es un modelo mediocre en todos lados, o es el promedio
    de partidos genuinamente parejos (donde nadie podría hacerlo mejor) y partidos
    donde el modelo sí tiene una opinión clara?
    """
    bins = [0.5, 0.55, 0.6, 0.65, 0.7, 0.8, 1.0]
    labels = ["50-55%", "55-60%", "60-65%", "65-70%", "70-80%", "80-100%"]
    d = df.copy()
    d["conf_bucket"] = pd.cut(d["favorite_prob"], bins=bins, labels=labels, include_lowest=True)
    tab = d.groupby("conf_bucket", observed=True).agg(n=("favorite_won", "size"), accuracy=("favorite_won", "mean"))

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar(labels, tab.reindex(labels)["accuracy"], color="#534AB7")
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0))
    ax.set_xlabel("Confianza del modelo en su favorito")
    ax.set_ylabel("% de veces que acertó")
    ax.set_title(f"{tour.upper()}: accuracy según confianza del modelo")
    for i, lbl in enumerate(labels):
        if lbl in tab.index:
            ax.annotate(f"n={tab.loc[lbl,'n']:,}", (i, tab.loc[lbl, "accuracy"]),
                        textcoords="offset points", xytext=(0, 6), fontsize=8, ha="center", color="#666666")
    fig.tight_layout()
    fig.savefig(OUT_DIR / f"{tour}_confidence_breakdown.png", dpi=140)
    plt.close(fig)
    return tab


def run_backtest(tour: str) -> list:
    report_lines = [f"\n## {tour.upper()}\n"]

    preds = pd.read_parquet(RATINGS_DIR / f"{tour}_predictions.parquet")
    preds["year"] = preds["tourney_date"].dt.year
    train = preds[preds["year"] < TEST_START_YEAR]
    test = preds[preds["year"] >= TEST_START_YEAR]

    # --- 1. Baseline: regresión logística de ranking (entrenada solo en `train`) ---
    train_rank = build_symmetric_rank_dataset(train)
    test_rank = build_symmetric_rank_dataset(test)
    baseline = LogisticRegression()
    baseline.fit(train_rank[["rank_diff"]], train_rank["outcome"])
    test_rank["baseline_prob"] = baseline.predict_proba(test_rank[["rank_diff"]])[:, 1]

    # --- 2. Elo/Glicko (mezclado por superficie) y su versión sin mezcla, en `test` ---
    test = add_favorite_columns(test, "prob_winner")
    test_general_only = add_favorite_columns(test, "prob_winner_general_only")

    results = [
        evaluate(np.ones(len(test)), test["prob_winner"], "Elo/Glicko (mezclado por superficie)"),
        evaluate(np.ones(len(test)), test["prob_winner_general_only"], "Elo/Glicko (solo general, sin mezcla)"),
        evaluate(test_rank["outcome"], test_rank["baseline_prob"], "Baseline: solo ranking oficial"),
    ]
    plot_metric_comparison(results, tour)

    cal_tab = plot_calibration(test, tour, "favorite_prob", "Elo/Glicko",
                                f"{tour}_calibration_elo.png")
    conf_tab = plot_confidence_breakdown(test, tour)

    # --- 3. Desglose por superficie ---
    surf_rows = []
    for surf in ["Hard", "Clay", "Grass"]:
        sub = test[test["surface"] == surf]
        if len(sub) < 50:
            continue
        r = evaluate(np.ones(len(sub)), sub["prob_winner"], surf)
        surf_rows.append(r)
    surf_df = pd.DataFrame(surf_rows)

    # --- reporte ---
    report_lines.append(f"Periodo de prueba: {TEST_START_YEAR}–2026 "
                         f"({len(test):,} partidos Elo/Glicko, {len(test_rank):,} con ranking para el baseline).\n")
    report_lines.append("\n| Modelo | Accuracy | Log-loss | Brier |\n|---|---|---|---|\n")
    for r in results:
        report_lines.append(f"| {r['modelo']} | {r['accuracy']:.1%} | {r['log_loss']:.4f} | {r['brier']:.4f} |\n")

    acc_elo = results[0]["accuracy"]
    acc_base = results[2]["accuracy"]
    acc_general = results[1]["accuracy"]
    report_lines.append(f"\n- Elo/Glicko acierta {acc_elo:.1%} de los partidos vs. {acc_base:.1%} del baseline "
                         f"de solo-ranking — una mejora de {(acc_elo-acc_base)*100:.1f} puntos porcentuales.\n")
    report_lines.append(f"- La mezcla por superficie aporta {(acc_elo-acc_general)*100:.2f} puntos porcentuales de "
                         f"accuracy frente a usar solo el rating general "
                         f"({'aporta algo real' if acc_elo > acc_general else 'no se nota diferencia clara'}).\n")

    report_lines.append(f"\n![comparación de modelos]({tour}_model_comparison.png)\n")
    report_lines.append(f"![calibración]({tour}_calibration_elo.png)\n")
    report_lines.append(f"![accuracy por confianza]({tour}_confidence_breakdown.png)\n")

    pct_coinflip = (test["favorite_prob"] < 0.6).mean()
    acc_high_conf = test[test["favorite_prob"] >= 0.7]["favorite_won"].mean()
    report_lines.append(f"\n- {pct_coinflip:.1%} de los partidos son 'volados' para el modelo (confianza <60%) "
                         f"— ahí ningún modelo debería esperar hacerlo mucho mejor que adivinar.\n")
    report_lines.append(f"- En los partidos donde el modelo sí tiene confianza (≥70%), acierta el "
                         f"{acc_high_conf:.1%} de las veces. El {acc_elo:.1%} agregado es el promedio de estos "
                         f"dos mundos, no un reflejo parejo de qué tan útil es el modelo.\n")

    report_lines.append("\n**Por superficie (Elo/Glicko, periodo de prueba):**\n\n")
    report_lines.append("| Superficie | n | Accuracy | Log-loss | Brier |\n|---|---|---|---|---|\n")
    for _, r in surf_df.iterrows():
        report_lines.append(f"| {r['modelo']} | {r['n']:,} | {r['accuracy']:.1%} | {r['log_loss']:.4f} | {r['brier']:.4f} |\n")

    return report_lines


if __name__ == "__main__":
    all_lines = ["# Reporte de validación (backtesting)\n",
                 f"Etapa 1 · Actividad 4 — periodo de prueba: {TEST_START_YEAR}–2026\n"]
    for tour in ["atp", "wta"]:
        print(f"Backtesting {tour.upper()}...")
        all_lines += run_backtest(tour)

    with open(OUT_DIR / "reporte_backtesting.md", "w", encoding="utf-8") as f:
        f.write("\n".join(all_lines))
    print(f"\nListo. Reporte en {OUT_DIR / 'reporte_backtesting.md'}")