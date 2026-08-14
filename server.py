#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
image-preprocessor MCP Server
图片预处理工具：根据任务类型自动选择分辨率压缩图片，供本地多模态模型识别。

任务类型 -> 目标最长边（像素）：
  ocr       -> 1600   文字识别 / 表格提取 / 数据读取，保留细节
  detail    -> 1024   详细描述 / 视觉问答 / 内容分析
  general   -> 768    一般识别 / 分类 / 摘要
  thumbnail -> 512    粗略预览 / 批量扫描 / 快速判断

token 估算基于 qwen3.5:9b 实测数据（2559px->4015t, 1600px->1565t,
1024px->655t, 768px->375t, 512px->175t），分段线性插值。
"""

import os
import io
import sys
import json
import time
import base64

# Windows 下强制 UTF-8 输出，避免 stdio 编码问题
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

os.environ.setdefault("FASTMCP_LOG_LEVEL", "ERROR")

from fastmcp import FastMCP
from PIL import Image, ImageOps

mcp = FastMCP("image-preprocessor")

TASK_RESOLUTIONS = {
    "ocr": 1600,
    "detail": 1024,
    "general": 768,
    "thumbnail": 512,
}

# (最长边, 估算token) 实测采样点
_TOKEN_SAMPLES = [(2559, 4015), (1600, 1565), (1024, 655), (768, 375), (512, 175)]


def estimate_tokens_for_long_edge(edge: int) -> int:
    """根据最长边估算视觉 token 占用（分段线性插值）。"""
    samples = sorted(_TOKEN_SAMPLES, key=lambda p: p[0])
    if edge <= samples[0][0]:
        x0, y0 = samples[0]
        x1, y1 = samples[1]
        return int(y0 + (y1 - y0) * (edge - x0) / (x1 - x0))
    for i in range(len(samples) - 1):
        x0, y0 = samples[i]
        x1, y1 = samples[i + 1]
        if x0 <= edge <= x1:
            return int(y0 + (y1 - y0) * (edge - x0) / (x1 - x0))
    x0, y0 = samples[-2]
    x1, y1 = samples[-1]
    return int(y0 + (y1 - y0) * (edge - x0) / (x1 - x0))


def load_image(path: str) -> Image.Image:
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)  # 修正 EXIF 方向
    return img


def resize_to_long_edge(img: Image.Image, max_edge: int) -> Image.Image:
    w, h = img.size
    longest = max(w, h)
    if longest <= max_edge:
        return img
    scale = max_edge / longest
    new_w = max(1, round(w * scale))
    new_h = max(1, round(h * scale))
    return img.resize((new_w, new_h), Image.LANCZOS)


def save_image(img: Image.Image, out_path: str, fmt: str) -> str:
    if fmt == "jpeg":
        if img.mode in ("RGBA", "LA", "P"):
            bg = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode in ("RGBA", "LA"):
                bg.paste(img, mask=img.split()[-1])
            else:
                bg.paste(img.convert("RGB"))
            img = bg
        else:
            img = img.convert("RGB")
        img.save(out_path, "JPEG", quality=88)
    elif fmt == "webp":
        img.save(out_path, "WEBP", quality=88)
    else:
        img.save(out_path, "PNG")
    return out_path


@mcp.tool()
def prepare_image(
    image_path: str,
    task: str = "general",
    max_resolution: int | None = None,
    output_format: str = "jpeg",
    output_dir: str | None = None,
    return_base64: bool = False,
) -> str:
    """按任务类型自动压缩图片，供本地多模态模型识别，返回处理结果 JSON。

    参数说明：
    - image_path: 图片文件绝对路径（必填）
    - task: 任务类型，控制目标分辨率。ocr=1600px(文字识别), detail=1024px(详细分析), general=768px(一般识别), thumbnail=512px(粗略)
    - max_resolution: 手动指定目标最长边像素，覆盖 task 默认值（可选）
    - output_format: 输出格式 jpeg/webp/png，默认 jpeg
    - output_dir: 输出目录，默认与输入图片同目录
    - return_base64: 是否同时返回 base64 数据（默认 false）
    """
    start = time.time()
    if not image_path or not os.path.isfile(image_path):
        return json.dumps({"ok": False, "error": f"文件不存在: {image_path}"}, ensure_ascii=False)
    task = (task or "general").lower()
    if task not in TASK_RESOLUTIONS:
        task = "general"
    target = max_resolution or TASK_RESOLUTIONS[task]
    try:
        img = load_image(image_path)
    except Exception as e:
        return json.dumps({"ok": False, "error": f"无法打开图片: {e}"}, ensure_ascii=False)
    orig_w, orig_h = img.size
    orig_size = os.path.getsize(image_path)
    new_img = resize_to_long_edge(img, target)
    fmt = pick_output_format(output_format)
    out_dir = output_dir or os.path.dirname(os.path.abspath(image_path)) or "."
    os.makedirs(out_dir, exist_ok=True)
    base, _ = os.path.splitext(os.path.basename(image_path))
    ext = {"jpeg": "jpg", "webp": "webp", "png": "png"}[fmt]
    out_path = os.path.join(out_dir, f"{base}_prep_{task}_{target}px.{ext}")
    save_image(new_img, out_path, fmt)
    new_size = os.path.getsize(out_path)
    new_w, new_h = new_img.size
    est_tokens = estimate_tokens_for_long_edge(max(new_w, new_h))
    elapsed = round(time.time() - start, 3)
    result = {
        "ok": True,
        "task": task,
        "original": {"path": image_path, "width": orig_w, "height": orig_h, "size_bytes": orig_size},
        "output": {"path": out_path, "width": new_w, "height": new_h, "size_bytes": new_size, "format": fmt},
        "estimated_tokens": est_tokens,
        "elapsed_seconds": elapsed,
    }
    if return_base64:
        with open(out_path, "rb") as f:
            result["base64"] = base64.b64encode(f.read()).decode("ascii")
        result["base64_mime"] = "image/jpeg" if fmt == "jpeg" else f"image/{fmt}"
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
def estimate_image_tokens(image_path: str) -> str:
    """估算一张图片在本地视觉模型中的 token 占用，并给出各任务档位的推荐分辨率。"""
    if not image_path or not os.path.isfile(image_path):
        return json.dumps({"ok": False, "error": f"文件不存在: {image_path}"}, ensure_ascii=False)
    try:
        img = load_image(image_path)
    except Exception as e:
        return json.dumps({"ok": False, "error": f"无法打开图片: {e}"}, ensure_ascii=False)
    w, h = img.size
    longest = max(w, h)
    refs = {t: estimate_tokens_for_long_edge(r) for t, r in TASK_RESOLUTIONS.items()}
    return json.dumps({
        "ok": True,
        "width": w,
        "height": h,
        "longest_edge": longest,
        "current_tokens": estimate_tokens_for_long_edge(longest),
        "recommendations": refs,
    }, ensure_ascii=False)


def pick_output_format(fmt: str) -> str:
    fmt = (fmt or "jpeg").lower()
    if fmt not in ("jpeg", "webp", "png"):
        fmt = "jpeg"
    return fmt


if __name__ == "__main__":
    mcp.run()
