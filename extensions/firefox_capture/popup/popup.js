
// popup.js

const btnCapture = document.getElementById("btn-capture");
const btnCaptureDetail = document.getElementById("btn-capture-detail");
const btnSend = document.getElementById("btn-send");
const outputDiv = document.querySelector(".output");
const statusDiv = document.querySelector(".status");
const serverStatusEl = document.getElementById("server-status");

// State
let currentResults = [];
let pageInfo = { url: "", title: "" };

const SERVER_URL = "http://localhost:56789";

// --- Check Server Status ---
function checkServerStatus() {
  serverStatusEl.textContent = "⚪ 正在连接...";
  
  // Set a timeout for the fetch
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 2000);
  
  fetch(`${SERVER_URL}/api/v1/health`, { signal: controller.signal })
    .then(response => {
      if (response.ok) {
        serverStatusEl.textContent = "🟢 已连接到 DarkEye Server";
        serverStatusEl.style.color = "#34c759"; // Green
      } else {
        throw new Error("Server error");
      }
    })
    .catch(err => {
      console.error("Server check failed:", err);
      serverStatusEl.textContent = "🔴 桌面端未启动";
      serverStatusEl.style.color = "#ff3b30"; // Red
    })
    .finally(() => clearTimeout(timeoutId));
}

// Init check
checkServerStatus();
// 【在这里添加启动时的打印】
log("支持JavDB"); 
log("支持JavLibrary");

function log(msg) {
  outputDiv.textContent += msg + "\n";
  outputDiv.scrollTop = outputDiv.scrollHeight;
}

btnCapture.addEventListener("click", () => {
  log("正在请求页面抓取...");
  statusDiv.textContent = "Requesting...";

  // 查询当前活动标签页 
  browser.tabs.query({ active: true, currentWindow: true }).then((tabs) => { 
    if (tabs.length === 0) { 
      log("Error: No active tab found."); 
      return; 
    } 
    const activeTab = tabs[0]; 
    const currentUrl = activeTab.url;
    let command = "capture"; // 默认 command

    if (currentUrl.startsWith("https://www.javlibrary.com")) {
        command = "capture-javlibrary";
    } else if (currentUrl.startsWith("https://javdb.com")) {
        command = "capture-javdb";
    }
    
    // 发送消息给 content script 
    browser.tabs.sendMessage(activeTab.id, { command: command }) 
      .then((response) => {
        if (!response) {
          log("Error: No response from content script.");
          return;
        }
        
        if (response.error) {
          log(`Error: ${response.error}`);
          statusDiv.textContent = "Error";
          return;
        }

        // 处理返回的数据
        currentResults = response.results || [];
        pageInfo.url = response.url;
        pageInfo.title = response.title;

        log(`成功提取 ${currentResults.length} 条数据`);
        if (currentResults.length > 0) {
          outputDiv.textContent += "--- All Results ---\n";
          currentResults.forEach(r => outputDiv.textContent += `${r.serial} [${r.score}]\n`);
        } else {
          log("未找到符合条件的内容 (评分>=4.5)");
        }
        statusDiv.textContent = `Done (${currentResults.length})`;

      })
      .catch((error) => {
        log(`Communication Error: ${error.message}`);
        log("提示: 请确保页面加载完成，或者刷新页面重试。");
        statusDiv.textContent = "Comm Error";
      });
  });
});

btnSend.addEventListener("click", () => {
  if (currentResults.length === 0) {
    log("没有数据可发送，请先抓取");
    return;
  }

  log("正在发送到本地服务器...");
  
  const serials = currentResults.map(r => r.serial);
  
  const payload = {
    url: pageInfo.url,
    title: pageInfo.title,
    content: serials.join(", "),
    extra: {
      count: serials.length,
      source: "firefox_plugin"
    }
  };

  fetch("http://127.0.0.1:56789/api/v1/capture", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  })
  .then(response => {
    if (response.ok) return response.json();
    throw new Error("Network response was not ok");
  })
  .then(data => {
    log("发送成功: " + JSON.stringify(data));
    statusDiv.textContent = "Sent Success";
  })
  .catch(error => {
    log("发送失败: " + error.message);
    statusDiv.textContent = "Sent Failed";
  });
});
