'''跳转打开网页，没有什么其他的功能'''

from webbrowser import open
import logging

def jump_javlibrary(serial_number):
    open("https://www.javlibrary.com/cn/vl_searchbyid.php?keyword="+serial_number)
    
def jump_javdb(serial_number):
    open("https://javdb.com/search?q="+serial_number)

def jump_javtxt(serial_number):
    #这个都是简单的跳转，后面要进行快速转到标准的页面上
    open("https://javtxt.com/search?type=id&q="+serial_number)

def jump_missav(serial_number):
    #这个都是简单的跳转，后面要进行快速转到标准的页面上
    open("https://missav.ai/cn/search/"+serial_number)

def jump_minnanoav(actressname):
    open("https://www.minnano-av.com/search_result.php?search_scope=actress&search_word="+actressname+"&search= Go")

def jump_avdanyuwiki(name):
    open("https://avdanyuwiki.com/?s="+name)

def jump_avmoo(serial_number):
    #这个都是简单的跳转，后面要进行快速转到标准的页面上
    open("https://avmoo.website/cn/search/"+serial_number)

def jump_javbus():
    open("https://www.javbus.com/")

def jump_fanza(serial_number):
    '''特点是原始一手资料，但是东西会下架，然后cid特别多'''
    open("https://www.dmm.co.jp")

def jump_mgs(serial_number):
    open("https://www.mgstage.com")

def jump_netflav():
    open("https://netflav.com/")

def jump_jinjier():
    open("https://jinjier.art/")

def jump_123av(serial_number):
    open("https://123av.gg/zh/search?keyword="+serial_number)

def jump_avwiki():
    '''陌生女优信息'''
    open("https://av-wiki.net")

def jump_avdict():
    '''av女优大词典'''
    open("https://av-help.memo.wiki/")

def jump_jable(serial_number):
    open("https://jable.tv/search/"+serial_number+"/")

def jump_supjav(serial_number):
    if serial_number.startswith("FC2-"):
        serial_number=serial_number.split("-")[-1]
    open("https://supjav.com/?s="+serial_number)

def jump_kana():
    open("https://zh.wikipedia.org/wiki/%E7%89%87%E5%81%87%E5%90%8D")

def jump_gana():
    open("https://zh.wikipedia.org/wiki/%E5%B9%B3%E5%81%87%E5%90%8D")


def send_navigate_request(url: str):
    import requests
    try:
        # 发送导航指令到本地服务器
        response = requests.post("http://localhost:56789/api/v1/navigate", json={
            "url": url,
            "target": "new_tab"
        }, timeout=2)
        
        if response.status_code == 200:
            return True
        else:
            return False
    except Exception as e:
        logging.error(f"发送到本地浏览器跳转指令失败: {e}")
        return False

def send_crawler_request(web:str,serial_number:str):
    '''发送爬取指令到本地服务器，由，本地服务器去指挥浏览器插件
    web:javlib,javdb
    '''
    import requests
    try:
        # 发送导航指令到本地服务器
        response = requests.post("http://localhost:56789/api/v1/startcrawler", json={
            "web": web,
            "serial_number": serial_number
        }, timeout=2)
        if response.status_code == 200:
            return True
        else:
            return False
    except Exception as e:
        logging.error(f"发送到本地浏览器跳转指令失败: {e}")
        return False