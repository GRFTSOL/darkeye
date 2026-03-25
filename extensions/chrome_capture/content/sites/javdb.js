//javdb的站点有一个问题，就是图片有水印，作为封面无法使用。
//优点就是资源比较全，有javlib没有的一些资源。

// JavLibrary 站点：dvdid 搜索、解析、自动续跑
(function() {
    const api = chrome || browser;
    if (!window.location.href.includes("javdb.com")) return;
  
    api.runtime.onMessage.addListener((message, sender, sendResponse) => {
      if (message.command === "javdb-dvdid"){
          sessionStorage.setItem('darkeye_auto_parse', 'true')
          sessionStorage.setItem('id', message.serial)
          if (!search_javdb()){
              //这里回传失败的信息
          }
      }
    });
  
    function search_javdb(){//先解析多个结果，然后根据番号选择，找到目标页面，然后跳转后详细解析
        console.log("开始搜索javdb");
        const videos = document.querySelectorAll('div.item');
        if (videos.length === 0) {
            if (document.title.includes("Just a moment") || document.title.includes("Attention Required") || document.querySelector('#challenge-running')) {
                console.log("DarkEye: 遇到 Cloudflare，暂不报错，等待自动重试...");
                sessionStorage.setItem('darkeye_auto_parse', 'true');
                return false;
            }
            console.log("该番号javdb没有搜索结果");
            sessionStorage.setItem('darkeye_auto_parse', 'false')
            api.runtime.sendMessage({
                command: "send_crawler_result",
                id: sessionStorage.getItem('id'),
                web:'javdb',
                result: false,
                data:{}
            });
            return false;
        }
        console.log("搜索结果个数: " + videos.length);
        const results = Array.from(videos).map(video => {
            const idDiv = video.querySelector('.video-title strong');
            const titleContainer = video.querySelector('.video-title');
            const link = video.querySelector('a.box');

            let titleText = "";
            if (titleContainer) {
                const clone = titleContainer.cloneNode(true);
                const strongEl = clone.querySelector('strong');
                if (strongEl) strongEl.remove();
                titleText = clone.textContent.trim();
            }

            const href = link ? link.getAttribute('href') : "";

            return {
                id: idDiv ? idDiv.textContent.trim() : "",
                title: titleText,
                url: href ? `https://javdb.com${href}` : ""
            };
        });
        const searchId = (sessionStorage.getItem('id') || "").trim().toUpperCase();
        let targetUrl = null;

        if (searchId) {
            const matched = results.find(item => (item.id || "").trim().toUpperCase() === searchId);
            if (matched) {
                targetUrl = matched.url;
            }
        }

        if (!targetUrl && results.length > 0) {
            targetUrl = results[0].url;
        }
        if (targetUrl) {
            sessionStorage.setItem('darkeye_auto_parse', 'true');
            window.location.href = targetUrl;
            parse_data_javdb();
        }

    }
  
    function parse_data_javdb(){ // 这个是解析 JavDB 详细页
      if (window.location.href.includes("javdb.com")) {
          const videoDetail = document.querySelector(".video-detail");
          if (!videoDetail) return;

          const data = {};

          // 番号：h2.title 里第一个 strong
          const idStrong = videoDetail.querySelector("h2.title strong");
          if (idStrong) {
              let idText = idStrong.textContent.trim();
              idText = idText.replace(/\s+$/,""); // 去掉末尾空格
              idText = idText.endsWith('v') ? idText.slice(0, -1) : idText;
              data.id = idText;
          } else {
              data.id = "";
          }
          console.log("番号: " + data.id);

          // 标题：优先当前显示标题（中文），否则用原始标题（日文）
          const currentTitleEl = videoDetail.querySelector("h2.title strong.current-title");
          const originTitleEl = videoDetail.querySelector("h2.title .origin-title");
          if (currentTitleEl) {
              data.title = currentTitleEl.textContent.trim();
          } else if (originTitleEl) {
              data.title = originTitleEl.textContent.trim();
          } else {
              data.title = "";
          }
          console.log("标题: " + data.title);

          // 面板块集合
          const panelBlocks = videoDetail.querySelectorAll(".movie-panel-info .panel-block");
          const getPanelValue = (labelText) => {
              for (const block of panelBlocks) {
                  const strongEl = block.querySelector("strong");
                  if (!strongEl) continue;
                  if (strongEl.textContent.trim().startsWith(labelText)) {
                      const val = block.querySelector(".value");
                      return val ? val.textContent.trim() : "";
                  }
              }
              return "";
          };

          data.release_date = getPanelValue("日期:");
          data.length = getPanelValue("時長:");
          data.director = getPanelValue("導演:");
          data.maker = getPanelValue("片商:");
          data.label = getPanelValue("發行:");
          data.series=getPanelValue("系列:");

          // 类别
          const genreBlock = Array.from(panelBlocks).find(block => {
              const strongEl = block.querySelector("strong");
              return strongEl && strongEl.textContent.trim().startsWith("類別:");
          });
          if (genreBlock) {
              const genreLinks = genreBlock.querySelectorAll(".value a");
              data.genre = Array.from(genreLinks).map(el => el.textContent.trim());
          } else {
              data.genre = [];
          }

          // 演员：按 strong.symbol.female / strong.symbol.male 区分女优与男优
          const castBlock = Array.from(panelBlocks).find(block => {
              const strongEl = block.querySelector("strong");
              return strongEl && strongEl.textContent.trim().startsWith("演員:");
          });
          data.actress = [];
          data.actor = [];
          if (castBlock) {
              const valueEl = castBlock.querySelector(".value");
              if (valueEl) {
                  const links = valueEl.querySelectorAll("a");
                  for (const a of links) {
                      const name = a.textContent.trim();
                      if (!name) continue;
                      const next = a.nextElementSibling;
                      if (next && next.classList.contains("symbol")) {
                          if (next.classList.contains("female")) {
                              data.actress.push(name);
                          } else if (next.classList.contains("male")) {
                              data.actor.push(name);
                          }
                      } else {
                          data.actress.push(name);
                      }
                  }
              }
          }

          // 封面
          //const imgElement = videoDetail.querySelector(".video-cover");
          //data.image = imgElement ? imgElement.src : "";

          sessionStorage.setItem('darkeye_auto_parse', 'false');
          console.log(data);
          if (data) {
              console.debug("发送数据");
              api.runtime.sendMessage({
                  command: "send_crawler_result",
                  id: sessionStorage.getItem('id'),
                  web:'javdb',
                  result: true,
                  data:data
              });
          }
      }
    }
  
    if (sessionStorage.getItem('darkeye_auto_parse') === 'true') {
        sessionStorage.removeItem('darkeye_auto_parse');
        if (!window.location.href.startsWith("https://www.javdb.com/search?q=")) {
            setTimeout(() => {
                console.log("DarkEye: 检测到自动跳转任务，开始解析...");
                parse_data_javdb();
            }, 1000);
        }
    }
  })();
  