"""
手动请求 GET /api/v1/actress/{actress_jp_name}。

先启动 Darkeye；若 Firefox 插件已连 /events，会等待 minnano 采集（默认超时 130s）。
无插件时通常返回 503。

用法::

    python manual_tests/test_actress_api.py
    python manual_tests/test_actress_api.py --name YOUR_JP_NAME
    python manual_tests/test_actress_api.py --base-url http://127.0.0.1:56789
"""

from __future__ import annotations

import argparse
import json
import sys
from urllib.parse import quote

import requests

DEFAULT_BASE = "http://127.0.0.1:56789"
TIMEOUT = 130
# 默认示例名（三上 + 悠 + 亚），避免部分编辑器编码导致字面量乱码
DEFAULT_NAME = "\u4e09\u4e0a\u60a0\u4e9c"

"""
橋本ありな 
八掛うみ
桃谷エリカ
水トさくら
miru
"""

def main() -> int:
    p = argparse.ArgumentParser(description="GET /api/v1/actress/{actress_jp_name}")
    p.add_argument("--base-url", default=DEFAULT_BASE, help="API 根地址")
    p.add_argument("--name", default=DEFAULT_NAME, help="日文女优名")
    p.add_argument(
        "--timeout",
        type=float,
        default=TIMEOUT,
        help=f"请求超时秒数（默认 {TIMEOUT}）",
    )
    args = p.parse_args()
    base = args.base_url.rstrip("/")
    url = f"{base}/api/v1/actress/{quote(args.name, safe='')}"

    print(f"GET {url}")
    try:
        r = requests.get(url, timeout=args.timeout)
    except OSError as e:
        print(f"请求失败: {e}")
        return 1

    print(f"HTTP {r.status_code}")
    try:
        print(json.dumps(r.json(), ensure_ascii=False, indent=2))
    except Exception:
        print(r.text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
