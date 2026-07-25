# FETCH — End-Product Software Deployment

Stepper build (NEMA17 + CNC Shield V3). One firmware, one Pi stack, one path.

## The software map

| Piece | File | Job |
|---|---|---|
| Firmware (THE one to flash) | `firmware/fetch_final/fetch_final.ino` | 4 steppers + 5 sonars + tilt servo + serial protocol + watchdog + front veto |
| Pi relay | `pi/fetch_relay.py` | phone WiFi vectors -> USB serial (phone-sees-robot homing) |
| Direct-path nav | `pi/topo_nav.py` | checkpoint graph router (BFS over verified segments) |
| Checkpoint server | `pi/topo_server.py` | iPhone QR destination -> AprilTag route -> drives the Uno |
| Bench tester | `pi/fake_phone.py` | simulates the phone stream, no app needed |
| Service installer | `pi/install_fetch_service.sh` | auto-start on boot via systemd |

## 1. Flash the firmware (from this Mac, robot USB-connected)

```bash
arduino-cli compile -b arduino:renesas_uno:unor4wifi ~/Developer/fetch/firmware/fetch_final
```

```bash
arduino-cli upload -b arduino:renesas_uno:unor4wifi -p /dev/cu.usbmodemB43A45B3E0482 ~/Developer/fetch/firmware/fetch_final
```

If upload fails: double-tap RESET (LED breathes) and retry.
Then Serial Monitor 115200: `f b l r q e s` drive keys, `t 120` tilts camera,
`us f=.. lf=..` lines stream distances.

## 2. SSH into the Pi

Enable once (SD card in this Mac): create an empty file named `ssh` on the
boot partition. Or on the Pi itself: `sudo raspi-config` -> Interface Options -> SSH.

```bash
ssh pi@raspberrypi.local
```

(Default password `raspberry` unless you changed it. If .local fails, find the
IP in your hotspot's client list and `ssh pi@<ip>`.)

## 3. Deploy the code to the Pi

```bash
scp -r ~/Developer/fetch/pi pi@raspberrypi.local:~/fetch
```

On the Pi (one time):

```bash
sudo apt update && sudo apt install -y python3-serial python3-opencv python3-pip && pip3 install pupil-apriltags --break-system-packages
```

## 4. Run it

Plug the Uno into the Pi via USB. Manual/bench test first:

```bash
python3 ~/fetch/fake_phone.py --approach
```

Phone-vision homing (the app streams to this):

```bash
python3 ~/fetch/fetch_relay.py
```

Direct-path checkpoint navigation (press-button-and-it-comes, out of sight):

```bash
python3 ~/fetch/topo_server.py --serial /dev/ttyACM0 --map ~/fetch/config/topo_map.demo.json --start-zone 0
```

## 5. Auto-start on boot (demo day)

```bash
bash ~/fetch/install_fetch_service.sh --serial /dev/ttyACM0 --start-zone 0 --dry-run
```

Re-run without `--dry-run` to install. Robot then boots straight into service.

## Protocol (Uno <-> Pi), for debugging

- Pi -> Uno: `v vx vy w\n` at up to 15 Hz (each -100..100), `t <deg>\n` tilt
- Uno -> Pi: `us f=52 lf=110 rf=200 lr=0 rr=88\n` at ~7 Hz (cm, 0 = no echo)
- Uno stops itself if `v` goes silent 500 ms (watchdog) and refuses forward
  motion under 25 cm front clearance (veto) — safety lives on the Uno.

## Wiring recap for fetch_final

- Motors (proven): FL=X(2,5) FR=Y(3,**A2**) RL=Z(4,7) RR=A(12,13), EN=8
- Sonars: TRIG all -> D9. Echoes: front D10, L-front A0, R-front A1,
  L-rear A3, R-rear A4
- Servo: signal D11, power from XL4015 @5.0V (never the Uno 5V), common GND
- POL / corner fixes: edit `POL[4]` and the four constructors at the top of
  fetch_final.ino only.
