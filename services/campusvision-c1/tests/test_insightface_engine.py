from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.vision.engines.insightface_engine import _select_onnx_providers  # noqa: E402


def test_select_onnx_providers_prefers_cuda_without_tensorrt():
    assert _select_onnx_providers(
        ["TensorrtExecutionProvider", "CUDAExecutionProvider", "CPUExecutionProvider"]
    ) == ["CUDAExecutionProvider", "CPUExecutionProvider"]


def test_select_onnx_providers_uses_cpu_when_cuda_missing():
    assert _select_onnx_providers(["AzureExecutionProvider", "CPUExecutionProvider"]) == [
        "CPUExecutionProvider"
    ]

