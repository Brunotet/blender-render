import os, sys, json, subprocess, time, glob, traceback, shutil

OUT = os.environ.get("OUT_DIR", "/kaggle/working/out")
os.makedirs(OUT, exist_ok=True)
A = json.loads(os.environ.get("JOB_ARGS", "{}"))
PROMPTS = A.get("prompts") or []
if not PROMPTS:
    raise SystemExit("no prompts")
SUFFIX = A.get("suffix", ", single object, centered, plain white background, studio lighting, high detail, 3d render")
MODEL = A.get("model", "YuCollection/FLUX.1-schnell-Diffusers")
BACKENDS = A.get("backends", ["trellis", "triposr"])
W = "/kaggle/working/w"
V = "/kaggle/working/v310"
VPY = V + "/bin/python"
os.makedirs(W, exist_ok=True)
LOG = open(OUT + "/asset3d.log", "a")


def log(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    LOG.write(s + "\n"); LOG.flush()


def sh(cmd, check=True, env=None):
    log("+", cmd)
    r = subprocess.run(cmd, shell=True, env=env)
    if check and r.returncode != 0:
        raise RuntimeError("FAILED(%d): %s" % (r.returncode, cmd))
    return r.returncode


def put(name, code):
    p = W + "/" + name
    open(p, "w").write(code)
    return p


# ---------------- stage 1: FLUX schnell (system python) ----------------
S1 = r'''
import torch, json
from diffusers import FluxPipeline
a = json.load(open("W/in.json"))
p = FluxPipeline.from_pretrained(a["model"], torch_dtype=torch.float16, device_map="balanced")
for i, pr in enumerate(a["prompts"]):
    im = p(pr + a["suffix"], height=768, width=768, num_inference_steps=4, guidance_scale=0.0,
           max_sequence_length=256, generator=torch.Generator("cpu").manual_seed(i)).images[0]
    im.save("W/img_%d.png" % i)
'''.replace("W/", W + "/")

# ---------------- stage 2: cutout ----------------
S2 = r'''
import glob
from rembg import remove, new_session
from PIL import Image
s = new_session("isnet-general-use")
for f in sorted(glob.glob("W/img_*.png")):
    remove(Image.open(f).convert("RGB"), session=s).save(f.replace("img_", "cut_"))
'''.replace("W/", W + "/")

# ---------------- backend: TRELLIS v1 (MIT) in py3.10 / torch2.4 / cu121 ----------------
T = r'''
import os, sys, glob, json, traceback
os.environ["SPCONV_ALGO"] = "native"
os.environ["ATTN_BACKEND"] = "xformers"
sys.path.insert(0, "/kaggle/working/TRELLIS")
from PIL import Image
from trellis.pipelines import TrellisImageTo3DPipeline
from trellis.utils import postprocessing_utils
p = TrellisImageTo3DPipeline.from_pretrained("microsoft/TRELLIS-image-large")
p.cuda()
done = []
for f in sys.argv[1:]:
    n = os.path.basename(f).replace("cut_", "").replace(".png", "")
    try:
        out = p.run(Image.open(f), seed=1, preprocess_image=False)
        g = postprocessing_utils.to_glb(out["gaussian"][0], out["mesh"][0], simplify=0.95, texture_size=1024)
        g.export("OUT/asset_%s.glb" % n)
        done.append(n)
    except Exception:
        traceback.print_exc()
json.dump(done, open("W/trellis_done.json", "w"))
'''.replace("OUT", OUT).replace("W/", W + "/")

# ---------------- backend: TripoSR (MIT), marching cubes via skimage ----------------
TS = r'''
import os, sys, json, traceback, types
import numpy as np, torch
sys.path.insert(0, "/kaggle/working/TripoSR")
from skimage import measure
m = types.ModuleType("torchmcubes")
def marching_cubes(vol, thr):
    v, f, _, _ = measure.marching_cubes(vol.detach().cpu().numpy(), level=float(thr))
    return torch.from_numpy(v.copy()).float(), torch.from_numpy(f.copy()).long()
m.marching_cubes = marching_cubes
sys.modules["torchmcubes"] = m
from PIL import Image
from tsr.system import TSR
from tsr.utils import resize_foreground
model = TSR.from_pretrained("stabilityai/TripoSR", config_name="config.yaml", weight_name="model.ckpt")
model.renderer.set_chunk_size(8192)
model.to("cuda")
done = []
for f in sys.argv[1:]:
    n = os.path.basename(f).replace("cut_", "").replace(".png", "")
    try:
        im = resize_foreground(Image.open(f).convert("RGBA"), 0.85)
        a = np.array(im).astype(np.float32) / 255.0
        a = a[:, :, :3] * a[:, :, 3:4] + (1 - a[:, :, 3:4]) * 0.5
        im = Image.fromarray((a * 255).astype(np.uint8))
        with torch.no_grad():
            codes = model([im], device="cuda")
        mesh = model.extract_mesh(codes, True, resolution=256)[0]
        mesh.export("OUT/asset_%s.glb" % n)
        done.append(n)
    except Exception:
        traceback.print_exc()
json.dump(done, open("W/triposr_done.json", "w"))
'''.replace("OUT", OUT).replace("W/", W + "/")


def make_venv():
    if os.path.exists(VPY):
        return
    sh("pip -q install uv")
    sh("uv venv --python 3.10 " + V)
    ip = "uv pip install -q --python " + VPY + " "
    sh(ip + "torch==2.4.0 torchvision==0.19.0 --index-url https://download.pytorch.org/whl/cu121")
    sh(ip + "setuptools wheel numpy==1.26.4 pillow imageio imageio-ffmpeg tqdm easydict opencv-python-headless "
            "scipy ninja trimesh xatlas pyvista pymeshfix igraph transformers==4.46.3 huggingface_hub "
            "omegaconf einops scikit-image plyfile open3d onnxruntime rembg")


def trellis_setup():
    make_venv()
    ip = "uv pip install -q --python " + VPY + " "
    if not os.path.isdir("/kaggle/working/TRELLIS"):
        sh("git clone --recurse-submodules https://github.com/microsoft/TRELLIS /kaggle/working/TRELLIS")
    sh(ip + "xformers==0.0.27.post2 --no-deps --index-url https://download.pytorch.org/whl/cu121")
    sh(ip + "spconv-cu120")
    sh(ip + "git+https://github.com/EasternJournalist/utils3d.git" + chr(64) + "9a4eb15e4021b67b12c460c7057d642626897ec8")
    log("nvcc:", shutil.which("nvcc"), os.path.exists("/usr/local/cuda"))
    if not os.path.isdir("/kaggle/working/nvdiffrast"):
        sh("git clone https://github.com/NVlabs/nvdiffrast /kaggle/working/nvdiffrast")
    env = dict(os.environ, TORCH_CUDA_ARCH_LIST="7.5", CUDA_HOME=os.environ.get("CUDA_HOME", "/usr/local/cuda"))
    sh(ip + "--no-build-isolation /kaggle/working/nvdiffrast", env=env)


def triposr_setup():
    make_venv()
    if not os.path.isdir("/kaggle/working/TripoSR"):
        sh("git clone https://github.com/VAST-AI-Research/TripoSR /kaggle/working/TripoSR")


def run_backend(name, files):
    sh_ = put(name + ".py", {"trellis": T, "triposr": TS}[name])
    {"trellis": trellis_setup, "triposr": triposr_setup}[name]()
    sh(VPY + " " + sh_ + " " + " ".join(files))


t0 = time.time()
sh("pip -q install diffusers transformers accelerate sentencepiece protobuf")
put("in.json", json.dumps({"model": MODEL, "prompts": PROMPTS, "suffix": SUFFIX}))
sh("python " + put("s1.py", S1))
sh("pip -q install rembg onnxruntime-gpu pillow", check=False)
sh("pip -q install rembg onnxruntime pillow", check=False)
sh("python " + put("s2.py", S2))
for f in glob.glob(W + "/*.png"):
    shutil.copy(f, OUT)

cuts = sorted(glob.glob(W + "/cut_*.png"))
used = {}
for b in BACKENDS:
    todo = [f for f in cuts if os.path.basename(f).replace("cut_", "").replace(".png", "") not in used]
    if not todo:
        break
    log("=== backend", b, "for", len(todo), "images")
    try:
        run_backend(b, todo)
    except Exception:
        log(traceback.format_exc())
    for g in glob.glob(OUT + "/asset_*.glb"):
        n = os.path.basename(g)[6:-4]
        if n not in used and os.path.getsize(g) > 1000:
            used[n] = b
    log("so far:", used)

missing = [os.path.basename(f) for f in cuts if os.path.basename(f)[4:-4] not in used]
json.dump({"secs": time.time() - t0, "backend_per_asset": used, "missing": missing},
          open(OUT + "/asset3d.json", "w"))
if missing:
    raise SystemExit("no backend produced: %s" % missing)
