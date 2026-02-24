// Minnano AV actress 页面：悬浮球 + 采集 ID
(function(){
  if (!window.location.href.includes("minnano-av.com")) return;

  function initMinnanoOverlay() {
      if (!document.body) {
          window.addEventListener('DOMContentLoaded', initMinnanoOverlay);
          return;
      }
      const url = window.location.href;
      const match = url.match(/minnano-av\.com\/actress(\d+)\.html/);
      if (match) {
          const actressId = match[1];
          console.log("DarkEye: Minnano actress page detected. ID:", actressId);
          if (document.getElementById('darkeye-overlay')) return;
          createOverlay(actressId);
      }
  }

  function createOverlay(actressId) {
      const container = document.createElement('div');
      container.id = 'darkeye-overlay';
      container.style.cssText = `
          position: fixed;
          bottom: 30px;
          right: 30px;
          z-index: 2147483647;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      `;

      const fab = document.createElement('button');
      fab.textContent = 'DE';
      fab.style.cssText = `
          width: 56px;
          height: 56px;
          border-radius: 28px;
          background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
          color: #fff;
          border: 2px solid rgba(255,255,255,0.2);
          cursor: pointer;
          font-weight: 900;
          font-size: 18px;
          box-shadow: 0 4px 15px rgba(0,0,0,0.4);
          transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
          display: flex;
          align-items: center;
          justify-content: center;
          text-shadow: 0 1px 2px rgba(0,0,0,0.3);
      `;

      const panel = document.createElement('div');
      panel.style.cssText = `
          position: absolute;
          bottom: 70px;
          right: 0;
          background: #fff;
          border: 1px solid rgba(0,0,0,0.1);
          border-radius: 12px;
          padding: 12px;
          box-shadow: 0 8px 20px rgba(0,0,0,0.15);
          display: none;
          width: 180px;
          flex-direction: column;
          gap: 10px;
          animation: slideUp 0.2s ease-out;
      `;

      fab.onmouseenter = () => { fab.style.transform = 'scale(1.1)'; };
      fab.onmouseleave = () => {
          if (panel.style.display === 'none') fab.style.transform = 'scale(1)';
          else fab.style.transform = 'rotate(45deg)';
      };

      const styleSheet = document.createElement("style");
      styleSheet.innerText = `
        @keyframes slideUp {
          from { opacity: 0; transform: translateY(10px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `;
      document.head.appendChild(styleSheet);

      const info = document.createElement('div');
      info.innerHTML = `<strong>DarkEye</strong><br><span style="font-size:12px;color:#666">ID: ${actressId}</span>`;
      info.style.color = '#333';
      info.style.fontSize = '14px';
      info.style.textAlign = 'center';

      const btnCapture = document.createElement('button');
      btnCapture.textContent = '采集此ID';
      btnCapture.style.cssText = `
          background: #007aff;
          color: white;
          border: none;
          padding: 8px 12px;
          border-radius: 6px;
          cursor: pointer;
          font-size: 13px;
          font-weight: 600;
          transition: background 0.2s;
          width: 100%;
      `;
      btnCapture.onmouseover = () => btnCapture.style.background = '#0062cc';
      btnCapture.onmouseout = () => btnCapture.style.background = '#007aff';
      btnCapture.onclick = () => {
          btnCapture.textContent = '发送中...';
          btnCapture.disabled = true;
          browser.runtime.sendMessage({
              command: "capture_minnano_id",
              id: actressId
          });
          setTimeout(() => {
             btnCapture.style.background = '#34c759';
             btnCapture.textContent = '已发送';
          }, 500);
      };

      fab.onclick = () => {
          if (panel.style.display === 'none') {
              panel.style.display = 'flex';
              fab.style.transform = 'rotate(45deg)';
          } else {
              panel.style.display = 'none';
              fab.style.transform = 'rotate(0deg)';
          }
      };

      panel.appendChild(info);
      panel.appendChild(btnCapture);
      container.appendChild(panel);
      container.appendChild(fab);
      document.body.appendChild(container);
  }

  if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', initMinnanoOverlay);
  } else {
      initMinnanoOverlay();
  }
})();
