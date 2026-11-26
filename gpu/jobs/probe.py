import os, json
out = os.environ["OUT_DIR"]
info = {}
import torch
info["torch"] = torch.__version__
info["cuda"] = torch.cuda.is_available()
assert info["cuda"], "CUDA unavailable"
n = torch.cuda.device_count()
info["devs"] = [torch.cuda.get_device_name(i) for i in range(n)]
info["cap"] = [torch.cuda.get_device_capability(i) for i in range(n)]
x = torch.randn(2048, 2048, device="cuda")
info["matmul_ok"] = bool(torch.mm(x, x).sum().isfinite())
json.dump(info, open(out + "/probe.json", "w"), indent=1)
print(info)
