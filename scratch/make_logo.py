import numpy as np
from PIL import Image
import shutil

src_path = r"C:\Users\pavan\.gemini\antigravity-ide\brain\10754ef2-2bf8-44eb-b865-3fb1d7265303\.user_uploaded\media_1791790462864.png"

# Save exact original copy too
shutil.copy2(src_path, "frontend/logo_raw.png")

im = Image.open(src_path).convert("RGBA")
arr = np.array(im, dtype=np.float32)

# Estimate background from corners
corners = np.concatenate([
    arr[:20, :20, :3].reshape(-1, 3),
    arr[:20, -20:, :3].reshape(-1, 3),
    arr[-20:, :20, :3].reshape(-1, 3),
    arr[-20:, -20:, :3].reshape(-1, 3)
], axis=0)
bg = np.median(corners, axis=0)
print("Estimated BG color:", bg)

diff = np.sqrt(np.sum((arr[:, :, :3] - bg)**2, axis=2))

# Smooth transition
low_th = 10.0
high_th = 28.0
alpha = np.clip((diff - low_th) / (high_th - low_th), 0.0, 1.0) * 255.0
arr[:, :, 3] = alpha

out = Image.fromarray(arr.astype(np.uint8))
bbox = out.getbbox()
if bbox:
    pad = 4
    bbox = (max(0, bbox[0]-pad), max(0, bbox[1]-pad), min(out.width, bbox[2]+pad), min(out.height, bbox[3]+pad))
    out = out.crop(bbox)

out.save("frontend/logo.png")
print("Saved transparent logo to frontend/logo.png, size:", out.size)
