"""
手动请求 GET /api/v1/work/{serial_number}。

先启动 Darkeye；若 Firefox 插件已连 /events，会等待合并结果（可能较久，默认超时 130s）。
无插件时通常返回 503。

用法::

    python manual_tests/test_work_merge_api.py
    python manual_tests/test_work_merge_api.py --base-url http://127.0.0.1:56789

固定测试番号：
IPZZ-317
012318-589
AVOP-127
IBW-491
SMD-180
HXAD-015
STARS-260
ABF-017      这个很特殊，网站上有错误
"""




from __future__ import annotations

import argparse
import json
import sys
from urllib.parse import quote

import requests

DEFAULT_BASE = "http://127.0.0.1:56789"
TIMEOUT = 130
SERIAL = "IPZZ-317"


def main() -> int:
    p = argparse.ArgumentParser(description="GET /api/v1/work/{serial_number}")
    p.add_argument("--base-url", default=DEFAULT_BASE, help="API 根地址")
    p.add_argument(
        "--timeout",
        type=float,
        default=TIMEOUT,
        help=f"请求超时秒数（默认 {TIMEOUT}）",
    )
    args = p.parse_args()
    base = args.base_url.rstrip("/")
    url = f"{base}/api/v1/work/{quote(SERIAL, safe='')}"

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
