import os, json, time, torch
out = os.environ["OUT_DIR"]
args = json.loads(os.environ.get("JOB_ARGS", "{}"))
prompts = args.get("prompts") or ["a single anatomical human heart, medical model, centered, isolated on plain white background"]
size = int(args.get("size", 768))
t0 = time.time()
import subprocess, sys
subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "diffusers", "transformers", "accelerate", "sentencepiece", "protobuf"])
print("pip done", time.time() - t0, flush=True)
from diffusers import FluxPipeline
pipe = FluxPipeline.from_pretrained("black-forest-labs/FLUX.1-schnell", torch_dtype=torch.float16, device_map="balanced")
print("loaded", time.time() - t0, flush=True)
for i, p in enumerate(prompts):
    img = pipe(p, num_inference_steps=4, guidance_scale=0.0, height=size, width=size, max_sequence_length=256).images[0]
    img.save(os.path.join(out, "img_%d.png" % i))
    print("gen", i, time.time() - t0, flush=True)
json.dump({"prompts": prompts, "secs": time.time() - t0}, open(os.path.join(out, "img_gen.json"), "w"))
