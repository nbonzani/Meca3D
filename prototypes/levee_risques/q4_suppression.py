"""Q4 (suite) : effacement des trajectoires et de l'étude créées par q4_trajectoires.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from sc_client import Client, sauver
from sc_maquette import etat

c = Client()
out = {"avant": etat(c), "ui_documents": c.appel("ui.inspect")["result"]["documents"]}
d = c.appel("document.inspect")["result"]
out["chemin_est_la_copie"] = d["path"].replace("\\", "/").endswith("maquettes/bielle_trace.solidcraft")
r = c.cmd("timeline.delete", {"features": ["Trace_P", "Trace_alt"]})
out["timeline_delete"] = r
out["apres_delete_traces"] = etat(c)
out["sketches"] = c.appel("document.inspect")["result"]["sketches"]
r = c.cmd("motion.delete", {"study": "rotation_manivelle"})
out["motion_delete"] = r
out["apres_delete_etude"] = etat(c)
out["motion_list"] = c.cmd("motion.list")
sauver("q4_suppression.json", out)
print(json.dumps(out, indent=1)[:2500])
