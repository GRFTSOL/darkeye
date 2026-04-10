// background.js for Chrome (Manifest V3; SSE 在 offscreen，经 sse_command 转发)
const SERVER_URL = "http://localhost:56789";

/** 与 ``utils.serial_number.convert_fanza`` 一致，供 avdanyuwiki 首跳搜索串。 */
function convertFanzaForAvdanyuwiki(serial_number) {
  let converted_code = String(serial_number).toLowerCase().replace(/-/g, "00");
  const halfCoverPrefixes = ["start", "stars", "star", "sdde", "kmhrs"];
  const fullCoverPrefixes = [
    "namh",
    "dldss",
    "fns",
    "fsdss",
    "boko",
    "sdam",
    "hawa",
    "moon",
    "mogi",
    "nhdtb",
  ];
  if (halfCoverPrefixes.some((p) => converted_code.startsWith(p))) {
    converted_code = "1" + converted_code;
  }
  if (fullCoverPrefixes.some((p) => converted_code.startsWith(p))) {
    converted_code = "1" + converted_code;
  }
  if (converted_code.startsWith("knmb")) {
    converted_code = "h_491" + converted_code;
  }
  if (converted_code.startsWith("isrd")) {
    converted_code = "24" + converted_code;
  }
  return converted_code;
}

const pendingCrawlers = new Map();
/** 桌面 navigate 写入：tabId -> { actress_id?, source? } */
const tabNavigateContext = new Map();
/** session 中持久化，避免 MV3 service worker 休眠后丢失 ID */
const CRAWLER_WINDOW_STORAGE_KEY = "crawlerWindowId";
let crawlerWindowId = null; // 专用爬虫窗口 ID（内存缓存，与 session 同步）
/** 并发 ensure 只跑一次创建逻辑 */
let crawlerWindowEnsurePromise = null;

async function crawlerWindowExists(windowId) {
  try {
    await chrome.windows.get(windowId);
    return true;
  } catch {
    return false;
  }
}

async function hydrateCrawlerWindowIdFromStorage() {
  try {
    const data = await chrome.storage.session.get(CRAWLER_WINDOW_STORAGE_KEY);
    const stored = data[CRAWLER_WINDOW_STORAGE_KEY];
    if (stored == null) {
      crawlerWindowId = null;
      return;
    }
    if (await crawlerWindowExists(stored)) {
      crawlerWindowId = stored;
    } else {
      await chrome.storage.session.remove(CRAWLER_WINDOW_STORAGE_KEY);
      crawlerWindowId = null;
    }
  } catch (e) {
    console.error("DarkEye: hydrateCrawlerWindowIdFromStorage", e);
  }
}

async function clearCrawlerWindowPersistence() {
  crawlerWindowId = null;
  crawlerWindowEnsurePromise = null;
  try {
    await chrome.storage.session.remove(CRAWLER_WINDOW_STORAGE_KEY);
  } catch (e) {
    console.error("DarkEye: clearCrawlerWindowPersistence", e);
  }
}

/**
 * 返回可用的爬虫专用窗口 ID：优先 session 中已保存且仍存在的窗口，否则创建。
 */
async function ensureCrawlerWindowId() {
  if (crawlerWindowEnsurePromise) {
    return crawlerWindowEnsurePromise;
  }
  crawlerWindowEnsurePromise = (async () => {
    try {
      await hydrateCrawlerWindowIdFromStorage();
      if (crawlerWindowId != null) {
        return crawlerWindowId;
      }
      const crawlerHomeUrl = "https://www.baidu.com";
      const win = await chrome.windows.create({
        url: crawlerHomeUrl,
        type: "normal",
        focused: false,
        state: "minimized",
      });
      crawlerWindowId = win.id;
      await chrome.storage.session.set({
        [CRAWLER_WINDOW_STORAGE_KEY]: win.id,
      });
      return win.id;
    } catch (e) {
      console.error("DarkEye: ensureCrawlerWindowId", e);
      throw e;
    } finally {
      crawlerWindowEnsurePromise = null;
    }
  })();
  return crawlerWindowEnsurePromise;
}

/** 专用窗口内标签总数达到该值时通知桌面（去重：跌破后再回升才再报） */
const CRAWLER_BACKLOG_THRESHOLD = 13; // 与 Firefox 扩展一致；正常情况下大于10个就通知桌面
let backlogWarningArmed = true;

/** Uint8Array -> base64（避免大文件 String.fromCharCode 爆栈） */
function uint8ToBase64(u8) {
  const CHUNK = 0x8000;
  let s = "";
  for (let i = 0; i < u8.length; i += CHUNK) {
    s += String.fromCharCode.apply(
      null,
      u8.subarray(i, Math.min(i + CHUNK, u8.length))
    );
  }
  return btoa(s);
}

function postCoverFetchResult(request_id, ok, error, content_base64) {
  fetch(`${SERVER_URL}/api/v1/cover-image-fetch-result`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      request_id,
      ok,
      error: error || null,
      content_base64: content_base64 || null,
    }),
  }).catch((err) => {
    console.error("DarkEye: cover-image-fetch-result failed", err);
  });
}

function fetchCoverImageForDesktop(imageUrl, request_id) {
  const minBytes = 5 * 1024;
  fetch(imageUrl, { credentials: "omit", cache: "no-store" })
    .then((r) => {
      if (!r.ok) {
        postCoverFetchResult(request_id, false, `HTTP ${r.status}`, null);
        return null;
      }
      return r.arrayBuffer();
    })
    .then((buf) => {
      if (!buf) return;
      const u8 = new Uint8Array(buf);
      if (u8.length < minBytes) {
        postCoverFetchResult(request_id, false, "图片过小（小于 5KB）", null);
        return;
      }
      const b64 = uint8ToBase64(u8);
      postCoverFetchResult(request_id, true, null, b64);
    })
    .catch((e) => {
      console.error("DarkEye: fetchCoverImageForDesktop", e);
      postCoverFetchResult(request_id, false, String(e), null);
    });
}

function maybeNotifyCrawlerBacklog() {
  if (crawlerWindowId === null) {
    return Promise.resolve();
  }
  return chrome.tabs
    .query({ windowId: crawlerWindowId })
    .then((tabs) => {
      const count = tabs.length;
      if (count >= CRAWLER_BACKLOG_THRESHOLD && backlogWarningArmed) {
        backlogWarningArmed = false;
        fetch(`${SERVER_URL}/api/v1/crawler-backlog-warning`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            browser: "chrome",
            count,
            threshold: CRAWLER_BACKLOG_THRESHOLD,
          }),
        }).catch((err) => {
          console.error("DarkEye: crawler-backlog-warning failed", err);
        });
      }
      if (count < CRAWLER_BACKLOG_THRESHOLD) {
        backlogWarningArmed = true;
      }
    })
    .catch((err) => {
      console.error("DarkEye: maybeNotifyCrawlerBacklog", err);
    });
}

function handleCommand(data) {
  // 处理服务器发送来的命令
  if (data.type === "navigate") {
    const url = data.url;
    const target = data.target || "new_tab";
    const ctx = data.context || null;

    if (target === "new_tab") {
      chrome.tabs.create({ url }).then((tab) => {
        if (ctx != null && tab && tab.id !== undefined) {
          tabNavigateContext.set(tab.id, ctx);
        }
      });
    } else if (target === "current_tab") {
      chrome.tabs.query({ active: true, currentWindow: true }).then((tabs) => {
        if (tabs[0]) {
          const tid = tabs[0].id;
          chrome.tabs.update(tid, { url }).then(() => {
            if (ctx != null) tabNavigateContext.set(tid, ctx);
          });
        }
      });
    }
  }
  if (data.type === "crawler") {
    const web = data.web;
    const serial_number = data.serial_number;
    // 爬虫统一在专用窗口后台打开，不影响当前浏览窗口
    const addPendingInNewWindow = (url, type) => {
      const addTab = (windowId) => {
        return chrome.tabs
          .create({ windowId, url, active: false })
          .then((tab) => {
            if (tab && tab.id !== undefined) {
              pendingCrawlers.set(tab.id, { type, serial: serial_number });
            }
            return maybeNotifyCrawlerBacklog();
          })
          .catch(async (err) => {
            console.error("DarkEye: 爬虫窗口可能已被关闭，重新创建", err);
            await clearCrawlerWindowPersistence();
            backlogWarningArmed = true;
            addPendingInNewWindow(url, type);
          });
      };

      ensureCrawlerWindowId()
        .then((windowId) => addTab(windowId))
        .catch((err) => {
          console.error("DarkEye: 获取/创建爬虫窗口失败", err);
        });
    };
    if (web === "javlib") {
      // 开始执行对javlibrary的爬虫,第一步就是跳转
      const url =
        "https://www.javlibrary.com/cn/vl_searchbyid.php?keyword=" +
        String(serial_number);
      addPendingInNewWindow(url, "javlib");
    }
    if (web === "javdb") {
      // 开始执行对javdb的爬虫,第一步就是跳转
      const url = "https://javdb.com/search?q=" + String(serial_number);
      addPendingInNewWindow(url, "javdb");
    }
    if (web === "fanza") {
      // 开始执行对fanza的爬虫,第一步就是跳转
      const url =
        "https://www.dmm.co.jp/mono/-/search/=/searchstr=" +
        String(serial_number);
      addPendingInNewWindow(url, "fanza");
    }
    if (web === "javtxt") {
      const url =
        "https://javtxt.com/search?type=id&q=" +
        encodeURIComponent(String(serial_number));
      addPendingInNewWindow(url, "javtxt");
    }
    if (web === "avdanyuwiki") {
      const q = convertFanzaForAvdanyuwiki(String(serial_number));
      const url =
        "https://avdanyuwiki.com/?s=" + encodeURIComponent(q);
      addPendingInNewWindow(url, "avdanyuwiki");
    }
  }
  if (data.type === "fetch_cover_image") {
    const imageUrl = data.url;
    const request_id = data.request_id;
    if (imageUrl && request_id) {
      console.log("DarkEye: fetch_cover_image", request_id);
      fetchCoverImageForDesktop(imageUrl, request_id);
    }
  }
}

// 监听页面加载完成，启动对应爬虫 content script
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (
    changeInfo.status === "complete" &&
    crawlerWindowId !== null &&
    tab.windowId === crawlerWindowId
  ) {
    maybeNotifyCrawlerBacklog();
  }
  if (changeInfo.status === "complete" && pendingCrawlers.has(tabId)) {
    const task = pendingCrawlers.get(tabId);

    // 根据任务类型分发不同的指令，并透传 serial
    if (task.type === "javlib") {
      chrome.tabs.sendMessage(tabId, {
        command: "javlibrary-dvdid",
        serial: task.serial,
      });
      console.log("javlib爬虫开始:" + tabId);
    } else if (task.type === "javdb") {
      chrome.tabs.sendMessage(tabId, {
        command: "javdb-dvdid",
        serial: task.serial,
      });
      console.log("javdb爬虫开始:" + tabId);
    } else if (task.type === "fanza") {
      chrome.tabs.sendMessage(tabId, {
        command: "fanza-dvdid",
        serial: task.serial,
      });
      console.log("fanza爬虫开始:" + tabId);
    } else if (task.type === "javtxt") {
      chrome.tabs.sendMessage(tabId, {
        command: "javtxt-dvdid",
        serial: task.serial,
      });
      console.log("javtxt爬虫开始:" + tabId);
    } else if (task.type === "avdanyuwiki") {
      chrome.tabs.sendMessage(tabId, {
        command: "avdanyuwiki-dvdid",
        serial: task.serial,
      });
      console.log("avdanyuwiki爬虫开始:" + tabId);
    }

    // 注意：如果我们采用 Content Script 自动接力模式，这里可能不需要删除，每次刷新时判断有无任务，有就处理，直接任务全部结束
    // 为了防止多次触发，通常还是删除，依赖页面内的 sessionStorage 自动接力
    pendingCrawlers.delete(tabId);
  }
});

// 窗口关闭时重置专用爬虫窗口 ID（与 session 一致，含 SW 重启后仅 storage 有 ID 的情况）
chrome.windows.onRemoved.addListener(async (removedId) => {
  try {
    const data = await chrome.storage.session.get(CRAWLER_WINDOW_STORAGE_KEY);
    const stored = data[CRAWLER_WINDOW_STORAGE_KEY];
    if (removedId === crawlerWindowId || removedId === stored) {
      await clearCrawlerWindowPersistence();
      backlogWarningArmed = true;
    }
  } catch (e) {
    console.error("DarkEye: windows.onRemoved", e);
  }
});

chrome.tabs.onRemoved.addListener((tabId) => {
  tabNavigateContext.delete(tabId);
  if (crawlerWindowId !== null) {
    maybeNotifyCrawlerBacklog();
  }
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message && message.type === "sse_command" && message.payload) {
    try {
      handleCommand(message.payload);
    } catch (e) {
      console.error("DarkEye: Failed to handle SSE command", e);
    }
    return;
  }

  if (message.command === "check_existence") {
    // 批量检查番号是否存在于本地数据库
    fetch(`${SERVER_URL}/api/v1/check_existence`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ items: message.items }),
    })
      .then((res) => res.json())
      .then((data) => sendResponse(data))
      .catch((err) => sendResponse({ error: err.message }));

    return true; // Async response
  }

  if (message.command === "capture_item") {
    // 现在这个代码没有被调用，这个是用于批量抓取的
    fetch(`${SERVER_URL}/api/v1/capture`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(message.payload),
    })
      .then((res) => res.json())
      .then((data) => sendResponse(data))
      .catch((err) => sendResponse({ error: err.message }));

    return true; // Async response
  }

  if (message.command === "capture_one") {
    // 接受插件发来的单个id,然后发到本地，触发爬虫
    fetch(`${SERVER_URL}/api/v1/capture/one`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(message.payload),
    })
      .then((res) => res.json())
      .then((data) => sendResponse(data))
      .catch((err) => sendResponse({ error: err.message }));
    console.log("DarkEye: 抓取指令 to server", message);
    return true; // Async response
  }

  if (message.command === "get_tab_context") {
    const tabId = sender.tab && sender.tab.id;
    const ctx = tabId !== undefined ? tabNavigateContext.get(tabId) : undefined;
    sendResponse({ context: ctx || null });
    return false;
  }

  if (message.command === "capture_minnano_actress") {
    const tabId = sender.tab && sender.tab.id;
    const tabCtx =
      tabId !== undefined ? tabNavigateContext.get(tabId) || {} : {};
    const msgCtx = message.context || {};
    const context = Object.assign({}, tabCtx, msgCtx);
    const payload = {
      context,
      url: sender.tab && sender.tab.url ? sender.tab.url : "",
    };
    if (message.error) {
      payload.error = message.error;
    } else {
      payload.data = message.data;
    }
    fetch(`${SERVER_URL}/api/v1/minnano-actress-capture`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
      .then((response) => response.json())
      .then((data) => {
        console.log("DarkEye: minnano actress capture sent", data);
        sendResponse({ ok: true, data });
        if (
          context.persist &&
          !message.error &&
          tabId !== undefined
        ) {
          setTimeout(() => {
            chrome.tabs.remove(tabId);
          }, 10000);
        }
      })
      .catch((error) => {
        console.error("DarkEye: Failed to send minnano capture", error);
        sendResponse({ ok: false, error: String(error) });
      });
    return true;
  }

  if (message.command === "send_crawler_result") {
    console.log("发送爬虫的结果到本地服务器", message);
    // Send to local server
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
        console.log("DarkEye: ID sent to server", data);
        // Close the tab after successful send

        if (sender.tab && sender.tab.id) {
          setTimeout(() => {
            chrome.tabs.remove(sender.tab.id);
          }, 10000);
        }
      })
      .catch((error) => {
        console.error("DarkEye: Failed to send data", error);
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
    console.error("DarkEye: Failed to create offscreen document", e);
  }
}

chrome.runtime.onStartup.addListener(() => {
  ensureOffscreen();
  hydrateCrawlerWindowIdFromStorage();
});

chrome.runtime.onInstalled.addListener(() => {
  ensureOffscreen();
  hydrateCrawlerWindowIdFromStorage();
});

ensureOffscreen();
hydrateCrawlerWindowIdFromStorage();
