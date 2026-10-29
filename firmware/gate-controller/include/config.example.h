// Copy this file to config.h and fill in your values.
// config.h is git-ignored so secrets never reach the repository.
#pragma once

#define WIFI_SSID   "your-wifi-name"
#define WIFI_PASS   "your-wifi-password"

// https:// for the deployed site, http://192.168.x.x:8000 for a LAN server.
#define API_BASE    "https://parkq.onrender.com"
#define LOT_ID      "L001"             // parking lot id registered on the server
#define DEVICE_KEY  "dev-key-xxxxxxxx" // lots.device_key of that lot

// QR reader (GM65/GM861) default baud rate
#define QR_BAUD     9600
