# FETCH final build and commissioning manual

**Baseline:** Hiwonder TT-motor mecanum chassis, Uno R4, two L298N modules, two
XL4015 converters, five HC-SR04 sensors, Pi 4 + USB camera, iPhone checkpoint
app, and HomeJoy 11.1 V 2000 mAh Li-ion battery.

This is the only final build described here. Do not mix in the archived CNC
Shield, A4988, NEMA, L293D, TF-Luna, servo, or battery-monitor designs.

## What the completed demo does

The person scans the QR on the nearest checkpoint and presses **CALL FETCH**.
The phone sends `zone=<id>` to the Pi. The robot can begin out of sight. It
localizes from a visible AprilTag, finds a route through a strongly connected
directed checkpoint graph, then visually approaches each next tag. The Uno
stops locally when ultrasonic clearance is unsafe. The last AprilTag, centered
and held at the expected sonar range, is the arrival proof.

The robot comes to the **scanned checkpoint**, not to an arbitrary unmarked
person. The app must remain open while it travels; losing the phone heartbeat
causes a stop. Use this only on a supervised, taped-off demo route.

## Required parts

1. Obtain one Hiwonder 180 × 140 × 89 mm mecanum chassis kit with four 3–6 V, 1:120 TT brushed motors and four 66 mm mecanum wheels.
2. Obtain one Arduino Uno R4 Minima.
3. Obtain exactly two standard L298N dual H-bridge modules.
4. Obtain one HiLetgo three-pack of adjustable XL4015 modules; install two and keep the third as a spare.
5. Obtain five genuine-working HC-SR04 modules.
6. Obtain one Raspberry Pi 4 and one forward-facing UVC USB camera.
7. Obtain one dedicated 5.1 V / 3 A Pi power bank and a short suitable cable.
8. Use one HomeJoy 11.1 V 2000 mAh Li-ion pack at a time and only its matching 3S charger.
9. Obtain one inline ATC/ATO blade-fuse holder and 3 A fuses.
10. Obtain one latching master power switch rated for at least 12.6 V DC and 5 A DC.
11. Obtain two 470 µF electrolytic capacitors rated at least 16 V.
12. Use short 18–20 AWG stranded copper for battery and motor-power branches, 22 AWG for motors, and 24–26 AWG for logic/sensors.
13. Use proper crimp splices or solder plus heat-shrink, insulated ferrules for screw terminals, cable ties, and strain relief.
14. Obtain a digital multimeter; a DC clamp meter or inline wattmeter is strongly recommended for commissioning.
15. Print the generated A4 checkpoint posters at 100% scale on matte paper and mount them rigidly.

## Reject incompatible substitutions

16. Do not use the L293D shield: its approximately 0.6 A continuous channel rating and voltage loss are a poor match for four loaded TT motors.
17. Do not use the old CNC Shield, A4988 drivers, or JK42HS40 NEMA motors with this wiring or firmware.
18. Do not feed 11.1–12.6 V directly into any TT motor.
19. Do not feed the motor battery directly into the Uno 5 V pin, Pi, camera, sonar, or L298 logic-5 V terminal.
20. Do not parallel the two XL4015 outputs; each converter powers only its assigned L298N motor-supply input.
21. Do not connect two battery packs together.
22. Do not use a fixed 5 V automotive converter for the L298 motor rail; the L298 bridge voltage drop would leave the motors underpowered.
23. Do not add a TF-Luna, camera-tilt servo, or battery monitor to this pin map.

## Mechanical assembly

24. Assemble the chassis and verify every mecanum roller turns freely.
25. Orient all four wheels according to the chassis manufacturer's mecanum X-pattern; photograph the finished orientation.
26. Label the motor locations `FL`, `FR`, `RL`, and `RR` before wiring.
27. Mount the battery low and centered, isolated from sharp metal edges.
28. Mount both L298N modules and both XL4015 modules where air can circulate and no conductive surface touches their undersides.
29. Mount the physical switch where an operator can reach it immediately.
30. Mount the fuse holder within 10 cm of the battery positive connector.
31. Mount the Pi, Uno, and camera rigidly; aim the camera level and straight forward.
32. Mount the front sonar facing forward.
33. Mount left-front and left-rear sonar modules facing left, separated as far as the chassis permits.
34. Mount right-front and right-rear sonar modules facing right, separated as far as the chassis permits.
35. Keep sonar transducers clear of wheels, cables, soft fabric, and angled chassis plates.

## Power wiring — battery disconnected

36. Identify battery positive and negative with the multimeter; never trust wire color alone.
37. Cut only a replaceable adapter lead if possible; do not cut the battery pack itself near its cells.
38. Connect battery positive to the inline 3 A fuse holder.
39. Connect the fuse-holder output to the master switch input.
40. Split the switched positive into two independent branches: XL4015 #1 `IN+` and XL4015 #2 `IN+`.
41. Split battery negative into XL4015 #1 `IN-`, XL4015 #2 `IN-`, L298N #1 GND, L298N #2 GND, and Uno GND.
42. Ensure the negative split makes one common reference among the motor battery, both converters, both L298Ns, and Uno.
43. Remove the `5V-EN` regulator jumper from both L298N modules.
44. Remove `ENA` and `ENB` jumper caps from both L298N modules so D5/D6/D9/D10 can provide PWM.
45. Leave both L298 motor-supply terminals disconnected while adjusting the converters.
46. Insert the 3 A fuse, turn on briefly, and set XL4015 #1 to exactly 6.50 V using the multimeter.
47. Set XL4015 #2 to exactly 6.50 V using the multimeter.
48. Turn power off and wait for both converter outputs to fall below 0.5 V.
49. Connect XL4015 #1 `OUT+`/`OUT-` only to L298N #1 motor `VS/+12V` and GND.
50. Connect XL4015 #2 `OUT+`/`OUT-` only to L298N #2 motor `VS/+12V` and GND.
51. Install one 470 µF capacitor directly across each L298 motor-supply input: capacitor `+` to 6.5 V and striped `-` to GND.
52. Connect Uno `5V` to both L298N logic `5V` terminals; the removed `5V-EN` jumpers prevent regulator conflict.
53. Power the Uno through its USB connection to the Pi; never power the Pi from the Uno.
54. Power the Pi only from the separate 5.1 V / 3 A power bank.
55. Confirm the Pi USB-to-Uno cable also provides the serial link and common logic ground.

## Exact motor-driver signal wiring

56. Connect L298N #1 channel A to motor `M1/FL`: `ENA=D5`, `IN1=D2`, `IN2=D4`.
57. Connect L298N #1 channel B to motor `M2/FR`: `ENB=D6`, `IN3=D7`, `IN4=D8`.
58. Connect L298N #2 channel A to motor `M3/RL`: `ENA=D9`, `IN1=D12`, `IN2=D13`.
59. Connect L298N #2 channel B to motor `M4/RR`: `ENB=D10`, `IN3=A0`, `IN4=A1`.
60. Connect each driver's two output terminals only to its assigned motor.
61. Tug-test every screw-terminal conductor and verify no loose strands bridge adjacent terminals.

| Motor | Position | PWM | Direction 1 | Direction 2 | Driver channel |
|---|---|---:|---:|---:|---|
| M1 | front-left | D5 | D2 | D4 | L298N #1 A |
| M2 | front-right | D6 | D7 | D8 | L298N #1 B |
| M3 | rear-left | D9 | D12 | D13 | L298N #2 A |
| M4 | rear-right | D10 | A0 | A1 | L298N #2 B |

## Exact ultrasonic wiring

62. Connect all five HC-SR04 `VCC` pins to Uno 5 V.
63. Connect all five HC-SR04 `GND` pins to the common Uno ground.
64. Connect all five `TRIG` pins together and connect the shared trigger wire to D3.
65. Connect front `ECHO` to D11.
66. Connect left-front `ECHO` to A2.
67. Connect right-front `ECHO` to A3.
68. Connect left-rear `ECHO` to A4.
69. Connect right-rear `ECHO` to A5.
70. Keep D0 and D1 unused.

All five modules transmit together because the direct L298 wiring consumes 12
GPIO. Firmware captures all echo pulses concurrently and repeats every 65 ms.
That meets the sensor's repeat-cycle guidance, but simultaneous modules can
still hear one another. Physical cross-talk testing is a mandatory acceptance
gate, not an optional improvement.

## Electrical inspection before first power

71. Remove the fuse and disconnect both the motor battery and Pi power bank.
72. Measure resistance between battery positive and negative on the robot side; investigate a near-short before continuing.
73. Verify continuity from every ground node to every other ground node.
74. Verify there is no continuity from 6.5 V rails to 5 V logic rails.
75. Verify converter outputs are not connected to one another.
76. Verify both `5V-EN` jumpers and all four `ENA/ENB` jumpers are physically removed.
77. Verify both capacitors have correct polarity.
78. Reinsert the fuse, keep all motors lifted off the floor, and switch on.
79. Measure both motor rails again: each must remain 6.3–6.7 V unloaded.
80. Measure Uno/sensor/L298 logic: 4.8–5.2 V.
81. Confirm the Pi shows no undervoltage warning on its separate supply.
82. Switch off immediately for odor, smoke, hot wiring, converter squeal, or unstable voltage.

## Load firmware and Pi software

83. Install the Arduino CLI/core or Arduino IDE with the Uno R4 Minima board package.
84. Flash `firmware/tt_fetch_drive/tt_fetch_drive.ino` to the Uno R4.
85. Open serial at 115200 baud and confirm `FETCH_TT_READY V3` plus `S` telemetry packets containing five ranges and one stop flag.
86. On the Pi run `sudo apt update`.
87. Install dependencies with `sudo apt install -y python3-opencv python3-serial avahi-daemon`.
88. Confirm `python3 -c "import cv2, serial; print(cv2.__version__, hasattr(cv2, 'aruco'))"` prints `True` for ArUco support.
89. Copy the repository to the Pi and connect the UVC camera and Uno USB cable.
90. Identify the Uno serial device with `ls -l /dev/serial/by-id/`; use that stable path instead of guessing `/dev/ttyACM0` when possible.
91. Put the iPhone and Pi on the same private hotspot or travel router; do not rely on mall guest Wi-Fi because client isolation may block phone-to-Pi traffic.
92. Park at a known checkpoint and start the server with `python3 pi/topo_server.py --serial /dev/serial/by-id/YOUR_UNO --map topo_map.json --start-zone 0 --host 0.0.0.0 --port 8080`, replacing `0` with the actual starting checkpoint.
93. Verify `curl http://127.0.0.1:8080/status` on the Pi reports fresh camera and telemetry before enabling floor motion.

After manual commissioning, install automatic startup from the Pi checkout:

```bash
bash pi/install_fetch_service.sh --dry-run \
  --serial /dev/serial/by-id/YOUR_UNO --map /absolute/path/topo_map.json --start-zone 0
sudo bash pi/install_fetch_service.sh \
  --serial /dev/serial/by-id/YOUR_UNO --map /absolute/path/topo_map.json --start-zone 0
```

The real invocation installs required Pi packages, sets the hostname to `fetch`,
enables Avahi and `fetch.service`, and prints the service status. The configured
start zone is a physical promise: after every boot, park the robot at that exact
checkpoint before allowing calls.

## Build the iPhone app target

94. Open the generated `ios/FetchCheckpoint.xcodeproj` in Xcode; regenerate it after editing `ios/project.yml` with `xcodegen generate --spec ios/project.yml`.
95. Confirm the target's generated Info.plist contains `NSCameraUsageDescription` for checkpoint QR scanning.
96. Confirm it contains `NSLocalNetworkUsageDescription` for nearby-robot control.
97. Confirm App Transport Security permits local-network HTTP only; the generated project uses `NSAllowsLocalNetworking`, not a broad Internet exception.
98. Select your development team, run on a physical iPhone, enter `http://fetch.local:8080`, and press **TEST CONNECTION**.
99. Keep the app foregrounded and the phone awake throughout a call; its 500 ms status polling is the route heartbeat.

## Print and map checkpoints

100. Run `python3 markers/make_checkpoints.py` using Python with OpenCV ArUco, Pillow, qrcode, and NumPy installed.
101. Print `markers/fetch_CHECKPOINTS_PRINT_ME.pdf` on A4 at **Actual Size / 100%** with no fit-to-page scaling.
102. Measure the black AprilTag square; reject the print unless it is 180 mm ±1 mm.
103. Start with checkpoints 2–3 m apart, approximately camera height, matte, flat, and well lit.
104. Keep each tag's surrounding white quiet zone unobstructed.
105. Use duplicate posters with the same checkpoint ID on angled/multi-face mounts if a checkpoint must be seen from different incoming directions.
106. Treat an edge `A→B` as valid only when the robot stopped at A can acquire B and the straight physical segment A-to-B is cleared.
107. If using `tools/make_topo_map.py --edges 0-1,1-2`, remember each hyphen creates both directions; physically test both `0→1` and `1→0`.
108. Validate that the graph is strongly connected so every checkpoint can route to every other checkpoint.
109. Do not place an edge around a blind corner, through a doorway that may close, or through normal pedestrian flow.

## One-wheel and mecanum commissioning

110. Keep the chassis lifted and send only stop commands at startup.
111. Command each motor forward one at a time and record actual wheel-face direction from the outside of that wheel.
112. Correct motor location only in firmware `CORNER`; correct direction only in firmware `POLARITY` or by swapping that motor's two output wires—not both.
113. Repeat until a positive forward command makes all four wheel-ground contact patches propel the chassis forward.
114. Test low-speed forward, backward, left strafe, right strafe, clockwise rotate, and counterclockwise rotate with the chassis still lifted.
115. Put the robot on the floor at minimum practical speed and repeat each primitive for one second with an operator at the switch.
116. Adjust only `TRIM` values in small increments if one motor is consistently stronger; do not conceal a mechanical bind with software.
117. Run the small mecanum circle test and confirm the chassis orientation remains approximately fixed; if it spins, stop and repair wheel placement/corner/polarity mapping before navigation.

## Mandatory sensor and navigation acceptance tests

118. Test every sonar alone against a large flat target at 20, 60, and 100 cm; require ±3 cm or document a stricter observed envelope.
119. Test all five operating together in their installed positions at the same distances and at angled walls; reject the shared-trigger layout if cross-talk produces unsafe false-clear readings.
120. Place obstacles just inside each programmed threshold and command motion toward them; every applicable direction must stop.
121. Cover the camera during a route; verify motor commands cease within one second.
122. Disconnect Uno USB during a route; verify the 500 ms firmware command watchdog stops motion.
123. Disable iPhone Wi-Fi or close the app during a route; verify the server stops motion approximately two seconds after heartbeat loss.
124. Press **STOP FETCH** during forward, strafe, and rotation; verify each stops.
125. Place an unrelated obstacle at 50 cm while the target tag is still small; verify the software reports blocked and never claims arrival.
126. At each checkpoint, verify arrival requires the correct target tag centered, sufficiently large, and front sonar near 65 cm for the hold time.
127. Traverse every directed edge twice in daylight-equivalent lighting and twice in the actual demo lighting without touching the robot.
128. Summon from every checkpoint to every other checkpoint at least once; any failure means the graph/demo is not ready.

## Power, heat, payload, and 20-minute acceptance

129. Fully charge the pack only with its matching charger; after resting, verify approximately 12.6 V and no swelling, damage, odor, or heat.
130. Measure battery-side current with wheels lifted, forward on the floor, strafe, rotate, blocked-start for less than one second, and with final payload.
131. Require normal sustained battery current to stay at or below 3 A because the selected fuse and small SM-style connector are the present limit.
132. If the 3 A fuse opens during normal motion, do not install a larger fuse until the exact battery BMS, connector, lead, switch, and motor-stall ratings are verified.
133. Record motor-rail voltage under the worst normal floor maneuver; investigate a rail below 5.8 V or repeated Uno/Pi resets.
134. Weigh the complete robot and keep it below the chassis maker's claimed 1500 g capacity with margin.
135. Run the final route continuously for 20 minutes with the intended payload and network.
136. At 5, 10, 15, and 20 minutes record battery, connector, XL4015, L298N, and motor temperatures.
137. Stop for a battery above 45 °C, warm/darkened connector, motor odor, repeated thermal shutdown, or any wiring too hot to touch; use an infrared thermometer and keep L298N/XL4015 case surfaces below 70 °C as a conservative prototype gate.
138. After the run, switch off and measure the rested battery; stop demo use and recharge at 10.5 V rather than relying on unknown pack protection.
139. A simple 80%-usable capacity model predicts about 32 minutes at 3 A, 38 minutes at 2.5 A, and 48 minutes at 2 A; only the physical 20-minute payload test proves your pack/build.

## Demo-day operating sequence

140. Inspect tires, wheel screws, wires, fuse, switch, battery condition, camera aim, and all posters.
141. Measure the resting motor battery and confirm both motor rails are 6.3–6.7 V.
142. Power the Pi first, start the server, then power the motor system with wheels clear.
143. Confirm `/status` shows fresh camera, fresh telemetry, no stop flag, and a valid map.
144. Place the robot exactly at a commissioned checkpoint pose.
145. Put one trained operator beside the robot's physical switch for every run.
146. Have the user stand at a poster, scan its QR, verify the displayed checkpoint ID, and press **CALL FETCH**.
147. Keep the app foregrounded while the robot follows the route; never enter its path to demonstrate avoidance.
148. If behavior differs from commissioning, press app stop and then the physical switch—do not debug a moving robot.
149. At arrival, retrieve/load the robot only after it is fully stopped.
150. After the demo, switch motor power off, shut down the Pi normally, disconnect the battery, and charge/store it on a nonflammable surface under supervision.

## Go/no-go record

The build is **software-verified but not physically approved** until every blank
below contains measured evidence from this exact assembled robot.

Copy `commissioning/acceptance_template.json` to a new robot/date-specific JSON
file, enter the measured results, then run
`python3 tools/validate_commissioning.py commissioning/YOUR_RECORD.json`. The
blank template must fail; do not replace missing measurements with estimates.

| Gate | Pass evidence required | Result |
|---|---|---|
| Two XL4015 rails | 6.3–6.7 V idle and ≥5.8 V worst normal load | ___ |
| Logic rail | 4.8–5.2 V, no resets | ___ |
| Current/fuse | all sustained modes ≤3 A; 3 A fuse survives | ___ |
| Five sonars | 20/60/100 cm and installed cross-talk test pass | ___ |
| Motion primitives | F/B/L/R/CW/CCW correct, no unintended spin | ___ |
| Directed graph | every physical edge passes twice in demo lighting | ___ |
| Failure stops | camera, USB, phone, obstacle, cancel all pass | ___ |
| Arrival integrity | obstacle never equals arrival; target gate passes | ___ |
| Payload | total mass and floor traction pass | ___ |
| Runtime/thermal | 20 min pass with recorded temperatures | ___ |
| Network | private network covers entire route without isolation | ___ |
| Full summons | every source-to-destination call passes | ___ |

No source-code analysis or calculation can fill these physical results. Until
all rows pass, describe FETCH as an in-progress supervised prototype—not as a
validated mall robot.
