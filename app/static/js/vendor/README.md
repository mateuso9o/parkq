# Vendored third-party code

| File | Package | Version | License | Source |
|---|---|---|---|---|
| `jsQR.js` | jsQR (Cobalt Powered) | 1.4.0 | Apache-2.0 | https://cdn.jsdelivr.net/npm/jsqr@1.4.0/dist/jsQR.js (npm `jsqr`) |

Used only by `../scanner.js` to read QR codes from the camera in browsers without `BarcodeDetector`
(Chrome / Edge on Windows). Kept in the repository so the gate kiosk does not depend on a CDN during a demo.
