import os
import sys
import uuid
import requests
from pathlib import Path
from urllib.parse import quote, urljoin

# ====== 改这里 ======
BASE_URL = "https://dav.jianguoyun.com/dav/"   # 坚果云 WebDAV 地址
USERNAME = "909510519@qq.com"                      # 不是登录邮箱，填 WebDAV 应用用户名
PASSWORD = "a9qcx52fsjgjinxm"                        # WebDAV 应用密码
REMOTE_ROOT = "/"                        # 远端根目录
TIMEOUT = 20
# ====================


def norm_path(p: str) -> str:
    p = (p or "").replace("\\", "/").strip()
    return "/" + p.strip("/")


def build_url(remote_path: str) -> str:
    merged = f"{norm_path(REMOTE_ROOT).rstrip('/')}/{norm_path(remote_path).lstrip('/')}"
    encoded = quote(merged, safe="/-_.~")
    return urljoin(BASE_URL.rstrip("/") + "/", encoded.lstrip("/"))


def req(session: requests.Session, method: str, remote_path: str, **kwargs):
    url = build_url(remote_path)
    return session.request(method, url, timeout=TIMEOUT, **kwargs)


def main():
    s = requests.Session()
    s.auth = (USERNAME, PASSWORD)

    print("1) PROPFIND 根目录连通性...")
    r = req(s, "PROPFIND", "/", headers={"Depth": "0"})
    print("   status:", r.status_code)
    if r.status_code not in (200, 207):
        print("   失败：请检查 BASE_URL / 用户名 / 密码")
        sys.exit(1)

    test_dir = f"/_dav_test_{uuid.uuid4().hex[:8]}"
    test_file = f"{test_dir}/hello.txt"

    print("2) MKCOL 创建测试目录:", test_dir)
    r = req(s, "MKCOL", test_dir)
    print("   status:", r.status_code)
    if r.status_code not in (201, 301, 405):  # 405: 已存在
        print("   创建目录失败")
        sys.exit(1)

    print("3) PUT 上传测试文件:", test_file)
    data = b"hello webdav from darkeye"
    r = req(s, "PUT", test_file, data=data)
    print("   status:", r.status_code)
    if r.status_code not in (200, 201, 204):
        print("   上传失败")
        sys.exit(1)

    print("4) GET 下载并校验...")
    r = req(s, "GET", test_file)
    print("   status:", r.status_code)
    if r.status_code != 200 or r.content != data:
        print("   下载或内容校验失败")
        sys.exit(1)

    print("5) DELETE 清理文件和目录...")
    r1 = req(s, "DELETE", test_file)
    r2 = req(s, "DELETE", test_dir)
    print("   delete file status:", r1.status_code)
    print("   delete dir  status:", r2.status_code)

    print("\n✅ WebDAV 基本读写链路正常。")


if __name__ == "__main__":
    main()