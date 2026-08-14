# image-preprocessor MCP Server

图片预处理 MCP Server：在调用本地多模态模型识别图片前，自动按任务类型压缩图片分辨率，
避免高清原图占满上下文窗口导致输出截断。

## 功能

- `prepare_image`：按任务类型自动压缩图片，返回处理后的图片路径、尺寸、估算 token 占用
- `estimate_image_tokens`：估算一张图片的 token 占用，并给出各任务档位的推荐分辨率

## 任务类型 -> 目标分辨率

| 任务 | 目标最长边 | 估算 token | 适用场景 |
|------|-----------|-----------|---------|
| `ocr` | 1600px | ~1565 | 文字识别、表格提取、数据读取 |
| `detail` | 1024px | ~655 | 详细描述、视觉问答、内容分析 |
| `general` | 768px | ~375 | 一般识别、分类、摘要 |
| `thumbnail` | 512px | ~175 | 粗略预览、批量扫描、快速判断 |

token 估算基于 qwen3.5:9b 实测数据（2559px->4015t, 1600px->1565t, 1024px->655t, 768px->375t, 512px->175t），分段线性插值。

## 环境要求

- Python 3.10+
- 依赖：`pip install -r requirements.txt`（fastmcp、pillow）

## 接入 MCP 配置

在 TraeWork / 客户端的 MCP 配置文件中添加：

```json
{
  "mcpServers": {
    "image-preprocessor": {
      "command": "E:\\应用\\Python314\\python.exe",
      "args": ["C:\\Users\\beimi\\mcp-servers\\image-preprocessor\\server.py"]
    }
  }
}
```

## 使用示例（工具调用）

```json
{"image_path": "C:\\Users\\me\\Pictures\\screenshot.png", "task": "ocr"}
{"image_path": "C:\\Users\\me\\Pictures\\photo.jpg", "task": "detail", "return_base64": true}
{"image_path": "C:\\Users\\me\\Pictures\\scan.png", "task": "ocr", "max_resolution": 1200, "output_format": "webp"}
```

## 本地测试

```bash
python test_local.py       # 功能测试（生成测试图，验证各档位）
python test_mcp_client.py  # MCP 协议测试（stdio 客户端真实调用）
```

## 设计要点

- 按最长边等比缩放（LANCZOIS 高质量插值），自动修正 EXIF 方向
- 透明图片转 JPEG 时自动垫白底
- 输出格式支持 jpeg / webp / png，默认 jpeg（质量 88）
- 输出文件命名：`{原名}_prep_{task}_{target}px.{ext}`
- 支持 `return_base64` 直接返回 base64 数据（配合 OpenAI 兼容接口的 image_url 使用）
