<div align="center">
  <a href="https://de4321.github.io/darkeye-webpage/" target="_blank">
    <img src="https://raw.githubusercontent.com/de4321/darkeye/main/resources/icons/logo.svg" alt="DarkEye" width="128" />
  </a>
  <h1>DarkEye</h1>
  <p><strong>在暗黑界睜開一隻眼</strong></p>
  <p>一款完全在本機、注重隱私的日本成人影片收藏與管理工具，支援瀏覽器外掛沉浸式採集與擬物化 DVD 盒子陳列。集採集、整理、分析與視覺化於一體。</p>
  <br />

[![README · 简体中文][badge-readme-zh-CN]](README.md)
[![README · 繁體中文][badge-readme-zh-TW]](README.zh-TW.md)
[![README · 日本語][badge-readme-ja]](README.ja.md)

![Python][badge-python]
![Framework][badge-framework]
![Platform][badge-platform]
![License][badge-license]
![GitHub last commit][badge-last-commit]
![GitHub release][badge-release]
![GitHub Repo stars][badge-stars]
![GitHub all releases][badge-downloads]

<br />

[📖 線上文件][link-docs]
[🎥 影片介紹][link-video]
[🌐 官網][link-website]
[💬 Discord][link-discord]

</div>

<p align="center">
  <a href="#download">下載與使用</a> •
  <a href="#features">特性</a> •
  <a href="#screenshots">介面預覽</a> •
  <a href="#privacy">隱私與資料</a> •
  <a href="#migration">遷移與匯入</a> •
  <a href="#crawler">爬蟲說明</a> •
  <a href="#development">開發</a> •
  <a href="#community">社群</a> •
  <a href="#references">參考專案</a>
</p>

<div align="center">
  <a href="https://github.com/de4321/darkeye/releases" target="_blank">
    <img src="./docs/assets/show.jpg" alt="DarkEye 擬物化 DVD 陳列" width="100%" />
  </a>
</div>


---

<a id="download"></a>

## 下載與使用

<div align="center">
  <a href="https://github.com/de4321/darkeye/releases/download/v1.2.4/DarkEye-v1.2.4.zip">
    <img src="https://img.shields.io/badge/%E4%B8%8B%E8%BC%89-Windows-blue?style=for-the-badge&logo=windows" alt="下載 Windows 版本" />
  </a>
</div>

下載程式並解壓，執行 exe 即可；瀏覽器擴充功能隨軟體附帶在 `extensions` 目錄內，一般情況下無需額外下載外掛。若需爬蟲採集，請依下方文件安裝**對應瀏覽器的一種**外掛。

除非外掛單獨更新，一般**不需要**單獨下載外掛。
<div align="center">
  <a href="https://github.com/de4321/darkeye/releases/download/v1.2.4/chrome_capture.zip">
    <img src="https://img.shields.io/badge/%E4%B8%8B%E8%BC%89-Chrome%2FEdge%20%E5%A4%96%E6%8E%9B-blue?style=for-the-badge" alt="下載 Chrome/Edge 外掛" />
  </a>
  　　
  <a href="https://github.com/de4321/darkeye/releases/download/v1.2.4/firefox_capture.zip">
    <img src="https://img.shields.io/badge/%E4%B8%8B%E8%BC%89-Firefox%20%E5%A4%96%E6%8E%9B-blue?style=for-the-badge" alt="下載 Firefox 外掛" />
  </a>
</div>

### 外掛安裝

👉 [線上文件：外掛安裝](https://de4321.github.io/darkeye/usage/#_2)

### 使用說明

👉 [線上文件：使用](https://de4321.github.io/darkeye/usage/#_3)

### 版本與更新

👉 [常見問題：更新與遷移](https://de4321.github.io/darkeye/faq/)

設定中可自動更新**軟體本體**；瀏覽器擴充因無法上架商店，但是**外掛**會在軟體 `extensions` 目錄更新，需要**手動在瀏覽器重新載入**。外掛另可在 [Releases][link-releases] 手動下載。遷移版本時請留意**更新瀏覽器外掛**；爬蟲易隨站台策略失效，需回饋後人工維護。軟體不解決代理問題——目標站台能在瀏覽器開啟，一般即可爬取。

---

<a id="features"></a>

## 特性

### 已實現

| **功能** | **說明** | **狀態** |
| -------- | -------- | -------- |
| **數據管理** | 影片、女優、男優、標籤的手動新增與增刪查改；部分爬蟲輔助 | ✅ |
| **私人資料記錄** | 自慰、做愛、晨勃記錄的手動新增與增刪查改 | ✅ |
| **分析與圖表** | 分析圖表與資料展示（仍有部分未完成功能） | ✅ |
| **擬物化 DVD 盒子陳列** | 擬物化 DVD 陳列與收藏體驗 | ✅ |
| **篩選過濾展示** | 篩選作品頁面 | ✅ |
| **瀏覽器擴充** | Chrome / Edge / Firefox 外掛沉浸式摘取；支援 javtxt、javlib、javdb 等互動式採集 | ✅ |
| **多鏈路爬蟲** | javlib、avdanyuwiki、javtxt、javdb、minnano-av 等；正規片源爬取較有效，且易過盾 | ✅ |
| **關聯圖譜** | 檢視關聯；約 1 萬節點下約 60 幀 | ✅ |
| **翻譯** | LLM 翻譯 + 一鍵覆蓋翻譯 | ✅ |
| **mdcz NFO 匯入** | [mdcz](https://github.com/ShotHeadman/mdcz) 刮削 NFO 匯入 | ✅ |
| **Jvedio NFO 匯入** | Jvedio 資料匯出 NFO（測試中） | ✅ |
| **外鏈跳轉** | JSON 驅動外鏈跳轉外部網站，可自定義 | ✅ |
| **本機影片連結** | 若本機已有影片，可將影片連結到資料庫 | ✅ |
| **備份** | 備份系統，按私庫重建喜歡的番號 | ✅ |
| **主題** | 主題切換（3D 場景尚不完全跟隨明／暗） | ✅ |
| **截圖** | 部分截圖能力；女優介面 `C` 鍵截圖 | ✅ |
| **自動更新** | 自動檢測並下載更新 | ✅ |


### 計劃與推進中

| **功能** | **說明** | **狀態** |
| -------- | -------- | -------- |
| **NFO 匯出** | 形成共識後開發；各工具實作不一，目前資料欄位仍不齊 | 🔄 |

---

<a id="migration"></a>

## 遷移與匯入

### mdcz 專案 NFO 匯入

已支援 [mdcz](https://github.com/ShotHeadman/mdcz) 刮削產出的 NFO 匯入。

👉 [線上文件：mdcz NFO](https://de4321.github.io/darkeye/usage/#mdcz-nfo)

### Jvedio 遷移資料

👉 [線上文件：Jvedio](https://de4321.github.io/darkeye/usage/#jvedio)

---

<a id="privacy"></a>

## 隱私與資料

- **資料與連線**：預設資料在程式旁的 `data/`（資料庫、設定、封面與頭像等，可在設定中調整路徑）。不會向第三方上傳你的片庫；連線主要來自爬蟲與資源拉取，以及選用的更新檢查（Cloudflare R2）、翻譯（Google 或你自備的 LLM API）等。


---

<a id="screenshots"></a>

## 介面預覽

### 擬物化 DVD

![收藏](docs/assets/dvd.jpg)

![展開](docs/assets/dvd2.jpg)

![女優](docs/assets/actress.jpg)

### 力導向圖

![力導向圖](docs/assets/directforceview.jpg)

### 分析圖表

![圖表](docs/assets/chart.jpg)

### 瀑布流

![多作品](docs/assets/mutiwork.jpg)

### 作品編輯

![編輯介面](docs/assets/edit.jpg)

### 瀏覽器外掛（以 javtxt 為例）

開啟外掛後與本機互動，可點選新增並自動觸發爬蟲寫入本機，另支援 javlib、javdb。介面中的「收藏／收錄」等能力僅在連線本機軟體時可用。

![javtxt 網站為例](docs/assets/capture.JPG)

---

<a id="crawler"></a>

## 爬蟲說明

目前爬蟲對作品會盡力取得：釋出時間、導演、中日文標題與劇情、女優、男優（若有）、標籤、封面、片長、製作商、廠牌、系列、劇照等。

對女優資訊主要取得：頭像、生日、出道日、三維、身高罩杯、曾用名（尚無曾用名更新機制；若初始使用曾用名可能導致資料問題）。

首次爬取往往會觸發 javlib 盾；約百次量級可能遇到 javdb 點選盾，依頁面提示操作即可。

目前爬取的主要網站是 javdb、javlibrary、javtxt、avdanyuwiki、minnao-av


---

<a id="development"></a>

## 開發

基於 PySide6 / Qt Quick 3D、SQLite、本機 FastAPI 與瀏覽器擴充功能協同，並含 C++ 力導向圖加速。
👉 [開發文件](https://de4321.github.io/darkeye/development/)

---

<a id="community"></a>

## 社群

有問題或想法？歡迎加入 Discord：[加入社群][link-discord]

- **新手支援**：文件閱讀中有疑問歡迎提問；線上文件持續完善中。
- **提前獲知進展**：新功能、開發進展與預釋出版本會先在 Discord 討論。
- **參與方向**：想影響 roadmap，歡迎來討論。

---

<a id="references"></a>

## 參考專案

- [mdcz](https://github.com/ShotHeadman/mdcz)：從本機影片檔名提取番號的程式碼參考，並嘗試適配其 NFO
- [Jvedio](https://github.com/hitchao/Jvedio)：資料庫接入與匯出
- [JavSP](https://github.com/Yuukiy/JavSP)：部分站點爬蟲邏輯參考
- [JAV-JHS](https://sleazyfork.org/zh-CN/scripts/558525-jav-jhs)：javdb、FC2 等資訊參考
- [JAV_MovieManager](https://github.com/4evergaeul/JAV_MovieManager)
- [stash](https://github.com/stashapp/stash)
- [AMMDS](https://github.com/QYG2297248353/AMMDS-Docker)
- [mdc-ng](https://github.com/mdc-ng/mdc-ng)

---

## 貢獻者

<a href="https://github.com/de4321/darkeye/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=de4321/darkeye" alt="Contributors" width="500" />
</a>

---

<div align="center" style="color: gray;">DarkEye — 在本機收藏，安心整理。</div>

<!-- Badge images -->

[badge-readme-zh-CN]: https://img.shields.io/badge/README%20%C2%B7%20%E7%AE%80%E4%BD%93%E4%B8%AD%E6%96%87-555555?style=for-the-badge
[badge-readme-zh-TW]: https://img.shields.io/badge/README%20%C2%B7%20%E7%B9%81%E9%AB%94%E4%B8%AD%E6%96%87-2ea44f?style=for-the-badge
[badge-readme-ja]: https://img.shields.io/badge/README%20%C2%B7%20%E6%97%A5%E6%9C%AC%E8%AA%9E-555555?style=for-the-badge
[badge-python]: https://img.shields.io/badge/Python-3.13-blue.svg
[badge-framework]: https://img.shields.io/badge/framework-PySide6%20(Qt6)-orange
[badge-platform]: https://img.shields.io/badge/Platform-Windows-blue
[badge-license]: https://img.shields.io/github/license/de4321/darkeye
[badge-last-commit]: https://img.shields.io/github/last-commit/de4321/darkeye
[badge-release]: https://img.shields.io/github/v/release/de4321/darkeye
[badge-stars]: https://img.shields.io/github/stars/de4321/darkeye?style=social
[badge-downloads]: https://img.shields.io/github/downloads/de4321/darkeye/total

<!-- Links -->

[link-docs]: https://de4321.github.io/darkeye/
[link-video]: https://youtu.be/VCsw1D0ccgY?si=e9typx4kPnzaVFZq
[link-website]: https://de4321.github.io/darkeye-webpage/
[link-discord]: https://discord.gg/3thnEguWUk
[link-releases]: https://github.com/de4321/darkeye/releases
