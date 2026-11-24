// Copy this file to config.h and fill in your values.
// config.h is git-ignored so secrets never reach the repository.
#pragma once

#define WIFI_SSID   "your-wifi-name"
#define WIFI_PASS   "your-wifi-password"

// https:// for the deployed site, http://192.168.x.x:8000 for a LAN server.
#define API_BASE    "https://parkq.onrender.com"
#define LOT_ID      "LOT02"            // the only seeded lot that has a device key
#define DEVICE_KEY  "dev-key-LOT02"    // lots.device_key of LOT02 (public demo seed, not a secret)

// QR reader (GM65/GM861) default baud rate
#define QR_BAUD     9600

// #define DEMO_AUTO_CAR          // simulator only: a virtual car parks after the entry barrier opens
