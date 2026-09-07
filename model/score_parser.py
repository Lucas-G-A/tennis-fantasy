"""
score_parser.py
Convierte el string de marcador ("6-3 3-6 7-6(4)") en juegos ganados por cada lado,
usado para el multiplicador de margen de victoria en el motor Elo/Glicko-2.
"""

import re

TIEBREAK_RE = re.compile(r"\((\d+)\)")


def parse_score(score: str):
    """
    Devuelve (games_winner, games_loser, valid) a partir del string de marcador.
    valid=False si el marcador no se pudo interpretar como sets normales
    (retiro, walkover, marcador corrupto, etc.) — en ese caso no debe usarse
    para margen de victoria.
    """
    if not isinstance(score, str) or not score.strip():
        return None, None, False

    s = score.strip()
    if any(tag in s for tag in ["RET", "W/O", "DEF", "ABD", "Walkover"]):
        return None, None, False

    sets = s.split()
    games_w, games_l = 0, 0
    n_valid_sets = 0

    for set_str in sets:
        # quita el detalle del tiebreak "(4)" -> ya no lo necesitamos para contar juegos
        clean = TIEBREAK_RE.sub("", set_str)
        if "-" not in clean:
            continue
        parts = clean.split("-")
        if len(parts) != 2:
            continue
        try:
            g_w, g_l = int(parts[0]), int(parts[1])
        except ValueError:
            continue
        games_w += g_w
        games_l += g_l
        n_valid_sets += 1

    if n_valid_sets == 0:
        return None, None, False

    return games_w, games_l, True


def margin_multiplier(games_winner: int, games_loser: int, weight_range: float = 0.3) -> float:
    """
    Multiplicador chico según qué tan lopsided fue el resultado.
    margen=0.5 (parejo) -> multiplicador=1.0
    margen=1.0 (el perdedor no ganó ni un juego) -> multiplicador=1+weight_range
    """
    total = games_winner + games_loser
    if total == 0:
        return 1.0
    margin = games_winner / total  # ~0.5 (parejo) a ~1.0 (dominante)
    return 1.0 + weight_range * (margin - 0.5)