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
    if (web==="javlib"){//开始执行对javlibrary的爬虫,第一步就是跳转
      url="https://www.javlibrary.com/cn/vl_searchbyid.php?keyword="+String(serial_number);
      browser.tabs.create({ url: url ,active:true}).then((tab) => {
          pendingCrawlers.set(tab.id, { type: "javlib", serial: serial_number });
      });
    }
    if (web==="javdb"){//开始执行对javdb的爬虫,第一步就是跳转
      url="https://www.javdb.com/search?keyword="+String(serial_number);
      browser.tabs.create({ url: url }).then((tab) => {
          pendingCrawlers.set(tab.id, { type: "javdb", serial: serial_number });
      });
    }
    if (web==="fanza"){//开始执行对fanza的爬虫,第一步就是跳转
      url="https://www.dmm.co.jp/mono/-/search/=/searchstr="+String(serial_number);
      
      browser.tabs.create({ url: url }).then((tab) => {
          pendingCrawlers.set(tab.id, { type: "fanza", serial: serial_number });
      }); 
    }
    
  }
}

// 监听 tab 加载状态
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
// Initial connect
// ion
connectSSE();

// Listen for messages from content scripts
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
            if (sender.tab && sender.tab.id) {
                setTimeout(() => {
                    browser.tabs.remove(sender.tab.id);
                }, 5000);
            }
        })
        .catch(error => {
            console.error("DarkEye: Failed to send data", error);
        });
    }
});
