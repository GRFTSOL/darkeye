// Minnano：桌面下发 minnano-actress-auto → 自动采集；多条搜索失败；单条则跳转详情
(function () {
  if (!window.location.href.includes("minnano-av.com")) return;

  const STORAGE_KEY = "darkeye_minnano_auto";

  function reportFailure(err, ctx) {
    sessionStorage.removeItem(STORAGE_KEY);
    chrome.runtime.sendMessage({
      command: "capture_minnano_actress",
      error: err,
      context: ctx || {},
    });
  }

  function reportSuccess(data, ctx) {
    sessionStorage.removeItem(STORAGE_KEY);
    chrome.runtime.sendMessage({
      command: "capture_minnano_actress",
      data: data,
      context: ctx || {},
    });
  }

  function tryMinnanoAutoRun() {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return;

    let state;
    try {
      state = JSON.parse(raw);
    } catch (e) {
      sessionStorage.removeItem(STORAGE_KEY);
      return;
    }

    const ctx = Object.assign({ persist: true }, state.context || {});
    const Scrape = window.DarkEyeMinnanoScrape;
    if (!Scrape) {
      reportFailure("minnano_scrape_unavailable", ctx);
      return;
    }

    if (Scrape.isSearchResultsPage(document)) {
      const rows = document.querySelectorAll("td.details");
      const n = rows.length;
      if (n > 1) {
        reportFailure("multiple_search_results", ctx);
        return;
      }
      if (n === 1) {
        const a = document.querySelector("td.details h2.ttl a[href]");
        if (a && a.href) {
          window.location.assign(a.href);
          return;
        }
      }
      reportFailure("minnano_auto_no_match", ctx);
      return;
    }

    if (Scrape.isActressDetailPage(document)) {
      const data = Scrape.scrapeActressPage(document);
      reportSuccess(data, ctx);
      return;
    }

    reportFailure("minnano_auto_unexpected_page", ctx);
  }

  chrome.runtime.onMessage.addListener((message) => {
    if (message.command === "minnano-actress-auto") {
      const payload = {
        jpName: message.jpName,
        context: Object.assign({ persist: true }, message.context || {}),
      };
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
      tryMinnanoAutoRun();
    }
    return false;
  });

  function boot() {
    tryMinnanoAutoRun();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
