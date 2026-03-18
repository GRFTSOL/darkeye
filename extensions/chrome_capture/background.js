const SERVER_URL = "http://localhost:56789";

const pendingCrawlers = new Map();
let crawlerWindowId = null;
let crawlerWindowPromise = null;

function handleCommand(data) {
  if (data.type === "navigate") {
    const url = data.url;
    const target = data.target || "new_tab";

    if (target === "new_tab") {
      chrome.tabs.create({ url }).then((tab) => {
        // no-op
      });
    } else if (target === "current_tab") {
      chrome.tabs
        .query({ active: true, currentWindow: true })
        .then((tabs) => {
          if (tabs[0]) {
            chrome.tabs.update(tabs[0].id, { url });
          }
        });
    }
  }

  if (data.type === "crawler") {
    const web = data.web;
    const serial_number = data.serial_number;

    const addPendingInNewWindow = (url, type) => {
      const addTab = (windowId) => {
        return chrome.tabs
          .create({ windowId, url, active: false })
          .then((tab) => {
            if (tab && tab.id !== undefined) {
              pendingCrawlers.set(tab.id, { type, serial: serial_number });
            }
          })
          .catch((err) => {
            console.error("DarkEye (Chrome): crawler window may be closed, recreate", err);
            crawlerWindowId = null;
            crawlerWindowPromise = null;
            addPendingInNewWindow(url, type);
          });
      };

      if (crawlerWindowId !== null) {
        addTab(crawlerWindowId);
        return;
      }

      if (crawlerWindowPromise === null) {
        const crawlerHomeUrl = "https://www.baidu.com";
        crawlerWindowPromise = chrome.windows
          .create({
            url: crawlerHomeUrl,
            type: "normal",
            focused: false,
            state: "minimized",
          })
          .then((win) => {
            crawlerWindowId = win.id;
            return win.id;
          })
          .catch((err) => {
            console.error("DarkEye (Chrome): Failed to create crawler window", err);
            crawlerWindowPromise = null;
            throw err;
          });
      }

      crawlerWindowPromise.then((windowId) => addTab(windowId));
    };

    if (web === "javlib") {
      const url = "https://www.javlibrary.com/cn/vl_searchbyid.php?keyword=" + String(serial_number);
      addPendingInNewWindow(url, "javlib");
    }
    if (web === "javdb") {
      const url = "https://www.javdb.com/search?q=" + String(serial_number);
      addPendingInNewWindow(url, "javdb");
    }
    if (web === "fanza") {
      const url = "https://www.dmm.co.jp/mono/-/search/=/searchstr=" + String(serial_number);
      addPendingInNewWindow(url, "fanza");
    }
  }
}

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === "complete" && pendingCrawlers.has(tabId)) {
    const task = pendingCrawlers.get(tabId);

    if (task.type === "javlib") {
      chrome.tabs.sendMessage(tabId, { command: "javlibrary-dvdid", serial: task.serial });
      console.log("javlib crawler start: " + tabId);
    } else if (task.type === "javdb") {
      chrome.tabs.sendMessage(tabId, { command: "javdb-dvdid", serial: task.serial });
      console.log("javdb crawler start: " + tabId);
    } else if (task.type === "fanza") {
      chrome.tabs.sendMessage(tabId, { command: "fanza-dvdid", serial: task.serial });
      console.log("fanza crawler start: " + tabId);
    }

    pendingCrawlers.delete(tabId);
  }
});

chrome.windows.onRemoved.addListener((windowId) => {
  if (windowId === crawlerWindowId) {
    crawlerWindowId = null;
    crawlerWindowPromise = null;
  }
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message && message.type === "sse_command" && message.payload) {
    try {
      handleCommand(message.payload);
    } catch (e) {
      console.error("DarkEye (Chrome): Failed to handle SSE command", e);
    }
    return;
  }

  if (message.command === "check_existence") {
    fetch(`${SERVER_URL}/api/v1/check_existence`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ items: message.items }),
    })
      .then((res) => res.json())
      .then((data) => sendResponse(data))
      .catch((err) => sendResponse({ error: err.message }));

    return true;
  }

  if (message.command === "capture_item") {
    fetch(`${SERVER_URL}/api/v1/capture`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(message.payload),
    })
      .then((res) => res.json())
      .then((data) => sendResponse(data))
      .catch((err) => sendResponse({ error: err.message }));

    return true;
  }

  if (message.command === "capture_one") {
    fetch(`${SERVER_URL}/api/v1/capture/one`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(message.payload),
    })
      .then((res) => res.json())
      .then((data) => sendResponse(data))
      .catch((err) => sendResponse({ error: err.message }));
    console.log("DarkEye (Chrome): capture_one to server", message);
    return true;
  }

  if (message.command === "capture_minnano_id") {
    console.log("DarkEye (Chrome): Received ID capture request", message);

    fetch(`${SERVER_URL}/api/v1/actressid`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        source: "minnano",
        id: message.id,
        url: sender.tab ? sender.tab.url : null,
      }),
    })
      .then((response) => response.json())
      .then((data) => {
        console.log("DarkEye (Chrome): ID sent to server", data);
        if (sender.tab && sender.tab.id) {
          chrome.tabs.remove(sender.tab.id);
        }
      })
      .catch((error) => {
        console.error("DarkEye (Chrome): Failed to send ID", error);
      });
  }

  if (message.command === "send_crawler_result") {
    console.log("DarkEye (Chrome): send crawler result to local server", message);

    fetch(`${SERVER_URL}/api/v1/crawler-result`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        results: message.result,
        id: message.id,
        web: message.web,
        data: message.data,
      }),
    })
      .then((response) => response.json())
      .then((data) => {
        console.log("DarkEye (Chrome): crawler result sent", data);
        if (sender.tab && sender.tab.id) {
          setTimeout(() => {
            chrome.tabs.remove(sender.tab.id);
          }, 10000);
        }
      })
      .catch((error) => {
        console.error("DarkEye (Chrome): Failed to send data", error);
      });
  }
});

async function ensureOffscreen() {
  if (chrome.offscreen && chrome.offscreen.hasDocument) {
    const hasDoc = await chrome.offscreen.hasDocument();
    if (hasDoc) return;
  }
  try {
    await chrome.offscreen.createDocument({
      url: "offscreen.html",
      reasons: ["DOM_SCRAPING"],
      justification: "SSE connection to receive DarkEye server commands",
    });
  } catch (e) {
    console.error("DarkEye (Chrome): Failed to create offscreen document", e);
  }
}

chrome.runtime.onStartup.addListener(() => {
  ensureOffscreen();
});

chrome.runtime.onInstalled.addListener(() => {
  ensureOffscreen();
});

ensureOffscreen();

