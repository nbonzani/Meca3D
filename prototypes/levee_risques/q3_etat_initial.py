"""Q3 : état initial de la bielle (valeurs articulaires, poses, révision, dirty)."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from sc_client import Client, sauver

c = Client()
doc = c.appel("document.inspect")["result"]
print({k: doc[k] for k in ("dirty", "revision", "undo", "redo", "marker", "name")})
jl = c.cmd("joint.list")
sauver("q3_joint_list_initial.json", jl)
cl = c.cmd("component.list")
sauver("q3_component_list_initial.json", cl)
for j in jl["result"]["joints"]:
    print(j["id"], j["name"], j["type"], j["values"], j["a"], j["b"])
for ch in cl["result"]["components"][0]["children"]:
    print(ch["id"], ch["name"], ch["grounded"], [round(x, 6) for x in sum(ch["transform"], [])])
print(json.dumps(c.cmd("motion.list")))
print(json.dumps(c.appel("control.pending")))
