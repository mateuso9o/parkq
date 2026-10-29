// Pin map of the ParkQ Gate Controller board.
// MUST equal GPIO_MAP in hardware/gate-controller/design.py (checked by a test).
#pragma once

#define PIN_QR_IN_RX   16   // QR reader (entry)  TX -> ESP32 RX2
#define PIN_QR_IN_TX   17
#define PIN_QR_OUT_RX  32   // QR reader (exit)   on UART1 remapped
#define PIN_QR_OUT_TX  33
#define PIN_SERVO_IN   18   // SG90 entry barrier
#define PIN_SERVO_OUT  19   // SG90 exit barrier
#define PIN_SLOT1      34   // IR slot sensors (input-only pins, LOW = car)
#define PIN_SLOT2      35
#define PIN_SLOT3      36
#define PIN_SLOT4      39
#define PIN_LED_G      23
#define PIN_LED_R      22
#define PIN_BUZZER     4    // via NPN transistor: HIGH = beep
