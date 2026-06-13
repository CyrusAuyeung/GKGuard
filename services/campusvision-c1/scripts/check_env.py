from __future__ import annotations

import importlib
import sys


def check(name: str):
    try:
        module = importlib.import_module(name)
        version = getattr(module, "__version__", "unknown")
        print(f"[OK] {name}: {version}")
        return module
    except Exception as exc:
        print(f"[MISS] {name}: {exc}")
        return None


print("Python:", sys.version)
torch = check("torch")
check("cv2")
check("numpy")
check("fastapi")
check("insightface")
check("onnxruntime")

if torch is not None:
    try:
        print("[OK] torch.cuda.is_available:", torch.cuda.is_available())
        if torch.cuda.is_available():
            print("[OK] cuda device:", torch.cuda.get_device_name(0))
    except Exception as exc:
        print("[WARN] CUDA check failed:", exc)

print("Environment check finished.")
