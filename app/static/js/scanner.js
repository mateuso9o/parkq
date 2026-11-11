// Camera QR scanner for the gate kiosk.
// 1) BarcodeDetector (built into Chrome on Android / macOS / ChromeOS) when it can read QR codes.
// 2) jsQR as a fallback for other browsers (e.g. Chrome/Edge on Windows): drop jsQR.min.js (v1.4.0, Apache-2.0)
//    into /static/js/vendor/jsQR.js and it is picked up automatically; nothing else needs to change.
// getUserMedia only works on https:// or http://localhost, which both our hosting options provide.

let jsQRPromise;
function loadJsQR() {
  if (window.jsQR) return Promise.resolve(window.jsQR);
  jsQRPromise ||= new Promise((resolve) => {
    const s = document.createElement("script");
    s.src = "/static/js/vendor/jsQR.js";
    s.onload = () => resolve(window.jsQR || null);
    s.onerror = () => resolve(null);
    document.head.appendChild(s);
  });
  return jsQRPromise;
}

async function pickDecoder() {
  if ("BarcodeDetector" in window) {
    try {
      const formats = await window.BarcodeDetector.getSupportedFormats();
      if (formats.includes("qr_code")) {
        const det = new window.BarcodeDetector({ formats: ["qr_code"] });
        return { name: "BarcodeDetector", decode: async (video) => (await det.detect(video))[0]?.rawValue || "" };
      }
    } catch { /* fall through to jsQR */ }
  }
  const jsQR = await loadJsQR();
  if (!jsQR) return null;
  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  return {
    name: "jsQR",
    decode: async (video) => {
      const scale = Math.min(1, 640 / (video.videoWidth || 640));
      canvas.width = Math.round(video.videoWidth * scale); canvas.height = Math.round(video.videoHeight * scale);
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      const img = ctx.getImageData(0, 0, canvas.width, canvas.height);
      return jsQR(img.data, img.width, img.height, { inversionAttempts: "dontInvert" })?.data || "";
    },
  };
}

export const cameraSupported = () => !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);

// createScanner({ video, onCode, onError }) -> { start(), stop(), running }
// A code is reported once each time it is presented: while the same QR stays in view it is not reported again, and it
// counts as "presented again" only after it has been out of view for `gapMs` (so a QR held up while the barrier opens
// does not trigger a second, red "already used" message).
export function createScanner({ video, onCode, onError = () => {}, gapMs = 1500, intervalMs = 120 }) {
  let stream = null, timer = null, last = "", lastSeen = 0, busy = false;
  const api = {
    running: false,
    async start() {
      if (api.running) return;
      if (!cameraSupported()) return onError({ code: "NO_CAMERA_API", message: "เบราว์เซอร์นี้ไม่รองรับกล้อง หรือหน้านี้ไม่ได้เปิดผ่าน https" });
      const decoder = await pickDecoder();
      if (!decoder) return onError({ code: "NO_DECODER", message: "เบราว์เซอร์นี้ยังอ่าน QR จากกล้องไม่ได้ ให้ใช้เครื่องอ่าน QR หรือเบราว์เซอร์ Chrome บนมือถือ" });
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: "environment" }, width: { ideal: 1280 } }, audio: false });
      } catch (e) {
        return onError({ code: e.name, message: e.name === "NotAllowedError" ? "ยังไม่ได้อนุญาตให้ใช้กล้อง กรุณากดอนุญาตในเบราว์เซอร์" : "เปิดกล้องไม่ได้ (" + e.name + ")" });
      }
      video.srcObject = stream; video.setAttribute("playsinline", ""); await video.play().catch(() => {});
      api.running = true;
      timer = setInterval(async () => {
        if (busy || video.readyState < 2) return;
        busy = true;
        try {
          const code = await decoder.decode(video);
          const t = Date.now();
          if (code) {
            const sameInView = code === last && t - lastSeen < gapMs;
            lastSeen = t;
            if (!sameInView) { last = code; onCode(code); }
          }
        } catch { /* a frame that cannot be read is simply skipped */ } finally { busy = false; }
      }, intervalMs);
    },
    stop() {
      clearInterval(timer); timer = null; api.running = false;
      stream?.getTracks().forEach((t) => t.stop()); stream = null; video.srcObject = null;
    },
  };
  return api;
}
