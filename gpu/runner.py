import os, sys, json, threading, time, subprocess, traceback
# JOB_SPEC is prepended by the workflow
spec = json.loads(JOB_SPEC)
OUT = "/kaggle/working"
t0 = time.time()
def log(*a):
    print("[runner %ds]" % (time.time() - t0), *a, flush=True)
# Watchdog: guarantees the kernel (and GPU quota burn) ends, whatever the job does.
def _kill():
    log("WATCHDOG: max_minutes exceeded, killing")
    open(OUT + "/WATCHDOG.txt", "w").write("timeout")
    os._exit(3)
w = threading.Timer(spec["max_minutes"] * 60, _kill); w.daemon = True; w.start()
rc = 1
try:
    subprocess.run("nvidia-smi", shell=True)
    subprocess.run(["git", "clone", "--depth", "1", spec["repo"], OUT + "/repo"], check=True)
    subprocess.run(["git", "-C", OUT + "/repo", "fetch", "--depth", "1", "origin", spec["sha"]], check=False)
    subprocess.run(["git", "-C", OUT + "/repo", "checkout", spec["sha"]], check=False)
    env = dict(os.environ, JOB_ARGS=json.dumps(spec["args"]), OUT_DIR=OUT + "/out")
    os.makedirs(OUT + "/out", exist_ok=True)
    rc = subprocess.run([sys.executable, OUT + "/repo/gpu/jobs/%s.py" % spec["job"]], env=env).returncode
except Exception:
    traceback.print_exc()
subprocess.run("rm -rf " + OUT + "/repo", shell=True)
if rc == 0:
    open(OUT + "/DONE.ok", "w").write("ok")
log("exit rc", rc)
os._exit(0 if rc == 0 else 1)
