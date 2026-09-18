// Local Vite component smoke test. Uses synthetic data and never calls providers.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const fs = require("node:fs");

(async () => {
  const xml = fs.readFileSync(".data/export-qa/branch.bpmn", "utf8");
  const browser = await chromium.launch({ headless: true, channel: "msedge" });
  try {
    const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    await page.goto(process.env.FRONTEND_URL || "http://localhost:5173");
    await page.evaluate(async (xml) => {
      const { default: React } = await import("/node_modules/.vite/deps/react.js");
      const { default: ReactDOM } = await import("/node_modules/.vite/deps/react-dom_client.js");
      const { default: Diagram } = await import("/src/features/recordings/BpmnDiagram.tsx");
      const { default: Document } = await import("/src/features/recordings/ReportDocument.tsx");
      await import("/src/features/recordings/SessionMedia.css");
      document.getElementById("root").style.display = "none";
      const host = document.createElement("main");
      host.style.cssText = "max-width:1000px;margin:auto;padding:16px;min-width:0";
      document.body.append(host);
      const report = { recording_id: "demo", revision: 3, review_status: "approved" };
      const api = async (path, options) => {
        const data = JSON.parse(options.body);
        if (path !== "/recordings/demo/report/file" || data.revision !== 3) throw new Error("Export contract mismatch");
        window.exportRequest = data;
        return new Blob(["%PDF-test"], { type: "application/pdf" });
      };
      ReactDOM.createRoot(host).render(React.createElement(React.Fragment, null,
        React.createElement(Diagram, { xml, filename: "demo.bpmn", onSelect: id => { window.selectedStep = id; } }),
        React.createElement(Document, { report, api, dirty: false })));
    }, xml);
    await page.locator('[data-element-id="step-1"] .djs-visual').waitFor();
    if (await page.locator('[data-element-id="decision-1"] .djs-visual path').count() === 0) throw new Error("No gateway marker");
    await page.locator('[data-element-id="step-1"] .djs-hit').click();
    if (await page.evaluate(() => window.selectedStep) !== "step-1") throw new Error("Evidence selection failed");
    const downloaded = page.waitForEvent("download");
    await page.getByRole("button", { name: "Descargar BPMN" }).click();
    if ((await downloaded).suggestedFilename() !== "demo.bpmn") throw new Error("BPMN download failed");
    await page.getByRole("button", { name: "Generar documento", exact: true }).click();
    await page.getByRole("link", { name: "Descargar PDF" }).waitFor();
    const file = page.waitForEvent("download");
    await page.getByRole("link", { name: "Descargar PDF" }).click();
    if (!(await file).suggestedFilename().endsWith(".pdf")) throw new Error("PDF download failed");
    await page.screenshot({ path: ".data/export-qa/bpmn-desktop.png", fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.getByRole("button", { name: "Encajar diagrama", exact: true }).click();
    await page.screenshot({ path: ".data/export-qa/bpmn-mobile.png", fullPage: true });
    if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)) throw new Error("Mobile overflow");
    if (errors.length) throw new Error(errors.join("\n"));
    console.log("BPMN tasks, gateways, selection, download, document contract and responsive layout verified");
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
