---
tags: [final, manual, wiring, hackathon, critical]
---
# FINAL BUILD MANUAL

This is the single authoritative FETCH hackathon build. Do not combine it with older TF-Luna, phone-tracking, BLE, UWB, BNO08x or mall-production pages.

## Final configuration

- Four [JK42HS40-1704-13A](JK42HS40-1704-13A.md) motors
- Four 80mm mecanum wheels
- Arduino Uno R4 + CNC Shield V3.00
- Four A4988 drivers at 1/4 microstepping and 1.275A target
- Five HC-SR04 sensors; no TF-Luna and no level shifter
- Raspberry Pi 4B + forward UVC USB webcam
- One 11.1V 2000mAh SM2P battery installed; second identical pack disconnected as spare
- 7.5A ATC/ATO fuse, DC master switch, 5.1V/5A buck and 470µF/25V motor-rail capacitor
- QR/AprilTag checkpoint posters and topological route graph

## Required parts

1. Raspberry Pi 4B and microSD card
2. UVC USB webcam
3. Arduino Uno R4
4. CNC Shield V3.00
5. Four A4988 modules
6. Four A4988 heatsinks
7. One 5V cooling fan aimed across all drivers
8. Four JK42HS40-1704-13A motors
9. Four 80mm mecanum wheels
10. Five HC-SR04 sensors
11. Two-pack 11.1V 2000mAh battery kit and its exact charger
12. Matching SM2P pigtail; do not cut the battery pack if a mating connector is available
13. ATC/ATO inline fuse holder and 7.5A fuse
14. DC master switch rated at least 15V/10A
15. 5.1V/5A regulated buck accepting 9–12.6V input
16. 470µF electrolytic capacitor rated at least 25V
17. Positive and ground distribution blocks
18. 18AWG power wire for short main-power extensions
19. 22AWG wire for sensors
20. Crimp connectors sized for each joined wire, bootlace ferrules, heat-shrink and strain relief
21. Data-capable USB-A to USB-C cable for Pi-to-Uno
22. Chassis, bin and fasteners
23. Printed checkpoint posters on rigid matte backing

## Numbered build procedure

1. Run `cd ~/Developer/fetch && ./verify_all.sh`; do not build from a failing revision.
2. Keep both batteries and the charger disconnected.
3. Measure the wheel diameter. Continue only if it is 80mm; otherwise update `WHEEL_DIA_MM` and rerun verification.
4. Mount the four JK42HS40 motors: front-left, front-right, rear-left and rear-right.
5. Mount all motor axles parallel.
6. Install the mecanum wheels in an X pattern when viewed from above.
7. Spin every wheel by hand and remove rubbing or binding.
8. Mount the Uno R4 where its USB-C connector remains reachable.
9. Seat the CNC Shield squarely on the Uno without offset or bent pins.
10. Leave the shield's motor-supply-to-Arduino power jumper off.
11. Install MS1 and MS2 jumpers under X, Y, Z and A.
12. Leave MS3 open under X, Y, Z and A.
13. Configure the A socket for independent D12/D13; do not clone X, Y or Z.
14. Identify the orientation of each A4988 from the actual shield labels.
15. Identify the two current-sense resistors on each A4988: R050, R100 or R200.
16. Stop if any driver is marked R200 or if markings cannot be read.
17. Insert all four A4988 modules with identical, correct orientation.
18. Attach one heatsink to each A4988 without shorting pins.
19. Mount the cooling fan so air crosses all four heatsinks.
20. Leave all four motor plugs disconnected.
21. Connect the SM2P mating pigtail to the inline fuse holder using a correctly sized step-down crimp.
22. Put the fuse holder within 10cm of the battery connector.
23. Leave the 7.5A fuse out.
24. Connect the fuse-holder output to the master switch.
25. Connect the switch output to the positive distribution block.
26. Connect the SM2P negative wire to the ground distribution block.
27. Connect positive distribution to CNC Shield motor `+` with 18AWG wire.
28. Connect ground distribution to CNC Shield motor `−` with 18AWG wire.
29. Connect positive distribution to buck `IN+`.
30. Connect ground distribution to buck `IN−`.
31. Connect the 470µF capacitor across the CNC motor terminal: capacitor `+` to motor `+`, striped `−` lead to motor `−`.
32. Verify capacitor polarity twice; a reversed electrolytic can fail violently.
33. Insert the 7.5A fuse and connect one battery.
34. Turn the master switch on without the Pi, Uno USB or motors connected.
35. Measure battery polarity at the CNC terminal; red probe on `+` must show positive voltage.
36. Adjust the buck output to 5.1V with a multimeter.
37. Turn the master switch off and remove the fuse.
38. Connect buck output to the Pi USB-C power input using the buck's supported USB output cable.
39. Connect Pi USB-A to Uno USB-C using the data-capable cable.
40. Connect the UVC webcam to another Pi USB-A port.
41. Mount the webcam rigidly at the front centre with the bin not blocking its view.
42. Connect sensor 5V distribution to the shield 5V rail.
43. Connect sensor ground distribution to shield GND.
44. Mount US1 facing 0° straight forward.
45. Wire US1: VCC→5V, GND→GND, TRIG→D9/X-limit signal, ECHO→D10/Y-limit signal.
46. Mount US2 facing 75° left-front.
47. Wire US2: VCC→5V, GND→GND, TRIG→D11/Z-limit signal, ECHO→A0/Abort.
48. Mount US3 facing 145° left-rear.
49. Wire US3: VCC→5V, GND→GND, TRIG→A1/Hold, ECHO→A2/Resume.
50. Mount US4 facing 215° right-rear.
51. Wire US4: VCC→5V, GND→GND, TRIG→A3/CoolEn, ECHO→D0/RX.
52. Mount US5 facing 285° right-front.
53. Wire US5: VCC→5V, GND→GND, TRIG→D1/TX, ECHO→A4/SDA.
54. Leave A5 unconnected.
55. Confirm end-stop headers supply signal and ground only; no sensor VCC may depend on an end-stop header.
56. Use continuity mode with the motor disconnected to confirm black/green form one JK42HS40 coil and red/blue form the other.
57. Connect black/green to one driver coil pair and red/blue to the other pair for each motor.
58. Lift the chassis so all wheels are clear of the floor.
59. Remove the four motor plugs again before setting Vref.
60. Insert the 7.5A fuse, connect one battery and turn the switch on.
61. Measure Vref between driver potentiometer wiper and GND.
62. Set every R050 driver to 0.510V or every R100 driver to 1.020V.
63. Turn power off and wait for LEDs to extinguish.
64. Reconnect all motor plugs.
65. Flash `firmware/fetch_drive/fetch_drive.ino` to the Uno R4.
66. Boot the Pi and verify the Uno appears as `/dev/ttyACM0`.
67. With wheels lifted, command one motor position at a time and verify X=front-left, Y=front-right, Z=rear-left, A=rear-right.
68. Power off before reversing a motor connector or changing a coil connection.
69. Verify a forward command propels all four wheels forward.
70. Verify a rotation command drives left and right sides oppositely.
71. Verify no A4988 enters thermal shutdown during a ten-minute lifted-wheel test.
72. Test US1 against a flat board at 20cm, 60cm and 100cm.
73. Confirm US1 stops positive forward commands below 60cm.
74. Test US2, US3, US4 and US5 individually against a flat board.
75. Confirm readings change for the correct physical sensor only.
76. Verify the Pi webcam opens as camera 0.
77. Print four checkpoint posters at 100% scale without trimming their white borders.
78. Glue each poster to rigid matte backing.
79. Place markers 0, 1, 2 and 3 approximately 3–5m apart in a simple corridor.
80. Ensure each next AprilTag is visible from the preceding stopped position.
81. Put each destination poster above a broad wall/backboard that US1 can detect.
82. Scan every QR code with the iPhone app.
83. Confirm every AprilTag decodes through the installed Pi webcam.
84. Create the route: `python3 tools/make_topo_map.py --edges 0-1,1-2,2-3 --output topo_map.json`.
85. Check it: `python3 pi/topo_nav.py --map topo_map.json --check`; require `CONNECTED`.
86. Physically park FETCH at marker 0.
87. Start: `python3 pi/topo_server.py --map topo_map.json --camera 0 --serial /dev/ttyACM0 --start-zone 0`.
88. Set `PI_BASE` in `ios/FetchCheckpoint.swift` to the Pi's current IP.
89. Put iPhone and Pi on the same Wi-Fi network.
90. For the first floor test only, set `APPROACH_MMS = 100.0` in `pi/topo_nav.py`, restart the server, scan checkpoint 1 and call FETCH.
91. Test every adjacent edge in both directions before attempting the whole route.
92. Restore `APPROACH_MMS = 200.0`, restart the server and rerun `./verify_all.sh`.
93. Test app cancellation while moving.
94. Disconnect Wi-Fi while moving and require a stop within 500ms plus deceleration.
95. Cover the camera and require route failure without uncontrolled continued travel.
96. Place an obstacle 50cm in front and require forward motion to stop.
97. Test obstacles near each corner sensor during rotation.
98. Confirm the master switch immediately removes motor and compute power.
99. Fully charge one pack with the supplied charger, attended and on a nonflammable surface.
100. Run the exact demo route repeatedly for 20 minutes.
101. Check battery, SM2P connector, fuse holder, buck and A4988 temperatures every five minutes.
102. Stop immediately for swelling, smell, softening, unexpected heat, Pi undervoltage or driver shutdown.
103. Repeat the 20-minute rehearsal using the second pack.
104. Choose the better pack for the judge run and keep the other charged, disconnected and ready for a power-off swap.
105. Run `./verify_all.sh` once more on the final software.
106. Perform two complete successful summons immediately before the judge demo.

## Fixed operating values

| Value | Final setting |
|---|---:|
| Wheel diameter | 80mm |
| Microstepping | 1/4 |
| Firmware speed ceiling | 250mm/s |
| Automatic approach | 200mm/s |
| Slew | 500mm/s² |
| US1 front polling | 50ms |
| Corner polling | one every 80ms |
| Front stop | 60cm |
| Checkpoint arrival | 65cm |
| Side/rear stop | 35cm |
| Rotation stop | 20cm |
| Command watchdog | 500ms |
| Motor current target | 1.275A |
| Fuse | 7.5A |

## Go/no-go

Run for judges only if all five sensors report correctly, all four motors pass direction tests, the camera sees every route edge, the graph is connected, no driver thermally shuts down, the Pi has no undervoltage warning, the selected battery completes 20 minutes and the operator can reach the switch immediately.
