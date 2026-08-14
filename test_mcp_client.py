# -*- coding: utf-8 -*-
"""通过 MCP 客户端协议（stdio）真实调用 server，验证 MCP 集成。"""
import asyncio
import json
import os

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER_PY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "server.py")
TEST_IMG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_test", "test_source.png")


async def main():
    params = StdioServerParameters(
        command=r"E:\应用\Python314\python.exe",
        args=[SERVER_PY],
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print("=== MCP tools ===")
            for t in tools.tools:
                print(f"  - {t.name}: {t.description.splitlines()[0] if t.description else ''}")

            res = await session.call_tool("prepare_image", {"image_path": TEST_IMG, "task": "ocr", "output_dir": os.path.dirname(TEST_IMG)})
            print("\n=== prepare_image(ocr) result ===")
            print(res.content[0].text[:400])

            res2 = await session.call_tool("estimate_image_tokens", {"image_path": TEST_IMG})
            print("\n=== estimate_image_tokens result ===")
            print(res2.content[0].text[:400])
            print("\nMCP CLIENT TEST PASSED")


if __name__ == "__main__":
    asyncio.run(main())
