# SPDX-License-Identifier: GPL-3.0-or-later
"""Solution de référence de la bielle-manivelle : Newton-Euler plan, INDÉPENDANTE d'Exudyn.

Transposée de `reference(t)` de prototypes/exudyn_bielle/bielle_manivelle.py. Module d'aide pour
les tests, sans aucun import de meca3d ni d'exudyn.

Plan (x, y), z sort du plan, pesanteur -g·y. Solides : 0 bâti, 1 manivelle OA, 2 bielle AB,
3 piston (centre B, glisse selon x). Liaisons : L01 pivot motorisée en O, L12 pivot en A,
L23 linéaire annulaire d'axe z en B, L30 glissière selon x.
"""

import numpy as np

# Données de la SPEC (EX-40) et du prototype
R_MANIVELLE = 0.10  # m
L_BIELLE = 0.30  # m
SECTION = 0.02  # section carrée des barres (m)
RHO = 7800.0  # kg/m3
M_PISTON = 0.5  # kg
G = 9.81  # m/s²
OMEGA, T_MONTEE = 20.0, 0.2  # rad/s, s

M1 = RHO * R_MANIVELLE * SECTION**2
M2 = RHO * L_BIELLE * SECTION**2
I1 = M1 * (R_MANIVELLE**2 + SECTION**2) / 12
I2 = M2 * (L_BIELLE**2 + SECTION**2) / 12


def theta(t: float) -> float:
    """Loi d'entrée : montée en vitesse sur 0,2 s puis ω = 20 rad/s."""
    if t < T_MONTEE:
        return OMEGA / 2 * (t - T_MONTEE / np.pi * np.sin(np.pi * t / T_MONTEE))
    return OMEGA / 2 * T_MONTEE + OMEGA * (t - T_MONTEE)


def theta_t(t: float) -> float:
    return OMEGA / 2 * (1 - np.cos(np.pi * t / T_MONTEE)) if t < T_MONTEE else OMEGA


def theta_tt(t: float) -> float:
    if t < T_MONTEE:
        return OMEGA * np.pi / (2 * T_MONTEE) * np.sin(np.pi * t / T_MONTEE)
    return 0.0


def reference(t: float) -> dict[str, np.ndarray | float]:
    """Cinématique exacte en fermeture de boucle, puis système linéaire 9×9 de Newton-Euler.

    Clés : O = {bâti→1}, A = {1→2}, B = {2→3} (forces, N), N = effort normal {bâti→3} (N),
    C = couple moteur {bâti→1} (N·m), xB = abscisse du piston (m).
    """
    r, lg = R_MANIVELLE, L_BIELLE
    th, w, al = theta(t), theta_t(t), theta_tt(t)
    b = np.arcsin(-r * np.sin(th) / lg)
    cb = np.cos(b)
    b_t = -r * w * np.cos(th) / (lg * cb)
    b_tt = (-r * al * np.cos(th) + r * w**2 * np.sin(th) + lg * np.sin(b) * b_t**2) / (lg * cb)

    pa = r * np.array([np.cos(th), np.sin(th)])
    pb = pa + lg * np.array([cb, np.sin(b)])
    g1, g2 = pa / 2, (pa + pb) / 2
    u, n = np.array([np.cos(th), np.sin(th)]), np.array([-np.sin(th), np.cos(th)])
    v, m = np.array([cb, np.sin(b)]), np.array([-np.sin(b), cb])
    a_a = r * (al * n - w**2 * u)
    a_g1 = a_a / 2
    a_b = a_a + lg * (b_tt * m - b_t**2 * v)
    a_g2 = (a_a + a_b) / 2

    # inconnues : Ox Oy C | Ax Ay | Bx By | N Mp
    k = np.zeros((9, 9))
    s = np.zeros(9)
    k[0, [0, 3]] = [1, -1]
    s[0] = M1 * a_g1[0]
    k[1, [1, 4]] = [1, -1]
    s[1] = M1 * a_g1[1] + M1 * G
    d_o, d_a = -g1, pa - g1
    k[2, 0], k[2, 1], k[2, 2] = -d_o[1], d_o[0], 1
    k[2, 3], k[2, 4] = d_a[1], -d_a[0]
    s[2] = I1 * al
    k[3, [3, 5]] = [1, -1]
    s[3] = M2 * a_g2[0]
    k[4, [4, 6]] = [1, -1]
    s[4] = M2 * a_g2[1] + M2 * G
    d_a2, d_b2 = pa - g2, pb - g2
    k[5, 3], k[5, 4] = -d_a2[1], d_a2[0]
    k[5, 5], k[5, 6] = d_b2[1], -d_b2[0]
    s[5] = I2 * b_tt
    k[6, 5] = 1
    s[6] = M_PISTON * a_b[0]
    k[7, [6, 7]] = [1, 1]
    s[7] = M_PISTON * G
    k[8, 8] = 1
    x = np.linalg.solve(k, s)
    return {
        "O": x[0:2],
        "C": float(x[2]),
        "A": x[3:5],
        "B": x[5:7],
        "N": float(x[7]),
        "xB": float(pb[0]),
    }
