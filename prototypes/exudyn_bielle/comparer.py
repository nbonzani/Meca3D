"""Compare les torseurs de liaison Exudyn à la solution de référence Newton-Euler.

Convention Exudyn établie : ForceLocal/TorqueLocal = action du solide 1 sur le solide 0
(ordre de itemNumbers), réduite au centre de liaison, exprimée dans la base de liaison liée au solide 0.
"""
import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import bielle_manivelle as BM

d = BM.simuler(hyperstatique=False)
t = d["j01F"][:, 0]
n = len(t)
R = BM.R_AXE_Z

ex = {k: np.zeros((n, 2)) for k in ["O", "A", "B"]}
ex["C"], ex["N"] = np.zeros(n), np.zeros(n)
ref = {k: np.zeros((n, 2)) for k in ["O", "A", "B"]}
ref["C"], ref["N"] = np.zeros(n), np.zeros(n)

for i in range(n):
    R1 = d["rot1"][i, 1:].reshape(3, 3)
    R2 = d["rot2"][i, 1:].reshape(3, 3)
    # action de 1 sur 0 en base locale -> action de 0 sur 1 en base globale : -R_J0 · F
    ex["O"][i] = -(R @ d["j01F"][i, 1:])[:2]
    ex["C"][i] = -(R @ d["j01M"][i, 1:])[2]
    ex["A"][i] = -(R1 @ R @ d["j12F"][i, 1:])[:2]
    ex["B"][i] = -(R2 @ R @ d["j23F"][i, 1:])[:2]
    ex["N"][i] = -d["j30F"][i, 2]
    rf = BM.reference(t[i])
    for k in ["O", "A", "B"]:
        ref[k][i] = rf[k]
    ref["C"][i], ref["N"][i] = rf["C"], rf["N"]

print(f"{'grandeur':28} {'max |réf|':>10} {'max |écart|':>12} {'écart relatif':>14}")
pire = 0.0
for k, lib in [("O", "R(0→1) en O  [N]"), ("A", "R(1→2) en A  [N]"), ("B", "R(2→3) en B  [N]"),
               ("N", "N(0→3) piston [N]"), ("C", "Couple moteur C [N·m]")]:
    e = np.abs(ex[k] - ref[k]).max()
    m = np.abs(ref[k]).max()
    pire = max(pire, e / m)
    print(f"{lib:28} {m:10.3f} {e:12.2e} {e / m:14.2e}")
print(f"\nPire écart relatif : {pire:.2e}")

# Figure
fig, ax = plt.subplots(3, 1, figsize=(9, 9), sharex=True)
ax[0].plot(t, ref["C"], "k-", lw=3, alpha=.35, label="référence Newton-Euler")
ax[0].plot(t, ex["C"], "r--", lw=1.2, label="Exudyn GenericJoint")
ax[0].set_ylabel("couple moteur C (N·m)")
ax[0].legend(loc="upper right")
for j, lab in [(0, "x"), (1, "y")]:
    ax[1].plot(t, ref["A"][:, j], "k-", lw=3, alpha=.35)
    ax[1].plot(t, ex["A"][:, j], "--", lw=1.2, label=f"A{lab} (1→2)")
ax[1].set_ylabel("réaction en A (N)")
ax[1].legend(loc="upper right")
ax[2].plot(t, ref["N"], "k-", lw=3, alpha=.35)
ax[2].plot(t, ex["N"], "b--", lw=1.2, label="N (0→3)")
ax[2].set_ylabel("réaction normale piston (N)")
ax[2].set_xlabel("t (s)  — montée en vitesse sur 0,2 s puis ω = 20 rad/s")
ax[2].legend(loc="upper right")
fig.suptitle("Bielle-manivelle : torseurs de liaison Exudyn vs référence")
fig.tight_layout()
fig.savefig("comparaison_bielle.png", dpi=110)
print("Figure : comparaison_bielle.png")

# Variante hyperstatique : pivot en B à la place de la linéaire annulaire (h = 3 en 3D)
print("\n--- Variante hyperstatique (pivot, pivot, pivot, glissière) ---")
try:
    dh = BM.simuler(hyperstatique=True)
    print("Simulation terminée ;", len(dh["j01F"]), "instants enregistrés.")
    i = len(dh["j01F"]) // 2
    print("Couple moteur à mi-parcours : Exudyn", -(R @ dh["j01M"][i, 1:])[2], " réf.", BM.reference(dh["j01F"][i, 0])["C"])
except Exception as exc:  # noqa: BLE001 — on veut rapporter l'échec tel quel
    print("ÉCHEC :", type(exc).__name__, str(exc)[:300])
sys.stdout.flush()
