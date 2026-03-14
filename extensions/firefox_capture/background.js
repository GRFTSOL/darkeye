// background.js for Firefox (Manifest V2)
const SERVER_URL = "http://localhost:56789";
const SSE_URL = `${SERVER_URL}/events`;

let eventSource = null;

function connectSSE() {
  if (eventSource) {
    eventSource.close();
  }

  try {
      console.log("DarkEye: Connecting to SSE server at " + SSE_URL);
      eventSource = new EventSource(SSE_URL);

      eventSource.onopen = () => {
        console.log("DarkEye: Connected to SSE server");
      };

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log("DarkEye: Received command", data);
          handleCommand(data);
        } catch (e) {
          console.error("DarkEye: Error parsing SSE message", e);
        }
      };

      eventSource.onerror = (err) => {
        // EventSource error handling is tricky, often it just closes
        console.error("DarkEye: SSE Error", err);
        eventSource.close();
        // Reconnect after 5 seconds
        setTimeout(connectSSE, 5000);
      };
  } catch (e) {
      console.error("DarkEye: Failed to create EventSource", e);
      setTimeout(connectSSE, 5000);
  }
}

const pendingCrawlers = new Map();
let crawlerWindowId = null; // 专用爬虫窗口 ID
let crawlerWindowPromise = null; // 创建中的窗口 Promise，避免多任务同时开多个窗口

function handleCommand(data) {//处理服务器发送来的命令
  if (data.type === "navigate") {
    const url = data.url;
    const target = data.target || "new_tab";

    if (target === "new_tab") {
      browser.tabs.create({ url: url }).then((tab) => {
          //pendingCrawlers.add(tab.id);
      });
    } else if (target === "current_tab") {
        browser.tabs.query({active: true, currentWindow: true}).then((tabs) => {
            if (tabs[0]) {
                browser.tabs.update(tabs[0].id, { url: url });
            }
        });
    }
  }
  if (data.type==="crawler"){
    const web = data.web;
    const serial_number = data.serial_number;
    // 爬虫统一在专用窗口后台打开，不影响当前浏览窗口
    const addPendingInNewWindow = (url, type) => {
      const addTab = (windowId) => {
        return browser.tabs.create({ windowId, url, active: false })
          .then((tab) => {
            if (tab && tab.id !== undefined) {
              pendingCrawlers.set(tab.id, { type, serial: serial_number });
            }
          })
          .catch((err) => {
            console.error("DarkEye: 爬虫窗口可能已被关闭，重新创建", err);
            crawlerWindowId = null;
            crawlerWindowPromise = null;
            addPendingInNewWindow(url, type);
          });
      };

      // 已有专用窗口：直接在该窗口新建标签
      if (crawlerWindowId !== null) {
        addTab(crawlerWindowId);
        return;
      }

      // 没有专用窗口：复用“正在创建”的 Promise，保证多任务只开一个窗口
      if (crawlerWindowPromise === null) {
        const crawlerHomeUrl = "https://www.baidu.com";
        crawlerWindowPromise = browser.windows.create({
          url: crawlerHomeUrl,
          type: "normal",
          focused: false,
          state: "minimized"
        })
          .then((win) => {
            crawlerWindowId = win.id;
            return win.id;
          })
          .catch((err) => {
            console.error("DarkEye: 创建爬虫窗口失败", err);
            crawlerWindowPromise = null;
            throw err;
          });
      }

      crawlerWindowPromise.then((windowId) => addTab(windowId));
    };
    if (web==="javlib"){//开始执行对javlibrary的爬虫,第一步就是跳转
      const url = "https://www.javlibrary.com/cn/vl_searchbyid.php?keyword="+String(serial_number);
      addPendingInNewWindow(url, "javlib");
    }
    if (web==="javdb"){//开始执行对javdb的爬虫,第一步就是跳转
      const url = "https://www.javdb.com/search?q="+String(serial_number);
      addPendingInNewWindow(url, "javdb");
    }
    if (web==="fanza"){//开始执行对fanza的爬虫,第一步就是跳转
      const url = "https://www.dmm.co.jp/mono/-/search/=/searchstr="+String(serial_number);
      addPendingInNewWindow(url, "fanza");
    }
  }
}

// 监听页面加载完成，启动对应爬虫 content script
browser.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === 'complete' && pendingCrawlers.has(tabId)) {
    const task = pendingCrawlers.get(tabId);
    
    // 根据任务类型分发不同的指令，并透传 serial
    if (task.type === "javlib") {
        browser.tabs.sendMessage(tabId, { command: "javlibrary-dvdid", serial: task.serial });
        console.log("javlib爬虫开始:" + tabId);
    } else if (task.type === "javdb") {
       browser.tabs.sendMessage(tabId, { command: "javdb-dvdid", serial: task.serial });
        console.log("javdb爬虫开始:" + tabId);
    } else if(task.type === "fanza"){
      browser.tabs.sendMessage(tabId, { command: "fanza-dvdid", serial: task.serial });
      console.log("fanza爬虫开始:" + tabId);
    }
    
    // 注意：如果我们采用 Content Script 自动接力模式，这里可能不需要删除，每次刷新时判断有无任务，有就处理，直接任务全部结束
    // 为了防止多次触发，通常还是删除，依赖页面内的 sessionStorage 自动接力
    pendingCrawlers.delete(tabId); 
  }
});

// 窗口关闭时重置专用爬虫窗口 ID 与 Promise
browser.windows.onRemoved.addListener((windowId) => {
  if (windowId === crawlerWindowId) {
    crawlerWindowId = null;
    crawlerWindowPromise = null;
  }
});

// 接收 content script 消息，转发到本地服务器
browser.runtime.onMessage.addListener((message, sender, sendResponse) => {//这个是向服务器发送的消息
    if (message.command === "check_existence") {
        // Batch check existence
        fetch(`${SERVER_URL}/api/v1/check_existence`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ items: message.items })
        })
        .then(res => res.json())
        .then(data => sendResponse(data))
        .catch(err => sendResponse({ error: err.message }));
        
        return true; // Async response
    }
    if (message.command === "capture_item") {
        // Capture single item
        fetch(`${SERVER_URL}/api/v1/capture`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(message.payload)
        })
        .then(res => res.json())
        .then(data => sendResponse(data))
        .catch(err => sendResponse({ error: err.message }));

        return true; // Async response
    }
    if (message.command === "capture_one") {
        // Capture single item
        fetch(`${SERVER_URL}/api/v1/capture/one`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(message.payload)
        })
        .then(res => res.json())
        .then(data => sendResponse(data))
        .catch(err => sendResponse({ error: err.message }));
        console.log("DarkEye: 抓取指令 to server", message);
        return true; // Async response
    }
    if (message.command === "capture_minnano_id") {
        console.log("DarkEye: Received ID capture request", message);
        
        // Send to local server
        fetch(`${SERVER_URL}/api/v1/actressid`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                source: "minnano",
                id: message.id,
                url: sender.tab.url
            })
        })
        .then(response => response.json())
        .then(data => {
            console.log("DarkEye: ID sent to server", data);
            // Close the tab after successful send
            if (sender.tab && sender.tab.id) {
                browser.tabs.remove(sender.tab.id);
            }
        })
        .catch(error => {
            console.error("DarkEye: Failed to send ID", error);
        });
    }
    if (message.command === "send_crawler_result") {
        console.log("发送爬虫的结果到本地服务器", message);
        // Send to local server
        fetch(`${SERVER_URL}/api/v1/crawler-result`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                results: message.result,
                id: message.id,
                web: message.web,
                data: message.data
            })
        })
        .then(response => response.json())
        .then(data => {
            console.log("DarkEye: ID sent to server", data);
            // Close the tab after successful send

            //if (sender.tab && sender.tab.id) {
            //    setTimeout(() => {
            //        browser.tabs.remove(sender.tab.id);
            //    }, 5000);
            //}
        })
        .catch(error => {
            console.error("DarkEye: Failed to send data", error);
        });
    }
});

// Initial connect
// ion
connectSSE();