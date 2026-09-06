# Reporte de análisis exploratorio

Etapa 1 · Actividad 2 — datos ATP/WTA, 1990–2026


## ATP

- Partidos analizados (con ranking registrado en ambos lados): 112,971

- Tasa de upset general: 34.9%

- El favorito (mejor ranking) gana el 50.2% de las veces cuando la diferencia de ranking es de solo 1 puesto, y el 73.4% cuando la diferencia es de 90+ puestos.

- Ronda con más upsets: SF (37.4%). Ronda con menos: R16 (34.2%).

- Superficie con más upsets: Carpet (35.9%). Con menos: Hard (34.2%).


![matches by surface](eda_outputs/atp_matches_by_surface_year.png)

![winrate vs rankgap](eda_outputs/atp_winrate_vs_rankgap.png)

![upset by round](eda_outputs/atp_upset_by_round.png)

![upset by surface](eda_outputs/atp_upset_by_surface.png)

![upset over time](eda_outputs/atp_upset_over_time.png)


## WTA

- Partidos analizados (con ranking registrado en ambos lados): 94,192

- Tasa de upset general: 33.5%

- El favorito (mejor ranking) gana el 52.4% de las veces cuando la diferencia de ranking es de solo 1 puesto, y el 75.5% cuando la diferencia es de 90+ puestos.

- Ronda con más upsets: F (37.1%). Ronda con menos: R16 (32.8%).

- Superficie con más upsets: Grass (34.2%). Con menos: Carpet (30.4%).


![matches by surface](eda_outputs/wta_matches_by_surface_year.png)

![winrate vs rankgap](eda_outputs/wta_winrate_vs_rankgap.png)

![upset by round](eda_outputs/wta_upset_by_round.png)

![upset by surface](eda_outputs/wta_upset_by_surface.png)

![upset over time](eda_outputs/wta_upset_over_time.png)


## Implicaciones para el modelo Elo/Glicko-2

- El ranking oficial ya es bastante predictivo, sobre todo con diferencias grandes: esto da un piso (benchmark) claro que el modelo Elo/Glicko debe superar para justificar su uso.

- La tasa de upset varía por superficie: confirma que vale la pena mantener ratings **separados por superficie** en vez de un solo Elo general.

- Contrario a la intuición inicial, la tasa de upset **no baja** en rondas tardías (semifinal y final incluso muestran una tasa ligeramente más alta que octavos/cuartos). Esto no significa que las finales sean más caóticas: lo que cambia es la composición de los partidos que llegan ahí — en rondas tempranas hay más brechas de ranking grandes (top-10 vs. top-150), mientras que en semifinal/final casi siempre son dos jugadores de elite con una brecha de ranking chica, donde el ranking pesa mucho menos como señal. Esto refuerza que el modelo debe pesar la **brecha de ranking real**, no la ronda en sí, y sugiere que el simulador de cuadros (Etapa 2) va a necesitar más granularidad que 'favorito vs. no favorito' entre jugadores top.
