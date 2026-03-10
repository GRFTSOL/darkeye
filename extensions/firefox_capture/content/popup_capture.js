// Popup 采集：响应 capture-javdb / capture-javlibrary，仅在 JavDB、JavLibrary 注入
(function() {
  browser.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.command === "capture-javdb") {
      try {
        const results = captureDataJavdb();
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

  function captureDataJavdb() {
    const items = document.querySelectorAll('.item');
    const results = [];
    items.forEach((item) => {
      const scoreEl = item.querySelector('.score .value');
      let score = 0;
      if (scoreEl) {
        const match = scoreEl.textContent.trim().match(/([\d\.]+)/);
        if (match) score = parseFloat(match[1]);
      }
      if (score >= 4.5) {
        const titleEl = item.querySelector('.video-title');
        if (titleEl) {
          const strongEl = titleEl.querySelector('strong');
          if (strongEl) {
            let text = strongEl.textContent.trim();
            if (text) results.push({ serial: text, score: score });
          }
        }
      }
    });
    return results;
  }

  function captureDataJavlibrary() {
    const videos = document.querySelectorAll('div.video');
    const results = [];
    videos.forEach((video) => {
      const idEl = video.querySelector('div.id');
      if (idEl) {
        const serial = idEl.textContent.trim();
        if (serial) {
          results.push({ serial: serial, score: 0 });
        }
      }
    });
    return results;
  }
})();
