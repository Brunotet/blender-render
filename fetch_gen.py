"""Download GPU-generated organ GLBs listed in gen/organs.json into gen/organs/ (hard-fails on any problem)."""
import json, os, subprocess, sys
spec = json.load(open("gen/organs.json"))
os.makedirs("gen/organs", exist_ok=True)
man = {}
for name, ent in spec["organs"].items():
    url = f"https://github.com/{spec['repo']}/releases/download/{ent['release']}/{ent['file']}"
    dst = f"gen/organs/{name}.glb"
    subprocess.run(["curl", "-fL", "--retry", "3", "-o", dst, url], check=True)
    if os.path.getsize(dst) < 1000:
        sys.exit(f"FATAL: {dst} too small")
    man[name] = {"file": f"{name}.glb", "rot": ent.get("rot", [0, 0, 0])}
json.dump(man, open("gen/organs/manifest.json", "w"))
print("fetched", sorted(man))
