各家网站，怎么说呢，实际上只要爬聚合站就行了，  
fanza上下架的作品，在其他的新的网站上也是没有作品的，比如javtxt


| 网站名                                       | 已爬取     | 数据    | 特点                                   |
| ----------------------------------------- | ------- | ----- | ------------------------------------ |
| [fanza](https://www.dmm.co.jp)            | 未使用     | 数据+视频 | 一手数据，缺点会下架片子，以及网络访问问题                |
| mgstage                                   | 未使用     | 数据+视频 | 一手数据，缺点会下架片子，以及网络访问问题,素人企划，SIRO      |
| [prestige](https://www.prestige-av.com/)                                  | 未使用     | 数据    | 蚊香社一手数据，缺点会下架片子，以及网络访问问题              |
| [fc2](https://video.fc2.com/)             | 未使用     | 数据    | 一手数据，缺点会下架片子，以及网络访问问题                |
| [avdanyuwiki](https://avdanyuwiki.com)    | 使用      | 数据+男优 | 男优数据，片子比fanza多，sod的封面不正规             |
| [minnanoav](https://www.minnano-av.com/)  | 使用      | 女优数据  | 女优数据，没有片子数据                          |
| [javdb](https://javdb.com)                | 使用      | 数据+视频 | 最全，各种FC2非正规数据的都有，封面有水印，不要其图片         |
| [javlibrary](https://www.javlibrary.com/) | 使用      | 数据    | 数据年代最久远                              |
| [javtxt](https://javtxt.com)              | 使用标题与故事 | 数据    | 年代新，基本上fanza没有的数据这里也没有，没有封面，但是有中日的故事 |
| [missav](https://missav.ai/)              | 使用图片    | 视频站   | 只用来补充下载封面数据                          |
| [avwiki](https://av-wiki.net/)            | 未使用     | 数据    | 好像有冷门数据                              |
| [AV女優大辞典wiki](https://av-help.memo.wiki/) | 未使用     | 数据    | 日本网站这个好像比较新，而且比较活跃                   |
| [avbase](https://www.avbase.net/)         | 未使用     | 数据    | 日本网站这个好像比较新，而且比较活跃                       |
| javbus                                    | 未使用     | 视频    | 这个基本不用，                              |
| avmoo                                     | 未使用     | 视频    | 这个基本不用，和javbus长的很像                   |


我只要做好fanza,avdanyuwiki,minnanoav,javdb,javlib,javtxt爬取就行了，其他的不需要，保证每种要素有两个备用来源就行了

采集优先日本网站，反爬力度低，信息准，不会涉及到翻译问题

番号 fanza,mgs,avdanyuwiki,javlib
发布日期 fanza,mgs,avdanyuwiki,javlib
导演 fanza,mgs,avdanyuwiki,javlib
时长 fanza,mgs,avdanyuwiki,javlib
制作商 fanza,mgs,avdanyuwiki,javlib
厂牌 fanza,mgs,avdanyuwiki,javlib

标签 fanza,mgs,avdanyuwiki,javlib

标题 fanza,mgs,javtxt
故事 fanza,mgs,javtxt

封面 fanza,mgs,javlib,missav
女优 fanza,mgs,avdanyuwiki,javlib
男优 avdanyuwiki

女优信息 minnanoav
男优信息 无来源



## 爬虫架构

现在把爬虫全放浏览器插件里，目前的合并不涉及到复杂的验证只是单纯的优先级

包装成同步接口

大概是这样的接口
```
GET /v1/work/{serial_number}
```

```
GET /v1/actress/{actress_jp_name}
```

然后里面全都是文本，包括标签也是文本，图片都是地址或者地址列表，后面需要时下载



python暴露接口下载图片的,输入一个图片的
```
def download_image_js(url, save_path) -> tuple[bool, str]:
```


爬虫的队列控制在python侧，显示队列的进度，可以增加修改，暂停队列，然后可以插队，新添加的

然后包括是写入数据库还是显示在GUI，各种校验，添加新男女优的动作


### 浏览器端

多请求，创建后active

然后聚合到一个Js里面，然后合并，然后返回数据


还有叠加网络不稳定
对于每个网站的策略都不一样的
javdb这个会有反爬，然后封IP，不要用香港的IP，流程是先查，然后跳转到详情页后抓，查可能没有东西，或者番号对不上。

javlib这个第一次100%触发cloudflare反爬，爬的多了就是点击盾，然后要么就是卡在反爬那里。可能直接跳到详情页，也有可能显示查不到结果，或者查到结果后但是没有匹配的，或者查到结果后有两个，不要蓝光的那个。这个也会加载fanza。实际上不需要等fanza加载好就可以抓数据了

javtxt这个网站好像会有反爬，至少裸的request请求是不行的，流程是先查，也有可能查不到，然后然后进详情页，然后这个详情页可能会没有。目前对于反爬的结果似乎就是没有反应。

avdanyuwiki,这个网站的反爬似乎就是不给东西，这个网站反应很慢，要加载fanza，在写爬虫的时候要注意，不要等fanza加载好了就可以去抓数据里。目前对于反爬的结果就是没有反应

fanza 这个网站能否访问都是一个谜。理论上非日本IP是无法访问的

minnao-av的问题还是会有加载不出来的问题。