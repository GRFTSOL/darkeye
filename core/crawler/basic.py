import requests
from requests.exceptions import RequestException, Timeout, ConnectionError, HTTPError

import requests


#这个好像没有什么用，遇到clould我去浏览器插件里爬
class Request:
    def __init__(self, use_scraper=True, timeout=30, proxy=None):
        """
        Args:
            use_scraper (bool): 是否启用 cloudscraper 绕过 CloudFlare
            timeout (int): 请求超时时间
            proxy (str): 代理地址 (e.g., 'http://127.0.0.1:7890')
        """
        import cloudscraper
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
        }
        self.cookies = {}
        self.proxies = {'http': proxy, 'https': proxy} if proxy else {}
        self.timeout = timeout

        if not use_scraper:
            self.scraper = None
            self._get_impl = requests.get
        else:
            self.scraper = cloudscraper.create_scraper()
            self._get_impl = self._scraper_monitor(self.scraper.get)

    def _scraper_monitor(self, func):
        """监控 cloudscraper，失败时降级回 requests"""
        def wrapper(*args, **kw):
            try:
                return func(*args, **kw)
            except Exception as e:
                print(f"CloudFlare 绕过失败: {e}, 降级使用普通 requests")
                # 如果是 get 请求则降级
                if func == self.scraper.get:
                    return requests.get(*args, **kw)
                raise e
        return wrapper

    def get(self, url, **kwargs):
        """发送 GET 请求"""
        # 合并参数，kwargs 允许覆盖默认设置
        request_kwargs = {
            'headers': self.headers,
            'proxies': self.proxies,
            'cookies': self.cookies,
            'timeout': self.timeout
        }
        request_kwargs.update(kwargs)
        
        response = self._get_impl(url, **request_kwargs)
        return response



def fetch_url(url, headers=None, timeout=10):
    """
    安全请求 URL，捕获所有网络异常并返回 False
    """
    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=timeout,           # 关键：设置超时，避免无限等待
            allow_redirects=True,      # 允许重定向
            verify=True                # SSL 验证（可设为 False 如果证书问题，但不推荐）
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