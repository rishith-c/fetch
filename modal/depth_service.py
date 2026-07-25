"""
FETCH cloud depth — Modal service. Ultra-fast monocular depth as a SECOND
perception layer (the sonars remain the 0-latency safety layer on the Uno).

Model: Depth-Anything-V2-Small — ~25 ms on an A10G at 518px. The container is
kept WARM (min_containers=1) so there is never a cold-start during the demo.

Deploy (one time, from the Mac):
    pip install modal && modal setup        # login once
    modal deploy modal/depth_service.py
It prints a URL like https://<user>--fetch-depth-web.modal.run
Put that URL in pi/cloud_depth.py.

Request:  POST raw JPEG bytes
Response: {"zones": [L, CL, C, CR, R], "ms": inference_ms}
  zones = five 0..1 clearance scores across the image (1 = far/clear, 0 = close)
  computed from the near-field depth percentile per vertical strip — exactly
  what the crowd-nav layer needs, tiny payload back.
"""
import modal

app = modal.App("fetch-depth")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("torch", "torchvision", "opencv-python-headless",
                 "transformers", "pillow", "numpy", "fastapi[standard]")
)

@app.cls(image=image, gpu="a10g", min_containers=1, scaledown_window=600)
class Depth:
    @modal.enter()
    def load(self):
        import torch
        from transformers import pipeline
        self.pipe = pipeline("depth-estimation",
                             model="depth-anything/Depth-Anything-V2-Small-hf",
                             device="cuda", torch_dtype=torch.float16)

    @modal.method()
    def zones(self, jpeg: bytes):
        import io, time, numpy as np
        from PIL import Image
        t0 = time.time()
        img = Image.open(io.BytesIO(jpeg)).convert("RGB")
        depth = np.array(self.pipe(img)["depth"], dtype=np.float32)
        # relative depth: larger = nearer for DA-v2 output map; normalize 0..1
        d = (depth - depth.min()) / (depth.ptp() + 1e-6)
        h, w = d.shape
        band = d[int(h*0.35):, :]              # ignore ceiling/far top
        strips = np.array_split(band, 5, axis=1)
        # nearness = 95th percentile of each strip; clearance = 1 - nearness
        zones = [float(1.0 - np.percentile(s, 95)) for s in strips]
        return {"zones": [round(z, 3) for z in zones],
                "ms": round((time.time() - t0) * 1000, 1)}

@app.function(image=image)
@modal.fastapi_endpoint(method="POST")
def web(request_body: bytes):
    return Depth().zones.remote(request_body)
