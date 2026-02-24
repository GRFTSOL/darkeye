// 作品番号探测器：JavDB / JavLibrary / JavTxt 列表页「已收录 / + 收藏」标签
(function() {
    const href = window.location.href;
    if (!href.includes("javdb.com") && !href.includes("javlibrary.com") && !href.includes("javtxt.com")) {
        return;
    }

    const State = {
        pendingItems: new Map(),
        checkQueue: new Set(),
        checkTimer: null
    };

    class SiteSniffer {
        constructor() {
            this.observer = null;
        }

        /** 标签位置：'top-left' | 'bottom-right'，子类可覆盖 */
        getTagPosition() {
            return 'top-left';
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
            this.observer = new MutationObserver((mutations) => {
                mutations.forEach((mutation) => {
                    mutation.addedNodes.forEach((node) => {
                        if (node.nodeType === 1) {
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

        startProcessor() {}

        processItem(element) {
            if (element.dataset.darkeyeProcessed) return;
            const id = this.extractId(element);
            console.log("DarkEye: 提取到ID:", id);
            if (!id) return;

            element.dataset.darkeyeProcessed = "true";
            State.pendingItems.set(id, { element });
            State.checkQueue.add(id);
            this.scheduleCheck();
        }

        scheduleCheck() {
            if (State.checkTimer) clearTimeout(State.checkTimer);
            State.checkTimer = setTimeout(() => this.performCheck(), 500);
        }

        async performCheck() {
            if (State.checkQueue.size === 0) return;
            const ids = Array.from(State.checkQueue);
            State.checkQueue.clear();

            try {
                const response = await browser.runtime.sendMessage({
                    command: "check_existence",
                    items: ids
                });
                if (response && response.results) {
                    Object.entries(response.results).forEach(([id, exists]) => {
                        console.log("DarkEye:更新UI");
                        this.updateUI(id, exists);
                    });
                }
            } catch (e) {
                console.error("DarkEye: Check existence failed", e);
            }
        }

        updateUI(id, exists) {
            const item = State.pendingItems.get(id);
            if (!item) return;
            const { element } = item;

            const tag = document.createElement("div");
            tag.className = "darkeye-tag darkeye-tag--" + this.getTagPosition();
            if (exists) {
                tag.classList.add("exists");
                tag.textContent = "已收录";
                tag.title = "本地已收录";
            } else {
                tag.classList.add("not-found");
                tag.textContent = "+ 收藏";
                tag.title = "点击采集到本地";
                tag.onclick = (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    this.captureItem(tag, id, element);
                };
            }

            if (getComputedStyle(element).position === 'static') {
                element.style.position = 'relative';
            }
            element.appendChild(tag);
            // 若容器是 <a>（如 javtxt 的 a.work），在冒泡阶段拦截，只拦跳转、不拦标签自身的点击
            if (element.tagName === 'A' && !element.dataset.darkeyeClickBound) {
                element.dataset.darkeyeClickBound = '1';
                element.addEventListener('click', (e) => {
                    if (e.target.closest('.darkeye-tag')) {
                        e.preventDefault();
                        e.stopPropagation();
                    }
                }, false);
            }
            console.log("DarkEye: 注入标签:", tag);
        }

        async captureItem(tag, id, element) {
            tag.classList.remove("not-found");
            tag.classList.add("loading");
            tag.textContent = "发送中...";

            try {
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
                    tag.onclick = null;
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
            const titleStrong = element.querySelector(".video-title strong");
            if (titleStrong) return titleStrong.textContent.trim();
            return null;
        }
    }

    class JavLibrarySniffer extends SiteSniffer {
        constructor() {
            super();
            this.itemSelector = ".video";
        }
        extractId(element) {
            const titleStrong = element.querySelector(".id");
            if (titleStrong) return titleStrong.textContent.trim();
            return null;
        }
    }

    class JavTxtSniffer extends SiteSniffer {
        constructor() {
            super();
            this.itemSelector = "a.work";
        }
        getTagPosition() {
            return 'bottom-right';
        }
        extractId(element) {
            const workIdEl = element.querySelector(".work-id");
            if (!workIdEl) return null;
            // 番号在 .work-id 内，后面可能有 .work-actress 等，取第一个空白前的 token（如 SNOS-079）
            const raw = workIdEl.textContent.trim();
            const first = raw.split(/\s+/)[0];
            return first || null;
        }
    }

    let activeSniffer = null;
    const url = window.location.href;
    if (url.includes("javdb.com")) {
        activeSniffer = new JavDBSniffer();
    } else if (url.includes("javlibrary.com")) {
        activeSniffer = new JavLibrarySniffer();
    } else if (url.includes("javtxt.com")) {
        activeSniffer = new JavTxtSniffer();
    }

    if (activeSniffer) {
        console.log("DarkEye: 启动嗅探器");
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => activeSniffer.init());
        } else {
            activeSniffer.init();
        }
    }
})();
