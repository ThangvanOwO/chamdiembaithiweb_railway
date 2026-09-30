"""Convert bubble_cnn.pth → bubble_cnn.onnx for faster inference."""
import sys
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ENGINE_DIR = REPO_ROOT / 'grading' / 'engine'
sys.path.insert(0, str(ENGINE_DIR))

import torch
from train_bubble_cnn import BubbleCNN

MODEL_PTH = str(ENGINE_DIR / 'bubble_cnn.pth')
MODEL_ONNX = str(ENGINE_DIR / 'bubble_cnn.onnx')

print(f"Loading model from {MODEL_PTH}...")
model = BubbleCNN()
state = torch.load(MODEL_PTH, map_location='cpu', weights_only=True)
model.load_state_dict(state)
model.eval()

# Dummy input: (batch=1, channels=1, H=32, W=32)
dummy = torch.randn(1, 1, 32, 32)

print(f"Exporting to ONNX: {MODEL_ONNX}...")
torch.onnx.export(
    model, dummy, MODEL_ONNX,
    input_names=['input'],
    output_names=['output'],
    dynamic_axes={'input': {0: 'batch'}, 'output': {0: 'batch'}},
    opset_version=17,
)

# Verify
import onnxruntime as ort
session = ort.InferenceSession(MODEL_ONNX)
import numpy as np
test_input = np.random.randn(1, 1, 32, 32).astype(np.float32)
outputs = session.run(None, {'input': test_input})
print(f"ONNX output shape: {outputs[0].shape}")
print(f"ONNX output: {outputs[0]}")

# Benchmark
import time
# PyTorch
t0 = time.time()
for _ in range(100):
    with torch.no_grad():
        model(torch.from_numpy(test_input))
pytorch_time = time.time() - t0

# ONNX
t0 = time.time()
for _ in range(100):
    session.run(None, {'input': test_input})
onnx_time = time.time() - t0

print(f"\nBenchmark (100 inferences):")
print(f"  PyTorch: {pytorch_time:.3f}s ({pytorch_time/100*1000:.1f}ms/image)")
print(f"  ONNX:    {onnx_time:.3f}s ({onnx_time/100*1000:.1f}ms/image)")
print(f"  Speedup: {pytorch_time/onnx_time:.1f}x")
print(f"\nDone! Model saved to {MODEL_ONNX}")
