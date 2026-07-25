# FETCH research and completion audit

Last software audit: 2026-07-23. Final selected prototype: TT mecanum chassis,
Uno R4, two L298N modules, two 6.5 V XL4015 rails, five HC-SR04 sensors, Pi 4
camera navigation, and the iPhone checkpoint app.

## Requirement interpretation

“Press a button when neither I nor the robot can see the other, and have the
robot come to me” is implemented as **checkpoint rendezvous**:

1. The person scans the QR on the nearest mapped poster.
2. The app sends that fixed checkpoint ID to the robot over private Wi-Fi.
3. The robot independently sees AprilTags with its forward camera and follows a
   pre-commissioned directed graph.
4. The person and robot never need line of sight to one another.
5. The final tag plus front-sonar range proves arrival at the poster.

This does not infer the phone's indoor coordinates and does not track a moving
person. That distinction is fundamental: without venue infrastructure, a phone
does not provide reliable mall-scale indoor position to this robot. A scanned
known checkpoint turns an underdetermined localization problem into a bounded
routing problem suitable for the hackathon.

## Research decisions

| Topic | Primary evidence | Decision in this build |
|---|---|---|
| Visual fiducials | [AprilTag 3 project](https://github.com/AprilRobotics/apriltag) documents small-tag improvements and OpenCV integration; [OpenCV ArUco detection](https://docs.opencv.org/4.x/d5/dae/tutorial_aruco_detection.html) provides dictionary-based marker detection. | Use OpenCV's built-in `DICT_APRILTAG_36h11` end-to-end so poster generation and Pi detection use the identical available family. Use a measured 180 mm tag and require route camera tests. |
| Camera geometry | Pinhole projection from the requested 1280 px width and assumed 70° horizontal FOV. | A 180 mm tag models as 54.8 px at 3 m. The Pi rejects a camera stream below 1280×720. Initial checkpoint spacing is 2–3 m; 5 m is only an experimentally proven extension. |
| Ultrasonic timing | [HC-SR04 datasheet](https://www.digikey.in/en/htmldatasheets/production/1979760/0/0/1/hc-sr04.html) specifies a 10 µs trigger, 40 kHz burst, nominal 2–400 cm range, and recommends a measurement cycle over 60 ms. | Trigger all five for 10 µs every 65 ms and capture all five echoes concurrently. Installed cross-talk testing remains mandatory. |
| Uno electrical/pins | [Arduino Uno R4 Minima datasheet](https://docs.arduino.cc/resources/datasheets/ABX00080-datasheet.pdf) identifies 5 V operation, PWM-capable pins, analog pins usable as GPIO, and per-pin current limits. | Use PWM D5/D6/D9/D10, eight other motor-direction GPIO, D3 shared trigger, and D11/A2–A5 echoes. L298 logic inputs—not motors—load the GPIO. |
| Motor driver loss | [ST L298 datasheet](https://www.st.com/resource/en/datasheet/l298.pdf) gives a typical total bridge drop of about 1.8 V at 1 A and larger worst-case drops, logic supply requirements, current limits, and thermal protection. | Two L298Ns are accepted because they are already selected, but they are inefficient and require measured current/heat. A 6.5 V driver rail yields about 4.7 V at a typical 1 A bridge load. |
| DC conversion | [XL4015 datasheet](https://www.xlsemi.com/datasheet/XL4015-EN.pdf) specifies an adjustable step-down regulator and headline 5 A capability under suitable implementation/thermal conditions. | Use two modules, one per L298N, never paralleled. Adjust each unloaded to 6.50 V and validate voltage and temperature under final load. Module marketing is not accepted as proof of continuous current. |
| Chassis/motors | [Hiwonder chassis listing](https://www.hiwonder.com/products/mecanum-wheel-smart-chassis-car) specifies four 3–6 V 1:120 TT motors, 120–240 RPM, 66 mm wheels, 180 × 140 × 89 mm chassis, and a claimed 1500 g capacity. | Treat 3–6 V and 1500 g as bounds that still require assembled payload and traction tests. |
| Pi power | [Raspberry Pi power documentation](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html) specifies the Pi 4's recommended 5.1 V / 3 A supply. | Use a separate power bank for Pi/camera/Uno compute; keep noisy motor power on the battery/converters. Grounds meet through Pi USB→Uno→L298 logic. |
| iPhone local network | Apple requires a [local-network usage description](https://developer.apple.com/documentation/BundleResources/Information-Property-List/NSLocalNetworkUsageDescription) and documents [`NSAllowsLocalNetworking`](https://developer.apple.com/documentation/bundleresources/information-property-list/nsapptransportsecurity/nsallowslocalnetworking) for `.local`/local resources. | Generated Xcode project contains both keys. The app uses `http://fetch.local:8080` on a private demo router/hotspot. Internet-wide ATS is not disabled. |
| Battery connector | The pack seller has not supplied an independently verified BMS-current or connector-current specification. | Begin with a 3 A fuse, use only the matching charger, never parallel packs, measure real current/heat, and do not increase the fuse without exact component ratings. |

## Software evidence

`./verify_all.sh` currently proves:

- 13/13 deterministic pin, camera, stopping-envelope, runtime, converter, and
  L298 voltage calculations pass.
- 16/16 navigation, multi-hop out-of-sight routing, directed-graph, stale-data, arrival, obstacle, serial,
  heartbeat, and live HTTP API tests pass.
- `tt_fetch_drive.ino` compiles for Uno R4 Minima at 18% flash and 13% RAM.
- Pi server, navigation, and map tools compile; a sample graph validates.
- Swift source typechecks and the generated Xcode project builds for an iOS
  Simulator target with required permission keys.
- All 12 generated AprilTags detect and all 12 QR payloads decode.
- The README, verifier, firmware, Pi service, app, posters, and final manual all
  name the same two-L298N baseline.

These checks are authoritative evidence for software structure and deterministic
models only. They are not evidence of physical performance.

## Requirement-by-requirement status

| Objective requirement | Evidence | Status |
|---|---|---|
| App selects where the person is | QR parser accepts only `FETCH:<nonnegative id>`; generated posters encode matching payloads. | Software proven |
| Button summons while robot is out of sight | App `POST /come`; HTTP integration test; route runs from current checkpoint to requested ID without person/robot line of sight. | Software proven; venue route pending |
| Robot knows where it is | It starts at an operator-confirmed `--start-zone` and updates `at` only after gated tag arrival. Fresh visible tags support localization search. | Software proven; camera route pending |
| Robot knows how to reach every checkpoint | Directed BFS plus strong-connectivity validation. | Software proven; physical directed edges pending |
| Robot follows wall codes | OpenCV AprilTag detector, centered visual steering, 1280×720 preflight, regenerated tags. | Software proven; actual camera/lighting pending |
| Obstacle is not confused with arrival | Arrival requires correct tag area, centering, 65±12 cm sonar, and 0.35 s hold; close small-tag obstacle test passes. | Software proven; physical obstacle test pending |
| Loss of Pi commands stops motors | Uno 500 ms watchdog. | Code/compile proven; unplug test pending |
| Loss of camera/telemetry stops route | 0.5 s freshness checks and tests. | Software proven; hardware disconnect tests pending |
| Loss of phone stops route | 2 s server heartbeat watchdog and integration test. | Software proven; real Wi-Fi/app-background test pending |
| Two L298Ns and five sonars fit Uno | 18 unique GPIO signals, correct PWM set, no overlap, firmware compiled. | Proven electrically at signal-map level |
| Battery runs 20 minutes | Energy model predicts 32 minutes even at 3 A using 80% capacity. | Model only; loaded 20-minute run pending |
| Electrical path is safe enough for demo | Fused, switched, isolated motor rails, separate Pi rail, common ground, required capacitors/jumpers documented. | Design reviewed; measurements/thermal pending |
| Entire supervised hackathon demo works | 1–150 manual and go/no-go sheet define exact acceptance. | **Not yet proven physically** |

## Hard limits and residual risks

- HC-SR04 has no diagnostic distinction between open space and a disconnected or
  acoustically failed sensor; preflight targets and an operator cutoff are
  therefore required.
- Five simultaneous ultrasonic transmitters can cross-talk. If installed tests
  show unsafe false clears, the hardware must change; software cannot certify it.
- L298N voltage loss and TT stall current are highly load-dependent. The exact
  motor stall current and pack BMS rating remain unknown until measured/sourced.
- No wheel encoders or IMU exist. The robot can visually home between tags but
  cannot guarantee a metrically accurate path through an unmarked blind segment.
- The graph is only valid for the exact poster positions, camera height, lighting,
  and cleared straight segments that were commissioned.
- Guest mall Wi-Fi may isolate clients. Use a private travel router/hotspot whose
  full-route coverage has been tested.
- HTTP control is unauthenticated and intentionally limited to a private demo
  network. It is not a production security architecture.
- Five hobby sonars and software stops do not constitute certified personnel
  protection. Keep the route controlled and an operator on the physical switch.

## Completion rule

The objective is complete only after every blank in the final manual's go/no-go
record contains measured evidence from this exact assembled robot and every
source-to-destination summon passes in the actual demo layout. Until then the
correct claim is **software-verified, physically pending**.
