import os, sys, json, subprocess, time, glob

OUT = os.environ.get("OUT_DIR", "/kaggle/working/out")
os.makedirs(OUT, exist_ok=True)
ARGS = json.loads(os.environ.get("JOB_ARGS", "{}"))
PROMPTS = ARGS.get("prompts") or []
if not PROMPTS:
    raise SystemExit("no prompts")
SUFFIX = ARGS.get("suffix", ", single object, centered, plain white background, studio lighting, high detail, 3d render")
MODEL = ARGS.get("model", "YuCollection/FLUX.1-schnell-Diffusers")
WORK = "/kaggle/working/w"
os.makedirs(WORK, exist_ok=True)


def sh(cmd, check=True, env=None):
    print("+", cmd, flush=True)
    r = subprocess.run(cmd, shell=True, env=env)
    if check and r.returncode != 0:
        raise SystemExit("FAILED: " + cmd)
    return r.returncode


def stage1_images():
    """FLUX schnell -> PNGs, in a subprocess so GPU memory is fully freed."""
    code = r'''
import torch, json, sys
from diffusers import FluxPipeline
a = json.load(open("%s/in.json"))
p = FluxPipeline.from_pretrained(a["model"], torch_dtype=torch.float16, device_map="balanced")
for i, pr in enumerate(a["prompts"]):
    im = p(pr + a["suffix"], height=768, width=768, num_inference_steps=4, guidance_scale=0.0,
           max_sequence_length=256, generator=torch.Generator("cpu").manual_seed(i)).images[0]
    im.save("%s/img_%%d.png" %% i)
''' % (WORK, WORK)
    json.dump({"model": MODEL, "prompts": PROMPTS, "suffix": SUFFIX}, open(WORK + "/in.json", "w"))
    open(WORK + "/s1.py", "w").write(code)
    sh("pip -q install diffusers transformers accelerate sentencepiece protobuf")
    sh("python %s/s1.py" % WORK)


def stage2_cutout():
    sh("pip -q install 'rembg[gpu]' onnxruntime-gpu pillow", check=False)
    code = r'''
import glob
from rembg import remove, new_session
from PIL import Image
s = new_session("isnet-general-use")
for f in sorted(glob.glob("%s/img_*.png")):
    im = remove(Image.open(f).convert("RGB"), session=s)
    im.save(f.replace("img_", "cut_"))
''' % WORK
    open(WORK + "/s2.py", "w").write(code)
    sh("python %s/s2.py" % WORK)


def stage3_trellis():
    if not os.path.isdir("/kaggle/working/TRELLIS"):
        sh("git clone --recurse-submodules https://github.com/microsoft/TRELLIS /kaggle/working/TRELLIS")
    sh("pip -q install pillow imageio imageio-ffmpeg tqdm easydict opencv-python-headless scipy ninja "
       "trimesh xatlas pyvista pymeshfix igraph transformers open3d plyfile")
    sh("pip -q install git+https://github.com/EasternJournalist/utils3d.git", check=False)
    sh("pip -q install git+https://github.com/NVlabs/nvdiffrast.git --no-build-isolation", check=False)
    code = r'''
import os, glob
os.environ["SPCONV_ALGO"] = "native"
os.environ["ATTN_BACKEND"] = "sdpa"
import sys; sys.path.insert(0, "/kaggle/working/TRELLIS")
from PIL import Image
from trellis.pipelines import TrellisImageTo3DPipeline
from trellis.utils import postprocessing_utils
p = TrellisImageTo3DPipeline.from_pretrained("microsoft/TRELLIS-image-large")
p.cuda()
for f in sorted(glob.glob("%s/cut_*.png")):
    out = p.run(Image.open(f), seed=1)
    glb = postprocessing_utils.to_glb(out["gaussian"][0], out["mesh"][0], simplify=0.95, texture_size=1024)
    glb.export(os.path.join("%s", os.path.basename(f).replace("cut_", "asset_").replace(".png", ".glb")))
''' % (WORK, OUT)
    open(WORK + "/s3.py", "w").write(code)
    sh("python %s/s3.py" % WORK)


t = time.time()
stage1_images()
stage2_cutout()
for f in glob.glob(WORK + "/*.png"):
    os.system("cp %s %s/" % (f, OUT))
stage3_trellis()
glbs = glob.glob(OUT + "/*.glb")
if not glbs:
    raise SystemExit("no GLB produced")
json.dump({"secs": time.time() - t, "glbs": [os.path.basename(g) for g in glbs]}, open(OUT + "/asset3d.json", "w"))
