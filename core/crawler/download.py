import requests
import sqlite3,logging
from config import DATABASE
from .javtxt import fetch_javtxt_movie_info
import time
import random
from core.database.update import update_titlestory

def download_image(url, save_path)->tuple[bool,str]:
    '''下载图片'''
    try:
        # 发送 HTTP GET 请求
        response = requests.get(url, stream=True,timeout=10)
        response.raise_for_status()  # 检查请求是否成功
        
        # 以二进制写入模式打开文件
        with open(save_path, 'wb') as file:
            for chunk in response.iter_content(1024):
                file.write(chunk)
        print(f"图片已保存到: {save_path}")
        return True,"成功下载"
    except Exception as e:
        print(f"下载图片失败: {e}")
        return False,str(e)

def download_image_with_retry(
    url,
    save_path,
    *,
    timeout_s: float = 10,
    retries: int = 0,#最多一次重复请求，下载图片
    backoff_base_s: float = 0.6,
)->tuple[bool,str]:
    '''下载图片'''
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    }

    last_err: Exception | None = None
    for attempt in range(max(0, retries) + 1):
        try:
            response = requests.get(url, stream=True, timeout=timeout_s, headers=headers)
            response.raise_for_status()

            with open(save_path, 'wb') as file:
                for chunk in response.iter_content(1024):
                    if chunk:
                        file.write(chunk)

            print(f"图片已保存到: {save_path}")
            return True, "成功下载"
        except Exception as e:
            last_err = e
            logging.warning(
                "下载图片失败 attempt=%s/%s url=%s err=%s",
                attempt + 1,
                max(0, retries) + 1,
                url,
                repr(e),
            )
            # 失败时尽量清理半成品文件
            try:
                import os
                if os.path.exists(save_path):
                    os.remove(save_path)
            except Exception as rm_exc:
                logging.debug(
                    "下载失败后清理半成品文件失败 path=%s: %s",
                    save_path,
                    rm_exc,
                    exc_info=True,
                )

            if attempt < max(0, retries):
                time.sleep(backoff_base_s * (2 ** attempt) + random.uniform(0.0, 0.2))

    print(f"下载图片失败: {last_err}")
    return False, str(last_err) if last_err is not None else "Unknown Error"

def update_title_story_db():
    '''更新整个数据库中的story'''

    query = f'''
        SELECT serial_number
        FROM work
        WHERE jp_title is NULL
        '''
    with sqlite3.connect(DATABASE) as conn:
        #返回所有需要更新的番号
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        serial_number_list=[row[0] for row in rows]
    
    for serial_number in serial_number_list:
        print(serial_number)
        data=fetch_javtxt_movie_info(serial_number)
        if data is not None:
            update_titlestory(serial_number,data["cn_title"],data["jp_title"],data["cn_story"],data["jp_story"])
        time.sleep(random.uniform(8, 15))

    