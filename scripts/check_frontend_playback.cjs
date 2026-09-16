// Requires the frontend Vite server and a Playwright installation; no API keys or uploads.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");

(async () => {
  const browser = await chromium.launch({ headless: true, channel: "msedge" });
  try {
    const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
    await page.goto(process.env.FRONTEND_URL || "http://localhost:5173");
    await page.evaluate(async () => {
      const { default: React } = await import("/node_modules/.vite/deps/react.js");
      const { default: ReactDOM } = await import("/node_modules/.vite/deps/react-dom_client.js");
      const { default: ScreenStudio } = await import("/src/ScreenStudio.tsx");
      const canvas = document.createElement("canvas");
      canvas.width = 320;
      canvas.height = 180;
      const context = canvas.getContext("2d");
      let frame = 0;
      setInterval(() => {
        context.fillStyle = frame++ % 2 ? "#d03050" : "#20ba70";
        context.fillRect(0, 0, 320, 180);
      }, 50);
      navigator.mediaDevices.getDisplayMedia = async () => canvas.captureStream(20);
      document.getElementById("root").style.display = "none";
      const host = document.createElement("div");
      document.body.append(host);
      ReactDOM.createRoot(host).render(React.createElement(ScreenStudio, {
        sessionId: "test", onProtectedChange: () => {},
        api: () => Promise.reject(new Error("No upload in playback test")),
        capabilities: null, onSaved: () => {}, onBusy: () => {}, agentPanel: null,
      }));
    });
    await page.getByRole("button", { name: "Compartir pantalla", exact: true }).click();
    await page.getByRole("button", { name: "Iniciar grabaci\u00f3n", exact: true }).click();
    await page.waitForTimeout(1400);
    await page.getByRole("button", { name: "Detener grabaci\u00f3n", exact: true }).click();
    const video = page.getByLabel("Reproducir grabaci\u00f3n local");
    await video.waitFor();
    const result = await video.evaluate(async (element) => {
      element.muted = true;
      await element.play();
      await new Promise((resolve) => setTimeout(resolve, 300));
      const canvas = document.createElement("canvas");
      canvas.width = canvas.height = 8;
      const context = canvas.getContext("2d");
      context.drawImage(element, 0, 0, 8, 8);
      return { srcObjectCleared: element.srcObject === null, readyState: element.readyState,
        width: element.videoWidth, currentTime: element.currentTime,
        pixel: Array.from(context.getImageData(0, 0, 1, 1).data), error: element.error?.code };
    });
    if (!result.srcObjectCleared || !result.width || !(result.currentTime > 0)
        || result.error || !result.pixel.slice(0, 3).some((v) => v > 10)) {
      throw new Error(JSON.stringify(result));
    }
    console.log(JSON.stringify(result));
    await page.screenshot({ path: ".data/playback-desktop.png" });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.screenshot({ path: ".data/playback-mobile.png" });
  } finally {
    await browser.close();
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
