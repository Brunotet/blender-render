"""Hard-fail if any asset is missing from assets/LICENSES.json or has a license that needs attribution."""
import json, os, sys
m = json.load(open("assets/LICENSES.json"))
ok, bad = set(m["allowed"]), []
listed = {a["path"] for a in m["assets"]}
for a in m["assets"]:
    if a["license"] not in ok: bad.append(f"{a['path']}: license {a['license']} not allowed")
    if not os.path.exists(a["path"]): bad.append(f"{a['path']}: listed but missing")
for root in ("assets", "scenes"):
    for d, _, fs in os.walk(root):
        for f in fs:
            p = os.path.join(d, f).replace("\\", "/")
            if f.endswith((".pyc", "LICENSES.json")) or "__pycache__" in p: continue
            if p not in listed: bad.append(f"{p}: not in LICENSES.json")
if bad:
    sys.exit("FATAL license check:\n" + "\n".join(bad))
print("license check ok:", len(listed), "assets")
