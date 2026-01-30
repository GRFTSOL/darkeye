//jablib
(function() {
  browser.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.command === "javlibrary-dvdid"){
        sessionStorage.setItem('darkeye_auto_parse', 'true')
        sessionStorage.setItem('id', message.serial)
        //这里开始爬，主要的步骤就是，大致搜索获得准确单作品详细页面的网址，然后解析，回传数据
        if (!search_javlibrary()){
            //这里回传失败的信息
        }
    }
  });


  function search_javlibrary(){
    // 检查是否是遇到多搜索界面，返回正确的地址供跳转
    // 直接跳到对应的番号页面
    // 搜不到，无结果
    // 多结果，一个蓝光一个普通，ブルーレイディスク 找不带蓝光版本的，封面比例正确
    // 多结果，还是不同的很少，MIDV-010
    if (window.location.href.startsWith("https://www.javlibrary.com/cn/vl_searchbyid.php?keyword=")){//以这个开头说明没有跳转到单个详情页。
        const videos = document.querySelectorAll('div.video');
        if (videos.length === 0) {
            // 优先检查是否是 Cloudflare
            if (document.title.includes("Just a moment") || document.title.includes("Attention Required") || document.querySelector('#challenge-running')) {
                console.log("DarkEye: 遇到 Cloudflare，暂不报错，等待自动重试...");
                // 关键：在这里设置 sessionStorage 标记，确保刷新后能接力
                sessionStorage.setItem('darkeye_auto_parse', 'true');
                return false; 
            }
            console.log("该番号javlib没有搜索结果");
            sessionStorage.setItem('darkeye_auto_parse', 'false')//消除标记
            // 回传失败的信息
            browser.runtime.sendMessage({
                command: "send_crawler_result",
                id: sessionStorage.getItem('id'),
                web:'javlib',
                result: false,
                data:{}
            });
            return false;
        }
        console.log("搜索结果个数: " + videos.length);
        const results = Array.from(videos).map(video => {
            const idDiv = video.querySelector('.id');
            const titleDiv = video.querySelector('.title');
            const link = video.querySelector('a');
            return {
                id: idDiv ? idDiv.textContent.trim() : "",
                title: titleDiv ? titleDiv.textContent.trim() : "",
                url: link ? link.href : ""
            };
        });
        console.log("results: " + results);

        // 筛选出不含"ブルーレイディスク"的条目
        const filtered = results.filter(item => !item.title.includes("ブルーレイディスク"));

        console.log("filtered: " + filtered);
        // 如果有符合条件的结果，返回第一个链接；如果没有符合条件的，返回第一个结果的链接（或者根据需求返回null）
        let targetUrl = null;
        if (filtered.length > 0) {
            targetUrl = filtered[0].url;
        } else if (results.length > 0) {
            // 如果所有的都包含蓝光字样，或者没有过滤出结果，这里默认返回第一个，防止死循环或无结果
            targetUrl = results[0].url;
        }
        
        if (targetUrl) {
            // 设置标记，表示正在进行自动跳转任务
            sessionStorage.setItem('darkeye_auto_parse', 'true');
            // 执行浏览器跳转
            window.location.href = targetUrl;
        }
    }else{
        parse_data_javlibrary()
    }
  }

  function parse_data_javlibrary(){
    // 解析javlibrary详细页面数据
    if (window.location.href.includes("javlibrary.com")) {
        const data = {};

        const dvdidElement = document.querySelector("#video_id .text");

        data.id = dvdidElement ? dvdidElement.textContent.trim() : "";
        //平台特有的以v结尾把v给去除了
        data.id = data.id.endsWith('v') ? data.id.slice(0, -1) : data.id;
        console.log("番号: " + data.id);

        const titleElement = document.querySelector(".post-title.text a");
        if (titleElement) {
            let newtitle=titleElement.textContent.replace(data.id,'').trim()
            data.title = newtitle;
            console.log("标题: " + data.title);
        }

        const dateElement = document.querySelector("#video_date .text");
        data.release_date = dateElement ? dateElement.textContent.trim() : "";
        console.log("发行日期: " + data.release_date);

        const lengthElement = document.querySelector("#video_length .text");
        data.length = lengthElement ? lengthElement.textContent.trim() : "";
        console.log("影片长度: " + data.length);

        const directorElement = document.querySelector("#video_director .text");
        data.director = directorElement ? directorElement.textContent.trim() : "";
        console.log("导演: " + data.director);

        
        const genreElements = document.querySelectorAll("#video_genres .genre a");
        data.genre = Array.from(genreElements).map(el => el.textContent.trim());
        console.log("类型列表: " + data.genre);

        const castElements = document.querySelectorAll("#video_cast .star a");
        data.actress = Array.from(castElements).map(el => el.textContent.trim());
        console.log("演员列表: " + data.actress);

        const imgElement = document.querySelector("#video_jacket_img");
        data.image = imgElement ? imgElement.src : "";
        console.log("封面地址找到: " + data.image);

        sessionStorage.setItem('darkeye_auto_parse', 'false')//消除标记
        if (data) {
            console.debug("发送数据")
            browser.runtime.sendMessage({
                command: "send_crawler_result",
                id: sessionStorage.getItem('id'),
                web:'javlib', 
                result: true,
                data:data
            });
        }
    }
  }

  // 页面加载时自动检查是否有未完成的任务
  if (sessionStorage.getItem('darkeye_auto_parse') === 'true') {
      // 清除标记，防止无限循环
      sessionStorage.removeItem('darkeye_auto_parse');
      // 检查当前是否是详情页（不以 searchbyid 开头）
      if (!window.location.href.startsWith("https://www.javlibrary.com/cn/vl_searchbyid.php?keyword=")) {
          // 延迟一点执行，确保DOM完全就绪
          setTimeout(() => {
              console.log("DarkEye: 检测到自动跳转任务，开始解析...");
              parse_data_javlibrary();
          }, 1000);
      }
  }
})();

//fanza
(function() {
  // Fanza 专用逻辑模块
  // 监听来自 background 的消息
  browser.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.command === "fanza-dvdid"){
        sessionStorage.setItem('darkeye_fanza_parse', 'true');
        if (message.serial) {
            sessionStorage.setItem('darkeye_fanza_serial', message.serial);
        }
        serach_fanza();
    }
  });


  function serach_fanza() {
      console.log("DarkEye: Fanza checkAndParse...");
      
      // 1. 检查年龄确认页面
      // 查找包含 "はい" 或 "Enter" 的链接/按钮
      const links = Array.from(document.querySelectorAll('a, input[type="submit"], button'));
      const yesBtn = links.find(el => {
          const text = el.textContent || el.value || "";
          return text.includes("はい") || text.includes("Enter");
      });
      
      if (yesBtn && (document.body.innerText.includes("18歳未満") || document.body.innerText.includes("Age Verification"))) {
          console.log("DarkEye: 检测到年龄确认，自动点击...");
          yesBtn.click();
          // 点击后页面会刷新，任务状态在 sessionStorage 里，刷新后会自动继续
          return;
      }

      // 2. 检查是否在搜索结果页
      if (window.location.href.includes("dmm.co.jp/mono/-/search/")) {
          console.log("DarkEye: Fanza 搜索结果页，开始提取...");
          
          const items = document.querySelectorAll('div.border-r.border-b.border-gray-300');
          const results = Array.from(items).map(item => {
              const linkElement = item.querySelector('a');
              if (linkElement) {
                  const url = linkElement.href;
                  const match = url.match(/cid=([^/&?]+)/);
                  if (match) {
                      return {
                          cid: match[1], 
                          url: url
                      };
                  }
              }
              return null;
          }).filter(item => item !== null);

          console.log("DarkEye Fanza Results:", results);
          
          // 获取透传的 serial
          const serial = sessionStorage.getItem('darkeye_fanza_serial') || "";


      }
  }

  function parse_data_fanza(){
    //专门检查fanza详细的页面

    //发送标记

        // 任务完成，清除标记
          sessionStorage.removeItem('darkeye_fanza_parse');
          sessionStorage.removeItem('darkeye_fanza_serial');
  }

  // 页面加载自动检查
  if (sessionStorage.getItem('darkeye_fanza_parse') === 'true') {
      setTimeout(checkAndParseFanza, 1000);
  }

})();




//popup的服务
(function() {
browser.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.command === "capture-javdb") {
      try {
        const results = captureDataJavdb();
        // sendResponse 返回 Promise 或者是直接返回对象（取决于浏览器实现，Firefox支持Promise）
        // 为了兼容性，这里返回 Promise.resolve
        return Promise.resolve({
          results: results,
          url: window.location.href,
          title: document.title
        });
      } catch (e) {
        return Promise.resolve({ error: e.message });
      }
    }
    if (message.command === "capture-javlibrary") {
      try {
        const results = captureDataJavlibrary();

        return Promise.resolve({
          results: results,
          url: window.location.href,
          title: document.title
        });
      } catch (e) {
        return Promise.resolve({ error: e.message });
      }
    }
});
  //这个是提取JavDB的番号，用于多个番号页面
  function captureDataJavdb() {
    const items = document.querySelectorAll('.item');
    const results = [];
    
    items.forEach((item) => {
      // 1. 提取评分
      const scoreEl = item.querySelector('.score .value');
      let score = 0;
      if (scoreEl) {
        // 文本形如: "4.15分, 由380人評價"
        const match = scoreEl.textContent.trim().match(/([\d\.]+)/);
        if (match) {
          score = parseFloat(match[1]);
        }
      }

      // 2. 筛选: 只保留 4.5 分以上
      if (score >= 4.5) {
        const titleEl = item.querySelector('.video-title');
        if (titleEl) {
          // 只要 strong 标签里的内容 (例如 MIDA-310)
          const strongEl = titleEl.querySelector('strong');
          if (strongEl) {
            let text = strongEl.textContent.trim();
            if (text) {
              results.push({ serial: text, score: score });
            }
          }
        }
      }
    });
    return results;
  }
  //这个是提取JavLibrary的番号，用于多个番号页面
  function captureDataJavlibrary() {
    //这个提取由于没有分数，直接全部提取出来
  const videos = document.querySelectorAll('div.video');
  const results = [];

  videos.forEach((video) => {
    // 2. 提取番号
    const idEl = video.querySelector('div.id');
    if (idEl) {
      const serial = idEl.textContent.trim();
      
      if (serial) {
        results.push({
          serial: serial,
          score: 0 // 暂时给个默认值，或者解析实际评分
        });
      }
    }
  });

  return results;
  }

})();

// minnao-av的 actress页面
(function(){
  // --- Minnano Overlay Logic ---
  // 这个是对于Minnano actress页面的Overlay，提取actress ID并传到本地服务器上
  function initMinnanoOverlay() {
      // Check if document body exists, if not wait for load
      if (!document.body) {
          window.addEventListener('DOMContentLoaded', initMinnanoOverlay);
          return;
      }

      const url = window.location.href;
      // Regex matches https://www.minnano-av.com/actress123456.html
      const match = url.match(/minnano-av\.com\/actress(\d+)\.html/);
      
      if (match) {
          const actressId = match[1];
          console.log("DarkEye: Minnano actress page detected. ID:", actressId);
          // Check if overlay already exists
          if (document.getElementById('darkeye-overlay')) return;
          createOverlay(actressId);
      }
  }

  function createOverlay(actressId) {
      // Container
      const container = document.createElement('div');
      container.id = 'darkeye-overlay';
      container.style.cssText = `
          position: fixed;
          bottom: 30px;
          right: 30px;
          z-index: 2147483647; /* Max z-index */
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      `;

      // Main Button (Floating Ball)
      const fab = document.createElement('button');
      fab.textContent = 'DE'; // DarkEye
      fab.style.cssText = `
          width: 56px;
          height: 56px;
          border-radius: 28px;
          background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
          color: #fff;
          border: 2px solid rgba(255,255,255,0.2);
          cursor: pointer;
          font-weight: 900;
          font-size: 18px;
          box-shadow: 0 4px 15px rgba(0,0,0,0.4);
          transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
          display: flex;
          align-items: center;
          justify-content: center;
          text-shadow: 0 1px 2px rgba(0,0,0,0.3);
      `;
      
      // Hover effect
      fab.onmouseenter = () => { fab.style.transform = 'scale(1.1)'; };
      fab.onmouseleave = () => { 
          if (panel.style.display === 'none') fab.style.transform = 'scale(1)'; 
          else fab.style.transform = 'rotate(45deg)';
      };

      // Expand Panel
      const panel = document.createElement('div');
      panel.style.cssText = `
          position: absolute;
          bottom: 70px;
          right: 0;
          background: #fff;
          border: 1px solid rgba(0,0,0,0.1);
          border-radius: 12px;
          padding: 12px;
          box-shadow: 0 8px 20px rgba(0,0,0,0.15);
          display: none;
          width: 180px;
          flex-direction: column;
          gap: 10px;
          animation: slideUp 0.2s ease-out;
      `;
      
      // Add animation keyframes
      const styleSheet = document.createElement("style");
      styleSheet.innerText = `
        @keyframes slideUp {
          from { opacity: 0; transform: translateY(10px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `;
      document.head.appendChild(styleSheet);

      // Info Text
      const info = document.createElement('div');
      info.innerHTML = `<strong>DarkEye</strong><br><span style="font-size:12px;color:#666">ID: ${actressId}</span>`;
      info.style.color = '#333';
      info.style.fontSize = '14px';
      info.style.textAlign = 'center';

      // Capture Button
      const btnCapture = document.createElement('button');
      btnCapture.textContent = '采集此ID';
      btnCapture.style.cssText = `
          background: #007aff;
          color: white;
          border: none;
          padding: 8px 12px;
          border-radius: 6px;
          cursor: pointer;
          font-size: 13px;
          font-weight: 600;
          transition: background 0.2s;
          width: 100%;
      `;
      
      btnCapture.onmouseover = () => btnCapture.style.background = '#0062cc';
      btnCapture.onmouseout = () => btnCapture.style.background = '#007aff';

      btnCapture.onclick = () => {
          btnCapture.textContent = '发送中...';
          btnCapture.disabled = true;
          
          browser.runtime.sendMessage({
              command: "capture_minnano_id",
              id: actressId
          });
          
          setTimeout(() => {
             btnCapture.style.background = '#34c759';
             btnCapture.textContent = '已发送';
          }, 500);
      };

      // Toggle Panel
      fab.onclick = () => {
          if (panel.style.display === 'none') {
              panel.style.display = 'flex';
              fab.style.transform = 'rotate(45deg)';
          } else {
              panel.style.display = 'none';
              fab.style.transform = 'rotate(0deg)';
          }
      };

      panel.appendChild(info);
      panel.appendChild(btnCapture);
      container.appendChild(panel);
      container.appendChild(fab);
      document.body.appendChild(container);
  }

  // Run init
  if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', initMinnanoOverlay);
  } else {
      initMinnanoOverlay();
  }
})();

// --- 作品番号探测器  ---
(function() {
    // 1. 识别网站前缀
    if (!window.location.href.startsWith("https://javdb.com") && !window.location.href.startsWith("https://www.javlibrary.com")) {
        return;
    }

    //console.log("DarkEye: JavDB Sniffer Activated");

    // State management
    const State = {
        pendingItems: new Map(), // id -> { element, timestamp }
        checkQueue: new Set(),
        checkTimer: null
    };

    class SiteSniffer {
        constructor() {
            this.observer = null;
        }

        init() {
            this.scanExisting();
            this.startObserver();
            this.startProcessor();
        }

        scanExisting() {
            const items = document.querySelectorAll(this.itemSelector);
            items.forEach(item => this.processItem(item));
        }

        startObserver() {
            // MutationObserver to handle waterfall flow
            this.observer = new MutationObserver((mutations) => {
                mutations.forEach((mutation) => {
                    mutation.addedNodes.forEach((node) => {
                        if (node.nodeType === 1) { // ELEMENT_NODE
                            if (node.matches && node.matches(this.itemSelector)) {
                                this.processItem(node);
                            }
                            if (node.querySelectorAll) {
                                const children = node.querySelectorAll(this.itemSelector);
                                children.forEach(item => this.processItem(item));
                            }
                        }
                    });
                });
            });

            this.observer.observe(document.body, {
                childList: true,
                subtree: true
            });
        }

        startProcessor() {
            // Periodic cleanup or re-check if needed (optional)
        }

        processItem(element) {
            // Avoid duplicate processing
            if (element.dataset.darkeyeProcessed) return;
            
            const id = this.extractId(element);
            if (!id) return;

            element.dataset.darkeyeProcessed = "true";
            
            // Add to state
            State.pendingItems.set(id, { element });
            State.checkQueue.add(id);
            
            this.scheduleCheck();
        }

        scheduleCheck() {
            if (State.checkTimer) clearTimeout(State.checkTimer);
            State.checkTimer = setTimeout(() => this.performCheck(), 500); // 500ms debounce
        }

        async performCheck() {
            if (State.checkQueue.size === 0) return;

            const ids = Array.from(State.checkQueue);
            State.checkQueue.clear();

            try {
                // Send batch check request to background
                const response = await browser.runtime.sendMessage({
                    command: "check_existence",
                    items: ids
                });

                if (response && response.results) {
                    Object.entries(response.results).forEach(([id, exists]) => {
                        this.updateUI(id, exists);
                    });
                }
            } catch (e) {
                console.error("DarkEye: Check existence failed", e);
                // Mark items as error or retry?
            }
        }

        updateUI(id, exists) {
            const item = State.pendingItems.get(id);
            if (!item) return;

            const { element } = item;
            
            // Create UI tag
            const tag = document.createElement("div");
            tag.className = "darkeye-tag";
            
            if (exists) {
                tag.classList.add("exists");
                tag.textContent = "已收录";
                tag.title = "本地已收录";
            } else {
                tag.classList.add("not-found");
                tag.textContent = "+ 收藏";
                tag.title = "点击采集到本地";
                
                // Bind click event for capture
                tag.onclick = (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    this.captureItem(tag, id, element);
                };
            }

            // Inject into container
            // Ensure parent has relative positioning for absolute child
            if (getComputedStyle(element).position === 'static') {
                element.style.position = 'relative';
            }
            element.appendChild(tag);
        }

        async captureItem(tag, id, element) {
            tag.classList.remove("not-found");
            tag.classList.add("loading");
            tag.textContent = "发送中...";

            try {
                // Construct payload
                const payload = {
                    url: window.location.href,
                    title: document.title,
                    content: id,
                    extra: {
                        source: "javdb_sniff",
                        timestamp: Date.now()
                    }
                };

                const response = await browser.runtime.sendMessage({
                    command: "capture_one",
                    payload: payload
                });

                if (response && !response.error) {
                    tag.classList.remove("loading");
                    tag.classList.add("exists");
                    tag.textContent = "已收录";
                    tag.onclick = null; // Remove click handler
                } else {
                    throw new Error(response ? response.error : "Unknown error");
                }
            } catch (e) {
                console.error("Capture failed", e);
                tag.classList.remove("loading");
                tag.classList.add("error");
                tag.textContent = "失败";
                setTimeout(() => {
                    tag.classList.remove("error");
                    tag.classList.add("not-found");
                    tag.textContent = "+ 收藏";
                }, 2000);
            }
        }
    }

    class JavDBSniffer extends SiteSniffer {
        constructor() {
            super();
            this.itemSelector = ".item";
        }

        extractId(element) {
            // Extract text from .video-title strong
            const titleStrong = element.querySelector(".video-title strong");
            if (titleStrong) {
                return titleStrong.textContent.trim();
            }
            return null;
        }
    }

    class JavLibrarySniffer extends SiteSniffer {
        constructor() {
            super();
            this.itemSelector = ".video";
        }

        extractId(element) {
            // Extract text from .video-title strong
            const titleStrong = element.querySelector(".id");
            if (titleStrong) {
                return titleStrong.textContent.trim();
            }
            return null;
        }
    }
    // 确保注入在网页加载后执行
// 2. 路由分发（只负责“选人”，不负责“干活”）
let activeSniffer = null;
const url = window.location.href;

if (url.includes("javdb.com")) {
    activeSniffer = new JavDBSniffer();
} else if (url.includes("javlibrary.com")) {
    activeSniffer = new JavLibrarySniffer();
}

// 3. 统一的生命周期管理（负责“择时”和“启动”）
if (activeSniffer) {
    // 复用您现有的加载检查逻辑
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => activeSniffer.init());
    } else {
        activeSniffer.init();
    }
}
})();
