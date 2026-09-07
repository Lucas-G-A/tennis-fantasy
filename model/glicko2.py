"""
glicko2.py
Implementación del algoritmo Glicko-2 (Mark Glickman), incluyendo el paso iterativo
para la volatilidad. Referencia: http://www.glicko.net/glicko/glicko2.pdf

Convención de escala: rating=1500, RD=350, volatilidad=0.06 (defaults estándar).
Todo el cálculo interno pasa a la escala Glicko-2 (mu, phi) y se regresa a la escala
original al final — así lo especifica el paper.
"""

import math
from dataclasses import dataclass

SCALE = 173.7178
DEFAULT_RATING = 1500.0
DEFAULT_RD = 350.0
DEFAULT_VOL = 0.06
TAU = 0.5          # constante del sistema: qué tanto puede cambiar la volatilidad entre periodos
EPSILON = 1e-6      # tolerancia de convergencia del paso iterativo


@dataclass
class RatingState:
    """Estado de un jugador en un pool de rating (general o una superficie)."""
    rating: float = DEFAULT_RATING
    rd: float = DEFAULT_RD
    vol: float = DEFAULT_VOL
    n_matches: int = 0              # partidos jugados en este pool (para blending por superficie)
    periods_since_active: int = 0   # para inflar RD en jugadores inactivos (lazy)

    def to_glicko2_scale(self):
        mu = (self.rating - DEFAULT_RATING) / SCALE
        phi = self.rd / SCALE
        return mu, phi

    def apply_inactivity(self):
        """RD crece durante periodos sin jugar: phi* = sqrt(phi^2 + n*vol^2)."""
        if self.periods_since_active == 0:
            return
        mu, phi = self.to_glicko2_scale()
        phi_star = math.sqrt(phi ** 2 + self.periods_since_active * self.vol ** 2)
        self.rd = phi_star * SCALE
        self.periods_since_active = 0


def _g(phi: float) -> float:
    return 1.0 / math.sqrt(1.0 + 3.0 * phi ** 2 / math.pi ** 2)


def _E(mu: float, mu_j: float, phi_j: float) -> float:
    return 1.0 / (1.0 + math.exp(-_g(phi_j) * (mu - mu_j)))


def _solve_new_volatility(phi: float, sigma: float, v: float, delta: float) -> float:
    """Paso 5 del paper: algoritmo de Illinois (regula falsi) para la nueva volatilidad."""
    a = math.log(sigma ** 2)

    def f(x):
        ex = math.exp(x)
        num = ex * (delta ** 2 - phi ** 2 - v - ex)
        den = 2 * (phi ** 2 + v + ex) ** 2
        return (num / den) - (x - a) / (TAU ** 2)

    A = a
    if delta ** 2 > phi ** 2 + v:
        B = math.log(delta ** 2 - phi ** 2 - v)
    else:
        k = 1
        while f(a - k * TAU) < 0:
            k += 1
        B = a - k * TAU

    fA, fB = f(A), f(B)
    while abs(B - A) > EPSILON:
        C = A + (A - B) * fA / (fB - fA)
        fC = f(C)
        if fC * fB <= 0:
            A, fA = B, fB
        else:
            fA = fA / 2.0
        B, fB = C, fC

    return math.exp(A / 2.0)


def update_rating_period(player: RatingState, games: list) -> RatingState:
    """
    Actualiza el rating de un jugador dado un conjunto de partidos jugados en un
    mismo periodo (una semana). Cada elemento de `games` es un dict:
        {"opponent": RatingState (pre-periodo), "score": 1.0 o 0.0, "weight": float}
    `weight` combina nivel de torneo, retiro, y margen de victoria (ver elo_engine.py).

    Si `games` está vacío, solo se infla la incertidumbre (RD) por inactividad.
    """
    player.apply_inactivity()

    if not games:
        player.periods_since_active += 1
        return player

    mu, phi = player.to_glicko2_scale()

    v_inv = 0.0
    delta_sum = 0.0
    for g in games:
        opp_mu, opp_phi = g["opponent"].to_glicko2_scale()
        g_phi_j = _g(opp_phi)
        E_val = _E(mu, opp_mu, opp_phi)
        w = g["weight"]
        v_inv += w * (g_phi_j ** 2) * E_val * (1 - E_val)
        delta_sum += w * g_phi_j * (g["score"] - E_val)

    if v_inv == 0:
        # caso degenerado (todos los pesos en 0): tratar como inactividad
        player.periods_since_active += 1
        return player

    v = 1.0 / v_inv
    delta = v * delta_sum

    new_sigma = _solve_new_volatility(phi, player.vol, v, delta)
    phi_star = math.sqrt(phi ** 2 + new_sigma ** 2)
    new_phi = 1.0 / math.sqrt(1.0 / phi_star ** 2 + 1.0 / v)
    new_mu = mu + new_phi ** 2 * delta_sum

    player.rating = new_mu * SCALE + DEFAULT_RATING
    player.rd = new_phi * SCALE
    player.vol = new_sigma
    player.n_matches += len(games)
    player.periods_since_active = 0

    return player


def win_probability(a: RatingState, b: RatingState) -> float:
    """Probabilidad de que `a` le gane a `b`, dado el estado (post-inactividad) de ambos."""
    mu_a, phi_a = a.to_glicko2_scale()
    mu_b, phi_b = b.to_glicko2_scale()
    combined_phi = math.sqrt(phi_a ** 2 + phi_b ** 2)
    return _E(mu_a, mu_b, combined_phi)