// background.js for Firefox (Manifest V2)
const SERVER_URL = "http://localhost:56789";
const SSE_URL = `${SERVER_URL}/events`;

let eventSource = null;

function connectSSE() {
  if (eventSource) {
    eventSource.close();
  }

  try {//失败后一直会重试下去。保证了桌面软件重启后还能连上
      console.log("DarkEye: Connecting to SSE server at " + SSE_URL);
      eventSource = new EventSource(SSE_URL);

      eventSource.onopen = () => {
        console.log("DarkEye: Connected to SSE server");
      };
      
      //有新消息的时候会触发这个事件
      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log("DarkEye: Received command", data);
          handleCommand(data);
        } catch (e) {
          console.error("DarkEye: Error parsing SSE message", e);
        }
      };

      //错误的时候会触发这个事件
      eventSource.onerror = (err) => {
        console.error("DarkEye: SSE Error", err);
        eventSource.close();
        setTimeout(connectSSE, 5000);
      };

  } catch (e) {
      console.error("DarkEye: Failed to create EventSource", e);
      setTimeout(connectSSE, 5000);
  }
}

/** 与 ``utils.serial_number.convert_fanza`` 一致，供 avdanyuwiki 首跳搜索串。 */
function convertFanzaForAvdanyuwiki(serial_number) {
  let converted_code = String(serial_number).toLowerCase().replace(/-/g, "00");
  const halfCoverPrefixes = ["start", "stars", "star", "sdde", "kmhrs"];
  const fullCoverPrefixes = [
    "namh", "dldss", "fns", "fsdss", "boko", "sdam", "hawa", "moon", "mogi", "nhdtb",
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
/** work_merge_fetch：request_id -> { serial, perSite, tabIds, mergeRequestId, ... } */
const workMergeJobs = new Map();
/** 合并层需要的四站键（merge_work.js 与 merge_service 一致） */
const WORK_MERGE_SITES_ALL = ["javlib", "javdb", "javtxt", "avdanyuwiki"];

/** 以下前缀只开 javdb + javtxt + avdanyuwiki（不开 javlib） */
const MERGE_PREFIX_THREE_NO_JAVLIB = [
  "LUXU",
  "SIRO",
  "GANA",
  "MIUM",
  "ARA",
  "MAAN",
  "NAMA",
  "HON",
  "DCV",
  "NTK",
  "AKO",
  "LADY",
  "SUKE",
  "AHSHIRO",
  "POW"
];

/**
 * 去掉 `-`、`_` 后若整串为纯数字（0-9），视为仅适合 javdb 检索的形态。
 */
function isDigitsOnlyAfterStripHyphens(serial) {
  const compact = String(serial).trim().replace(/[-_]/g, "");
  return compact.length > 0 && /^\d+$/.test(compact);
}

/**
 * 按番号前缀决定要开的爬虫标签（未匹配的番号默认四站全开）。
 * 例：FC2/HEYZO 只 javdb；纯数字只 javdb；MERGE_PREFIX_THREE_NO_JAVLIB 只三站（不开 javlib）。
 */
function resolveMergeSitesForSerial(serial) {
  const raw = String(serial).trim();
  if (!raw) return WORK_MERGE_SITES_ALL.slice();
  const u = raw.toUpperCase();
  if (u.startsWith("FC2") || u.startsWith("HEYZO")) {
    return ["javdb"];
  }
  if (isDigitsOnlyAfterStripHyphens(raw)) {
    return ["javdb"];
  }
  if (MERGE_PREFIX_THREE_NO_JAVLIB.some((p) => u.startsWith(p))) {
    return ["javdb", "javtxt", "avdanyuwiki"];
  }
  return WORK_MERGE_SITES_ALL.slice();
}

/** 单站超过此时长无结果则视为放弃该站，用空对象参与合并（与服务端 GET 120s 总超时配合） */
const WORK_MERGE_PER_SITE_MS = 30000;

/** 桌面 navigate 写入：tabId -> { actress_id?, source? } */
const tabNavigateContext = new Map();

let crawlerWindowId = null; // 专用爬虫窗口 ID
let crawlerWindowPromise = null; // 创建中的窗口 Promise，避免多任务同时开多个窗口

/** 专用窗口内标签总数达到该值时通知桌面（去重：跌破后再回升才再报） */
const CRAWLER_BACKLOG_THRESHOLD = 13;//正常情况下大于10个就通知桌面
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
  const minBytes = 5 * 1024;//小于5kb的图片认为是下载失败
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

function postWorkMergeResult(payload) {
  return fetch(`${SERVER_URL}/api/v1/work-merge-result`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
    .then((r) => r.json())
    .catch((err) => {
      console.error("DarkEye: work-merge-result failed", err);
      throw err;
    });
}

function clearWorkMergeTimer(job) {
  if (job && job.mergeTimeoutId != null) {
    clearTimeout(job.mergeTimeoutId);
    job.mergeTimeoutId = null;
  }
}

function finishWorkMergeJob(requestId, ok, merged, serial, error) {
  const job = workMergeJobs.get(requestId);
  if (job) clearWorkMergeTimer(job);
  const tabIds = job && job.tabIds ? job.tabIds.slice() : [];
  workMergeJobs.delete(requestId);
  postWorkMergeResult({
    request_id: requestId,
    ok,
    merged: merged || null,
    per_site: {},
    error: error || null,
    serial_number: serial || "",
  })
    .then(() => {
      tabIds.forEach((tid) => {
        if (tid !== undefined) {
          browser.tabs.remove(tid).catch(() => {});
        }
      });
    })
    .catch(() => {});
}

function runWorkMergeAndFinish(requestId) {
  const job = workMergeJobs.get(requestId);
  if (!job || job.finalized) return;
  job.finalized = true;
  clearWorkMergeTimer(job);

  let merged = null;
  let ok = true;
  let errMsg = null;
  try {
    for (const k of WORK_MERGE_SITES_ALL) {
      if (!Object.prototype.hasOwnProperty.call(job.perSite, k)) {
        job.perSite[k] = {};
      }
    }
    let snapshot = {};
    try {
      snapshot = JSON.parse(JSON.stringify(job.perSite));
    } catch (e) {
      snapshot = Object.assign({}, job.perSite);
    }
    merged = mergeCrawlResultsNoTranslate(snapshot, job.serial);
  } catch (e) {
    ok = false;
    errMsg = String(e);
    console.error("DarkEye: mergeCrawlResultsNoTranslate", e);
  }
  finishWorkMergeJob(requestId, ok, merged, job.serial, errMsg);
}

function onWorkMergeSiteResult(requestId, web, data) {
  const job = workMergeJobs.get(requestId);
  if (!job || job.finalized) return;
  job.perSite[web] = data && typeof data === "object" ? data : {};
  const sites = job.sites || WORK_MERGE_SITES_ALL;
  const n = sites.filter((k) =>
    Object.prototype.hasOwnProperty.call(job.perSite, k)
  ).length;
  if (n < sites.length) return;
  runWorkMergeAndFinish(requestId);
}

function onWorkMergePerSiteTimeout(requestId) {
  const job = workMergeJobs.get(requestId);
  if (!job || job.finalized) return;
  console.warn(
    "DarkEye: work_merge 单站 " +
      WORK_MERGE_PER_SITE_MS / 1000 +
      "s 内未返回的源将按空对象合并 request_id=" +
      requestId
  );
  runWorkMergeAndFinish(requestId);
}

function startWorkMergeFetch(requestId, serial) {
  const sites = resolveMergeSitesForSerial(serial);
  workMergeJobs.set(requestId, {
    serial: String(serial),
    sites,
    perSite: {},
    tabIds: [],
    mergeRequestId: requestId,
    mergeTimeoutId: null,
    finalized: false,
  });
  console.log("DarkEye: work_merge 启用站点", sites.join(","), "serial=", serial);
  const urls = {
    javlib:
      "https://www.javlibrary.com/cn/vl_searchbyid.php?keyword=" +
      String(serial),
    javdb: "https://javdb.com/search?q=" + String(serial),
    javtxt:
      "https://javtxt.com/search?type=id&q=" +
      encodeURIComponent(String(serial)),
    avdanyuwiki:
      "https://avdanyuwiki.com/?s=" +
      encodeURIComponent(convertFanzaForAvdanyuwiki(String(serial))),
  };

  const addPendingInNewWindowMerge = (url, type) => {
    const mergeRequestId = requestId;
    const serial_number = serial;
    const addTab = (windowId) => {
      return browser.tabs
        .create({ windowId, url, active: false })
        .then((tab) => {
          if (tab && tab.id !== undefined) {
            pendingCrawlers.set(tab.id, {
              type,
              serial: serial_number,
              context: {},
              mergeRequestId,
            });
            const job = workMergeJobs.get(mergeRequestId);
            if (job) job.tabIds.push(tab.id);
          }
          return maybeNotifyCrawlerBacklog();
        })
        .catch((err) => {
          console.error("DarkEye: 爬虫窗口可能已被关闭，重新创建", err);
          crawlerWindowId = null;
          crawlerWindowPromise = null;
          addPendingInNewWindowMerge(url, type);
        });
    };

    if (crawlerWindowId !== null) {
      addTab(crawlerWindowId);
      return;
    }
    if (crawlerWindowPromise === null) {
      const crawlerHomeUrl = "https://www.baidu.com";
      crawlerWindowPromise = browser.windows
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
          console.error("DarkEye: 创建爬虫窗口失败", err);
          crawlerWindowPromise = null;
          throw err;
        });
    }
    crawlerWindowPromise.then((windowId) => addTab(windowId));
  };

  sites.forEach((w) => addPendingInNewWindowMerge(urls[w], w));

  const j = workMergeJobs.get(requestId);
  if (j) {
    j.mergeTimeoutId = setTimeout(
      () => onWorkMergePerSiteTimeout(requestId),
      WORK_MERGE_PER_SITE_MS
    );
  }
}

function maybeNotifyCrawlerBacklog() {
  if (crawlerWindowId === null) {
    return Promise.resolve();
  }
  return browser.tabs
    .query({ windowId: crawlerWindowId })
    .then((tabs) => {
      const count = tabs.length;
      if (count >= CRAWLER_BACKLOG_THRESHOLD && backlogWarningArmed) {
        backlogWarningArmed = false;
        fetch(`${SERVER_URL}/api/v1/crawler-backlog-warning`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            browser: "firefox",
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

/**
 * HTTP GET /api/v1/actress/{jp}：与 startcrawler minnano 一致，可有 minnano_url 直达详情；
 * context 带 actress_http_request_id，回传走 /api/v1/actress-fetch-result（persist: false）。
 */
function startMinnanoActressHttpFetch(requestId, actressJpName, minnanoUrlFragment) {
  const jp = String(actressJpName || "").trim();
  if (!jp) return;
  const mid = String(minnanoUrlFragment || "").trim();
  let url;
  if (mid) {
    url = "https://www.minnano-av.com/actress" + mid + ".html";
  } else {
    url =
      "https://www.minnano-av.com/search_result.php?search_scope=actress&search_word=" +
      encodeURIComponent(jp) +
      "&search=+Go+";
  }
  const httpCtx = {
    actress_http_request_id: String(requestId),
    persist: false,
    actress_jp_name: jp,
  };
  if (mid) {
    httpCtx.minnano_url = mid;
  }
  const addPendingInNewWindow = (openUrl, type) => {
    const addTab = (windowId) => {
      return browser.tabs
        .create({ windowId, url: openUrl, active: false })
        .then((tab) => {
          if (tab && tab.id !== undefined) {
            pendingCrawlers.set(tab.id, {
              type,
              serial: jp,
              context: httpCtx,
            });
          }
          return maybeNotifyCrawlerBacklog();
        })
        .catch((err) => {
          console.error("DarkEye: 爬虫窗口可能已被关闭，重新创建", err);
          crawlerWindowId = null;
          crawlerWindowPromise = null;
          addPendingInNewWindow(openUrl, type);
        });
    };

    if (crawlerWindowId !== null) {
      addTab(crawlerWindowId);
      return;
    }
    if (crawlerWindowPromise === null) {
      const crawlerHomeUrl = "https://www.baidu.com";
      crawlerWindowPromise = browser.windows
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
          console.error("DarkEye: 创建爬虫窗口失败", err);
          crawlerWindowPromise = null;
          throw err;
        });
    }
    crawlerWindowPromise.then((windowId) => addTab(windowId));
  };
  addPendingInNewWindow(url, "minnano");
  console.log("DarkEye: minnano_actress_fetch", requestId, jp);
}

/**
 * HTTP GET /api/v1/top-actresses：打开 javtxt 热门页，回传走 /api/v1/top-actresses-result。
 */
function startJavtxtTopActressesHttpFetch(requestId) {
  const rid = String(requestId || "").trim();
  if (!rid) return;
  const url = "https://javtxt.com/top-actresses";
  const addPendingInNewWindow = (openUrl, type) => {
    const addTab = (windowId) => {
      return browser.tabs
        .create({ windowId, url: openUrl, active: false })
        .then((tab) => {
          if (tab && tab.id !== undefined) {
            pendingCrawlers.set(tab.id, {
              type,
              serial: "",
              context: {},
              apiRequestId: rid,
            });
          }
          return maybeNotifyCrawlerBacklog();
        })
        .catch((err) => {
          console.error("DarkEye: 爬虫窗口可能已被关闭，重新创建", err);
          crawlerWindowId = null;
          crawlerWindowPromise = null;
          addPendingInNewWindow(openUrl, type);
        });
    };

    if (crawlerWindowId !== null) {
      addTab(crawlerWindowId);
      return;
    }
    if (crawlerWindowPromise === null) {
      const crawlerHomeUrl = "https://www.baidu.com";
      crawlerWindowPromise = browser.windows
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
          console.error("DarkEye: 创建爬虫窗口失败", err);
          crawlerWindowPromise = null;
          throw err;
        });
    }
    crawlerWindowPromise.then((windowId) => addTab(windowId));
  };
  addPendingInNewWindow(url, "javtxt-top-actresses");
  console.log("DarkEye: javtxt_top_actresses_fetch", rid);
}

function handleCommand(data) {//处理服务器发送来的命令
  if (data.type === "navigate") {
    const url = data.url;
    const target = data.target || "new_tab";
    const ctx = data.context || null;

    if (target === "new_tab") {
      browser.tabs.create({ url: url }).then((tab) => {
          if (ctx != null && tab && tab.id !== undefined) {
            tabNavigateContext.set(tab.id, ctx);
          }
      });
    } else if (target === "current_tab") {
        browser.tabs.query({active: true, currentWindow: true}).then((tabs) => {
            if (tabs[0]) {
                const tid = tabs[0].id;
                browser.tabs.update(tid, { url: url }).then(() => {
                  if (ctx != null) tabNavigateContext.set(tid, ctx);
                });
            }
        });
    }
  }
  if (data.type === "work_merge_fetch") {
    const requestId = data.request_id;
    const serial = data.serial_number;
    if (requestId && serial != null && serial !== "") {
      console.log("DarkEye: work_merge_fetch", requestId, serial);
      startWorkMergeFetch(String(requestId), serial);
    }
  }
  if (data.type === "minnano_actress_fetch") {
    const requestId = data.request_id;
    const name = data.actress_jp_name;
    const minnanoUrl =
      data.minnano_url != null && data.minnano_url !== undefined
        ? String(data.minnano_url)
        : "";
    if (requestId && name != null && String(name).trim() !== "") {
      startMinnanoActressHttpFetch(String(requestId), String(name), minnanoUrl);
    }
  }
  if (data.type === "javtxt_top_actresses_fetch") {
    const requestId = data.request_id;
    if (
      requestId != null &&
      requestId !== undefined &&
      String(requestId).trim() !== ""
    ) {
      startJavtxtTopActressesHttpFetch(String(requestId));
    }
  }
  if (data.type==="crawler"){
    const web = data.web;
    const serial_number = data.serial_number;
    const crawlerContext = data.context || {};
    // 爬虫统一在专用窗口后台打开，不影响当前浏览窗口
    const addPendingInNewWindow = (url, type) => {
      const addTab = (windowId) => {
        return browser.tabs.create({ windowId, url, active: false })
          .then((tab) => {
            if (tab && tab.id !== undefined) {
              pendingCrawlers.set(tab.id, {
                type,
                serial: serial_number,
                context: crawlerContext,
              });
            }
            return maybeNotifyCrawlerBacklog();
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
      const url = "https://javdb.com/search?q="+String(serial_number);
      addPendingInNewWindow(url, "javdb");
    }
    if (web==="fanza"){//开始执行对fanza的爬虫,第一步就是跳转
      const url = "https://www.dmm.co.jp/mono/-/search/=/searchstr="+String(serial_number);
      addPendingInNewWindow(url, "fanza");
    }
    if (web==="javtxt"){
      const url = "https://javtxt.com/search?type=id&q="+encodeURIComponent(String(serial_number));
      addPendingInNewWindow(url, "javtxt");
    }
    if (web === "javtxt-top-actresses") {
      const url = "https://javtxt.com/top-actresses";
      addPendingInNewWindow(url, "javtxt-top-actresses");
    }
    if (web==="avdanyuwiki"){
      const q = convertFanzaForAvdanyuwiki(String(serial_number));
      const url = "https://avdanyuwiki.com/?s=" + encodeURIComponent(q);
      addPendingInNewWindow(url, "avdanyuwiki");
    }
    if (web === "minnano") {
      const ctx = crawlerContext || {};
      const mid = (ctx.minnano_url && String(ctx.minnano_url).trim()) || "";
      let url;
      if (mid) {
        url = "https://www.minnano-av.com/actress" + mid + ".html";
      } else {
        url =
          "https://www.minnano-av.com/search_result.php?search_scope=actress&search_word=" +
          encodeURIComponent(String(serial_number)) +
          "&search=+Go+";
      }
      addPendingInNewWindow(url, "minnano");
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

/**
 * minnano：complete 有时早于 content script 注册 onMessage，导致 sendMessage 丢包。
 * 使用有限次重试（间隔递增）。
 */
function sendMinnanoActressAutoMessage(tabId, msg, serial) {
  const maxAttempts = 6;
  function trySend(attemptNum) {
    browser.tabs
      .sendMessage(tabId, msg)
      .then(() => {
        console.log(
          "DarkEye: minnano sendMessage ok tabId=",
          tabId,
          "jp=",
          serial,
          "attempt=",
          attemptNum
        );
      })
      .catch((err) => {
        if (attemptNum < maxAttempts) {
          const wait = 100 * attemptNum;
          console.warn(
            "DarkEye: minnano sendMessage failed; retry",
            attemptNum + 1,
            "in",
            wait,
            "ms",
            err
          );
          setTimeout(() => trySend(attemptNum + 1), wait);
        } else {
          console.error(
            "DarkEye: minnano sendMessage FAILED after",
            maxAttempts,
            "attempts tabId=",
            tabId,
            err
          );
        }
      });
  }
  trySend(1);
}

// 监听页面加载完成，启动对应爬虫 content script
browser.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (
    changeInfo.status === "complete" &&
    crawlerWindowId !== null &&
    tab.windowId === crawlerWindowId
  ) {
    maybeNotifyCrawlerBacklog();
  }
  if (changeInfo.status === 'complete' && pendingCrawlers.has(tabId)) {
    const task = pendingCrawlers.get(tabId);
    if (task.type === "minnano") {
      console.log(
        "DarkEye: minnano tab complete tabId=",
        tabId,
        "url=",
        tab && tab.url
      );
    }

    // 根据任务类型分发不同的指令，并透传 serial
    if (task.type === "javlib") {
        const msg = { command: "javlibrary-dvdid", serial: task.serial };
        if (task.mergeRequestId) msg.mergeRequestId = task.mergeRequestId;
        browser.tabs.sendMessage(tabId, msg);
        console.log("javlib爬虫开始:" + tabId);
    } else if (task.type === "javdb") {
        const msg = { command: "javdb-dvdid", serial: task.serial };
        if (task.mergeRequestId) msg.mergeRequestId = task.mergeRequestId;
        browser.tabs.sendMessage(tabId, msg);
        console.log("javdb爬虫开始:" + tabId);
    } else if(task.type === "fanza"){
      browser.tabs.sendMessage(tabId, { command: "fanza-dvdid", serial: task.serial });
      console.log("fanza爬虫开始:" + tabId);
    } else if (task.type === "javtxt") {
        const msg = { command: "javtxt-dvdid", serial: task.serial };
        if (task.mergeRequestId) msg.mergeRequestId = task.mergeRequestId;
        browser.tabs.sendMessage(tabId, msg);
      console.log("javtxt爬虫开始:" + tabId);
    } else if (task.type === "javtxt-top-actresses") {
      const msg = { command: "javtxt-parse-top-actresses" };
      if (task.apiRequestId) {
        msg.request_id = task.apiRequestId;
      }
      browser.tabs.sendMessage(tabId, msg);
      console.log("javtxt top-actresses:" + tabId);
    } else if (task.type === "avdanyuwiki") {
        const msg = { command: "avdanyuwiki-dvdid", serial: task.serial };
        if (task.mergeRequestId) msg.mergeRequestId = task.mergeRequestId;
        browser.tabs.sendMessage(tabId, msg);
      console.log("avdanyuwiki爬虫开始:" + tabId);
    } else if (task.type === "minnano") {
      const msg = {
        command: "minnano-actress-auto",
        jpName: task.serial,
        context: Object.assign({ persist: true }, task.context || {}),
      };
      sendMinnanoActressAutoMessage(tabId, msg, task.serial);
      console.log("minnano爬虫开始:" + tabId);
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
    backlogWarningArmed = true;
  }
});

browser.tabs.onRemoved.addListener((tabId) => {
  tabNavigateContext.delete(tabId);
  if (crawlerWindowId !== null) {
    maybeNotifyCrawlerBacklog();
  }
});

// 接收 content script 消息，转发到本地服务器
browser.runtime.onMessage.addListener((message, sender, sendResponse) => {//这个是向服务器发送的消息
    if (message.command === "check_existence") {
        // 批量检查番号是否存在于本地数据库
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
        // 现在这个代码没有被调用，这个是用于批量抓取的
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
        // 接受插件发来的单个id,然后发到本地，触发爬虫
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
    if (message.command === "get_tab_context") {
        const tabId = sender.tab && sender.tab.id;
        const ctx = tabId !== undefined ? tabNavigateContext.get(tabId) : undefined;
        sendResponse({ context: ctx || null });
        return false;
    }
    if (message.command === "capture_minnano_actress") {
        const tabId = sender.tab && sender.tab.id;
        const tabCtx = tabId !== undefined ? (tabNavigateContext.get(tabId) || {}) : {};
        const msgCtx = message.context || {};
        const context = Object.assign({}, tabCtx, msgCtx);
        const httpRid = context.actress_http_request_id;
        if (httpRid) {
            const syncBody = {
                request_id: String(httpRid),
                ok: !message.error,
                actress_jp_name: context.actress_jp_name || null,
                data: message.error ? null : message.data,
                error: message.error || null,
            };
            fetch(`${SERVER_URL}/api/v1/actress-fetch-result`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(syncBody),
            })
                .then((response) => {
                    if (!response.ok) {
                        throw new Error(`HTTP ${response.status}`);
                    }
                    return response.json();
                })
                .then((data) => {
                    console.log("DarkEye: actress-fetch-result sent", data);
                    sendResponse({ ok: true, data });
                    // GET /api/v1/actress/... 同步查询：回传成功后关闭女优标签
                    if (sender.tab && sender.tab.id !== undefined) {
                        const tid = sender.tab.id;
                        setTimeout(() => {
                            browser.tabs.remove(tid).catch(() => {});
                        }, 3000);
                    }
                })
                .catch((error) => {
                    console.error("DarkEye: Failed to send actress-fetch-result", error);
                    sendResponse({ ok: false, error: String(error) });
                });
            return true;
        }
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
                // 桌面「单个女优」自动爬取（persist）：回传成功后与 send_crawler_result 一致，延迟关标签
                const mergedCtx = Object.assign({}, tabCtx, msgCtx);
                if (
                    mergedCtx.persist &&
                    !message.error &&
                    sender.tab &&
                    sender.tab.id !== undefined
                ) {
                    const tid = sender.tab.id;
                    setTimeout(() => {
                        browser.tabs.remove(tid);
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
        if (message.merge_request_id && message.web) {
            const rid = message.merge_request_id;
            const web = message.web;
            if (WORK_MERGE_SITES_ALL.indexOf(web) >= 0) {
                const job = workMergeJobs.get(rid);
                if (
                    job &&
                    job.sites &&
                    job.sites.indexOf(web) >= 0
                ) {
                    onWorkMergeSiteResult(rid, web, message.data || {});
                }
                return false;
            }
        }
        const topApiRid =
            message.web === "javtxt-top-actresses" && message.request_id
                ? String(message.request_id).trim()
                : "";
        console.log("发送爬虫的结果到本地服务器", message);
        const inner = message.data || {};
        const names = Array.isArray(inner.names) ? inner.names : [];
        const topPayload =
            topApiRid !== ""
                ? {
                      request_id: topApiRid,
                      ok: !!message.result,
                      names: names,
                  }
                : null;
        if (topPayload && inner.error) {
            topPayload.error = String(inner.error);
        }
        const postUrl =
            topApiRid !== ""
                ? `${SERVER_URL}/api/v1/top-actresses-result`
                : `${SERVER_URL}/api/v1/crawler-result`;
        const postBody =
            topApiRid !== ""
                ? JSON.stringify(topPayload)
                : JSON.stringify({
                      results: message.result,
                      id: message.id,
                      web: message.web,
                      data: message.data,
                  });
        fetch(postUrl, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: postBody,
        })
        .then(response => response.json())
        .then(data => {
            console.log("DarkEye: ID sent to server", data);
            // Close the tab after successful send

            if (sender.tab && sender.tab.id) {
                setTimeout(() => {
                    browser.tabs.remove(sender.tab.id);
                }, 10000);
            }
        })
        .catch(error => {
            console.error("DarkEye: Failed to send data", error);
        });
    }
});

// Initial connect
// ion
connectSSE();