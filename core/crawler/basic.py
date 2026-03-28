import requests
from requests.exceptions import RequestException, Timeout, ConnectionError, HTTPError


def fetch_url(url, headers=None, timeout=10):
    """
    安全请求 URL，捕获所有网络异常并返回 False
    """
    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=timeout,  # 关键：设置超时，避免无限等待
            allow_redirects=True,  # 允许重定向
            verify=True,  # SSL 验证（可设为 False 如果证书问题，但不推荐）
        )
        # 可选：检查 HTTP 状态码
        response.raise_for_status()  # 如果 4xx/5xx 会抛出 HTTPError

        return response  # 成功返回 response 对象

    except Timeout:
        print(f"[超时] {url}")
        return False

    except ConnectionError as e:
        # 包括 ConnectionAbortedError、连接拒绝等
        print(f"[连接错误] {url} - {e}")
        return False

    except HTTPError as e:
        print(f"[HTTP错误] {url} - {response.status_code}")
        return False

    except RequestException as e:
        # 捕获所有 requests 相关的异常（最广义的网）
        print(f"[请求异常] {url} - {e}")
        return False

    except Exception as e:
        # 万一还有其他意外异常
        print(f"[未知错误] {url} - {e}")
        return False
