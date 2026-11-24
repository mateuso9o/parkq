# ParkQ gate demo: phone scan → barrier opens in Wokwi

## Before presenting (10 min ahead)
1. Open https://parkq.onrender.com once. The free instance sleeps; the first request takes ~35-50 s.
2. VS Code, folder `firmware/gate-controller`: run `pio run` if `.pio/build/esp32dev/firmware.bin` is missing.
3. `F1` → **Wokwi: Start Simulator**. Serial Monitor should print the WiFi connect and `commands: ...` lines.
   (First time only: `F1` → *Wokwi: Request a new license* → sign in to the Wokwi account in the browser.)

## The demo
1. **Laptop / projector**: open the site, sign in as a driver (OTP is shown on screen in demo mode),
   open the lot **LOT02 โมเดลลานจอด IoT**, buy 1 hour (simulated payment), show the ticket QR.
2. **Phone**: open `https://parkq.onrender.com/gate?lot=LOT02&dir=in`, allow the camera.
   The page defaults to LOT01 if `lot=` is missing, and LOT01 has no board.
3. Point the phone at the ticket QR. The phone shows the welcome screen; within ~1 s the **entry servo in
   Wokwi turns to 90°**, the green LED lights, the buzzer beeps, and after 3 s the barrier closes.
4. Exit: `.../gate?lot=LOT02&dir=out`, scan the same ticket; the **exit servo** opens.
5. Auto car (Wokwi `config.h` has `#define DEMO_AUTO_CAR`): 4 s after the entry barrier opens the firmware marks the first
   free slot occupied (`auto: car parked in slot N`), and the exit barrier frees it. Remove the define for the real board.
6. Sensors: slide a switch left in Wokwi (= car present, LOW). The admin dashboard / lot page changes the
   free-slot count for LOT02.

## Digital twin (3D)
Open `https://parkq.onrender.com/twin?lot=LOT02` on the projector. Slide a switch in Wokwi: the slot turns red and a car drives in
(free count drops). A phone scan opens the barrier on screen. Drag the slider to replay the last 10 minutes; "กลับไปสด" returns to live.
Drag to orbit, wheel/pinch to zoom, "ธีม" switches light/dark. History resets whenever Render redeploys.

## Backups
- Projector will not scan: scan from the laptop screen, show the result on the projector.
- No internet: play `parkq-film/parkq-film-new.mp4`.
- Real board (later): copy `include/config.example.h` over `include/config.h` and set the real WiFi.
  The current `config.h` is the Wokwi one (WiFi `Wokwi-GUEST`).
