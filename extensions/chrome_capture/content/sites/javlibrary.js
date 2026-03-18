// JavLibrary 站点：dvdid 搜索、解析、自动续跑
(function() {
  const api = chrome || browser;
  if (!window.location.href.includes("javlibrary.com")) return;

  api.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.command === "javlibrary-dvdid"){
        sessionStorage.setItem('darkeye_auto_parse', 'true')
        sessionStorage.setItem('id', message.serial)
        if (!search_javlibrary()){
            //这里回传失败的信息
        }
    }
  });

  function search_javlibrary(){
    if (window.location.href.startsWith("https://www.javlibrary.com/cn/vl_searchbyid.php?keyword=")){
        const videos = document.querySelectorAll('div.video');
        if (videos.length === 0) {
            if (document.title.includes("Just a moment") || document.title.includes("Attention Required") || document.querySelector('#challenge-running')) {
                console.log("DarkEye: 遇到 Cloudflare，暂不报错，等待自动重试...");
                sessionStorage.setItem('darkeye_auto_parse', 'true');
                return false;
            }
            console.log("该番号javlib没有搜索结果");
            sessionStorage.setItem('darkeye_auto_parse', 'false')
            api.runtime.sendMessage({
                command: "send_crawler_result",
                id: sessionStorage.getItem('id'),
                web:'javlib',
                result: false,
                data:{}
            });
            return false;
        }
        console.log("搜索结果个数: " + videos.length);
        const results = Array.from(videos).map(video => {
            const idDiv = video.querySelector('.id');
            const titleDiv = video.querySelector('.title');
            const link = video.querySelector('a');
            return {
                id: idDiv ? idDiv.textContent.trim() : "",
                title: titleDiv ? titleDiv.textContent.trim() : "",
                url: link ? link.href : ""
            };
        });
        const filtered = results.filter(item => !item.title.includes("ブルーレイディスク"));//这个是过滤掉蓝光碟的
        let targetUrl = null;
        if (filtered.length > 0) {
            targetUrl = filtered[0].url;
        } else if (results.length > 0) {
            targetUrl = results[0].url;
        }
        if (targetUrl) {
            sessionStorage.setItem('darkeye_auto_parse', 'true');
            window.location.href = targetUrl;
        }
    } else {
        parse_data_javlibrary();
    }
  }

  function parse_data_javlibrary(){
    if (window.location.href.includes("javlibrary.com")) {
        const data = {};
        const dvdidElement = document.querySelector("#video_id .text");
        data.id = dvdidElement ? dvdidElement.textContent.trim() : "";
        data.id = data.id.endsWith('v') ? data.id.slice(0, -1) : data.id;
        console.log("番号: " + data.id);

        const titleElement = document.querySelector(".post-title.text a");
        if (titleElement) {
            let newtitle = titleElement.textContent.replace(data.id,'').trim();
            data.title = newtitle;
            console.log("标题: " + data.title);
        }

        const dateElement = document.querySelector("#video_date .text");
        data.release_date = dateElement ? dateElement.textContent.trim() : "";
        const lengthElement = document.querySelector("#video_length .text");
        data.length = lengthElement ? lengthElement.textContent.trim() : "";
        const directorElement = document.querySelector("#video_director .text");
        data.director = directorElement ? directorElement.textContent.trim() : "";
        const genreElements = document.querySelectorAll("#video_genres .genre a");
        data.genre = Array.from(genreElements).map(el => el.textContent.trim());
        const castElements = document.querySelectorAll("#video_cast .star a");
        data.actress = Array.from(castElements).map(el => el.textContent.trim());
        const imgElement = document.querySelector("#video_jacket_img");
        data.image = imgElement ? imgElement.src : "";

        sessionStorage.setItem('darkeye_auto_parse', 'false');
        if (data) {
            console.debug("发送数据");
            api.runtime.sendMessage({
                command: "send_crawler_result",
                id: sessionStorage.getItem('id'),
                web:'javlib',
                result: true,
                data:data
            });
        }
    }
  }

  if (sessionStorage.getItem('darkeye_auto_parse') === 'true') {
      sessionStorage.removeItem('darkeye_auto_parse');
      if (!window.location.href.startsWith("https://www.javlibrary.com/cn/vl_searchbyid.php?keyword=")) {
          setTimeout(() => {
              console.log("DarkEye: 检测到自动跳转任务，开始解析...");
              parse_data_javlibrary();
          }, 1000);
      }
  }
})();
