# DarkEye - 在暗黑界睜開一隻眼

[![README · 简体中文](https://img.shields.io/badge/README%20%C2%B7%20%E7%AE%80%E4%BD%93%E4%B8%AD%E6%96%87-555555?style=for-the-badge)](README.md)
[![README · 繁體中文](https://img.shields.io/badge/README%20%C2%B7%20%E7%B9%81%E9%AB%94%E4%B8%AD%E6%96%87%EF%BC%88%E8%87%BA%E7%81%A3%EF%BC%89-2ea44f?style=for-the-badge)](README.zh-TW.md)
[![README · 日本語](https://img.shields.io/badge/README%20%C2%B7%20%E6%97%A5%E6%9C%AC%E8%AA%9E-555555?style=for-the-badge)](README.ja.md)

> 一款完全在本機、注重隱私的成人影片收藏與管理工具，支援瀏覽器外掛沉浸式採集與擬物化 DVD 陳列。基於 PySide6 / Qt Quick 3D、SQLite、本機 FastAPI 與瀏覽器擴充功能協同，並含 C++ 力導向圖加速；集採集、整理、分析與視覺化於一體。

- **資料與連線**：預設資料在程式旁的 `data/`（資料庫、設定、封面與頭像等，可在設定中調整路徑）。不會向第三方上傳你的片庫；連線主要來自爬蟲與資源拉取，以及選用的更新檢查（GitHub Releases）、翻譯（Google 或你自備的 LLM API）等。

![Python](https://img.shields.io/badge/Python-3.13-blue.svg)
![Framework](https://img.shields.io/badge/framework-PySide6%20(Qt6)-orange)
![Platform](https://img.shields.io/badge/Platform-Windows-blue)
![License](https://img.shields.io/github/license/de4321/darkeye)
![GitHub last commit](https://img.shields.io/github/last-commit/de4321/darkeye)
![GitHub release](https://img.shields.io/github/v/release/de4321/darkeye)
![GitHub Repo stars](https://img.shields.io/github/stars/de4321/darkeye?style=social)
![GitHub all releases](https://img.shields.io/github/downloads/de4321/darkeye/total)

[📖 線上文件](https://de4321.github.io/darkeye/)
[🎥 影片介紹](https://youtu.be/VCsw1D0ccgY?si=e9typx4kPnzaVFZq)
[🌐 官網](https://de4321.github.io/darkeye-webpage/)
[💬 Discord](https://discord.gg/3thnEguWUk)

# 💡 快速開始
## 下載
[![下載 Windows 版本](https://img.shields.io/badge/%20下載-Windows%20-blue?style=for-the-badge&logo=windows)](https://github.com/de4321/darkeye/releases/download/v1.2.3/DarkEye-v1.2.3.zip)
下載程式，解壓，開啟exe即可使用。外掛隨著軟體附帶在目錄下面`extensions`資料夾內。可以不下載下面的選項。

[![下載Chrome/Edge外掛](https://img.shields.io/badge/%20下載-Chrome/Edge外掛%20-blue?style=for-the-badge)](https://github.com/de4321/darkeye/releases/download/v1.2.3/chrome_capture.zip)按照下面的外掛安裝，否則爬蟲收集功能將不可用。外掛選擇自己的瀏覽器，只下載對應的一個就行了。

[![下載FireFox外掛](https://img.shields.io/badge/%20下載-Firefox外掛%20-blue?style=for-the-badge)](https://github.com/de4321/darkeye/releases/download/v1.2.3/firefox_capture.zip)按照下面的外掛安裝，否則爬蟲收集功能將不可用。外掛選擇自己的瀏覽器，只下載對應的一個就行了。

## 外掛安裝
👉 https://de4321.github.io/darkeye/usage/#_2

## 使用
👉 https://de4321.github.io/darkeye/usage/#_3

## 版本遷移
👉 https://de4321.github.io/darkeye/faq/

現在正常情況下在設定裡點選自動更新就行了，但是這個只更新了軟體的本體，外掛還是要手動去下載更新的。目前似乎找不到一種更好的更新外掛的方式，主要是這個外掛上架不了市場。

版本遷移時注意`更新瀏覽器外掛`，由於爬蟲的特殊性，這個爬蟲很可能老失效。需要反饋然後人工修改。

## Jvedio遷移資料
👉 https://de4321.github.io/darkeye/usage/#jvedio

# 社群

有問題或想法？歡迎加入 Discord 社群交流：https://discord.gg/3thnEguWUk

- 新手支持
文件閱讀中若有疑問，歡迎提問；線上文件仍在持續完善中。

- 提前知道進展
“新功能、開發進展、預釋出版本會先在 Discord 討論”

- 參與方向討論
“想影響 roadmap，可以來參與討論”

# 參考專案

- [mdcz](https://github.com/ShotHeadman/mdcz) 參考其中從本地影片名字中提取番號的程式碼，並且嘗試去適配其nfo
- [Jvedio](https://github.com/hitchao/Jvedio) 接入其資料庫，將資料匯出
- [JavSP](https://github.com/Yuukiy/JavSP) 看看某些網站的爬蟲邏輯
- [JAV-JHS](https://sleazyfork.org/zh-CN/scripts/558525-jav-jhs) 參考其javdb FC2 資訊


# 🚀 開發方向
- 1.0 基礎工具的完善，包括力導向圖探索影片之間的關係，收藏體驗的增強
- 2.0 UGC，分散式同步資料
- 3.0 機器學習推薦演算法

## 特性
- [x] 影片，女優，男優，標籤的手動新增，增刪查改，部分爬蟲
- [x] 自慰，做愛，晨勃記錄的手動新增，增刪查改
- [x] 分析圖表,資料展示,還有部分未完成
- [x] 擬物化dvd展示
- [x] 篩選作品頁面
- [x] chrome/edge/firefox爬蟲外掛，沉浸式摘取資訊，支援javtxt,javlib,javdb互動式採集資訊，
- [x] 多鏈路爬蟲，主要使用javlib,avdanyuwiki,javtxt,javdb,minnano-av,對於正規片的爬取很有效，且易過盾。
- [x] 力導向圖，檢視關聯，承受1w節點60幀率
- [x] 搜尋本地影片，進入爬蟲列表
- [x] 備份系統，按私庫重建喜歡的番號
- [x] json驅動外鏈跳轉，可自定義。
- [x] 主題更改，剩下3D場景沒有更改明亮黑暗
- [x] 部分截圖功能，女優介面C鍵截圖
- [x] NFO資料匯入(測試中)
- [x] Jvedio資料匯出NFO(測試中)
- [ ] NFO資料匯出(形成共識後開發)
- [x] 自動檢測下載更新
- [x] LLM翻譯+一鍵覆蓋翻譯



擬物化的dvd
![收藏](docs/assets/dvd.jpg)
![展開](docs/assets/dvd2.jpg)
![女優](docs/assets/actress.jpg)

圖譜發現關係
![力導向圖](docs/assets/directforceview.jpg)
分析研究資料
![圖表](docs/assets/chart.jpg)
![多作品](docs/assets/mutiwork.jpg)
![編輯介面](docs/assets/edit.jpg)

下面以javtxt為例展示爬蟲外掛，開啟外掛後，會與本地互動，可點選新增，自動啟動爬蟲爬取資訊到本地，另外支援javlib與javdb。注意下面的這個中間的收藏與收錄在網站上是沒有的，只有開啟外掛與本地軟體後才會出現。
![javtxt網站為例](docs/assets/capture.JPG)

## 爬蟲
目前爬蟲對於作品只爬取釋出時間，導演，中日文標題與劇情，女優，男優(如果有)，標籤，封面圖片，影片長度，製作商，廠牌，系列，劇照等資訊。

對女優資訊的爬取只爬頭像，生日，出道日，三維，身高罩杯，與曾用名，目前沒有曾用名的更新機制。會有一個問題，如果一開始用的日文名是曾用名，則會有問題。

測試下來第一次爬蟲一定觸發javlib盾，然後基本上爬100次會遇到javdb的點選盾，互動點掉就行了。

軟體不解決代理問題，目標網站能用瀏覽器開啟就是能爬。


# 🚀 開發
👉 請訪問：https://de4321.github.io/darkeye/development/


# 📚 文件
👉 完整文件請訪問：https://de4321.github.io/darkeye/



