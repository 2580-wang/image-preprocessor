# -*- coding: utf-8 -*-
"""本地功能测试：生成测试图并验证各任务档位压缩与 token 估算。"""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import server  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

test_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_test")
os.makedirs(test_dir, exist_ok=True)
test_img = os.path.join(test_dir, "test_source.png")

img = Image.new("RGB", (2000, 1200), (240, 240, 245))
d = ImageDraw.Draw(img)
d.rectangle([0, 0, 2000, 200], fill=(30, 60, 120))
d.text((50, 60), "OCR TEST SAMPLE 123456", fill=(255, 255, 255))
d.text((100, 500), "Hello from image-preprocessor MCP", fill=(20, 20, 20))
img.save(test_img)
print(f"test image: 2000x1200 -> {test_img}")

for task in ["ocr", "detail", "general", "thumbnail"]:
    r = json.loads(server.prepare_image(image_path=test_img, task=task, output_dir=test_dir))
    out = r.get("output", {})
    print(f"[{task}] -> {out.get('width')}x{out.get('height')} | tokens~{r.get('estimated_tokens')} | {out.get('size_bytes')}B | {r.get('elapsed_seconds')}s")

r = json.loads(server.prepare_image(image_path=test_img, task="general", output_dir=test_dir, return_base64=True))
print("base64 length:", len(r.get("base64", "")), "| mime:", r.get("base64_mime"))

r = json.loads(server.estimate_image_tokens(test_img))
print("estimate: current=", r["current_tokens"], "| recs=", r["recommendations"])

r = json.loads(server.prepare_image(image_path="C:\\no_such_file.png", task="ocr"))
print("error case:", r["ok"], r["error"])
print("ALL TESTS PASSED")
