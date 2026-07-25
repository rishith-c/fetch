import importlib
import json
import pathlib
import sys
import threading
import time
import types
import unittest
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pi"))
sys.path.insert(0, str(ROOT / "tools"))

# The behavior tests use fakes; importing topo_server must not require the Mac
# to have the Pi's camera and serial packages installed.
if "cv2" not in sys.modules:
    sys.modules["cv2"] = types.ModuleType("cv2")
if "serial" not in sys.modules:
    serial_stub = types.ModuleType("serial")
    serial_stub.SerialException = OSError
    serial_stub.Serial = object
    sys.modules["serial"] = serial_stub

from topo_nav import TopoMap, TopoNav
topo_server = importlib.import_module("topo_server")
commissioning_validator = importlib.import_module("validate_commissioning")


class FakeVision:
    def __init__(self, detection=None, fresh=True, resolution_ok=True):
        self.detection = detection
        self.is_fresh = fresh
        self.is_resolution_ok = resolution_ok

    def fresh(self):
        return self.is_fresh

    def resolution_ok(self):
        return self.is_resolution_ok

    def resolution(self):
        return [1280, 720] if self.is_resolution_ok else [640, 480]

    def detect(self, marker_id):
        if self.detection is None:
            return None
        result = dict(self.detection)
        result["id"] = marker_id
        return result

    def visible_detections(self):
        return [] if self.detection is None else [dict(self.detection, id=0)]


class FakeDrive:
    def __init__(self, front=65, estop=False, fresh=True):
        self.front = front
        self.is_estop = estop
        self.is_fresh = fresh
        self.commands = []

    def fresh(self):
        return self.is_fresh

    def estop(self):
        return self.is_estop

    def front_cm(self):
        return self.front

    def sonar_cm(self):
        return [self.front, 0, 0, 0, 0]

    def cmd(self, vx, vy, omega):
        self.commands.append((vx, vy, omega))

    def stop(self):
        self.cmd(0, 0, 0)


class SimulatedRouteWorld:
    """Small deterministic closed loop for a multi-hop out-of-sight route."""

    def __init__(self):
        self.target = None
        self.front = 180
        self.offset = 0.45
        self.area = 0.002
        self.search_steps = 0
        self.targets_seen = []
        self.commands = []

    def _select(self, marker_id):
        if marker_id != self.target:
            self.target = marker_id
            self.front = 180
            self.offset = 0.45
            self.area = 0.002
            self.search_steps = 0
            self.targets_seen.append(marker_id)

    # Vision interface
    def fresh(self):
        return True

    def resolution_ok(self):
        return True

    def resolution(self):
        return [1280, 720]

    def visible_detections(self):
        return []

    def detect(self, marker_id):
        self._select(marker_id)
        if self.search_steps < 3:
            return None
        return {"id": marker_id, "offset": self.offset,
                "area_fraction": self.area}

    # Drive/telemetry interface
    def estop(self):
        return False

    def front_cm(self):
        return int(self.front)

    def sonar_cm(self):
        return [int(self.front), 0, 0, 0, 0]

    def cmd(self, vx, vy, omega):
        self.commands.append((vx, vy, omega))
        if abs(omega) > 1 and abs(vx) < 1:
            self.search_steps += 1
        if self.search_steps >= 3 and abs(omega) > 1:
            self.offset += omega * 0.0025
            self.offset = max(-0.8, min(0.8, self.offset))
        if vx > 1:
            self.front = max(55, self.front - 25)
            self.area = 0.002 + (180 - self.front) * 0.000085

    def stop(self):
        self.cmd(0, 0, 0)


class TopologyTests(unittest.TestCase):
    def test_out_of_sight_multihop_search_approach_and_arrival(self):
        graph = TopoMap({0: [1], 1: [0, 2], 2: [1]})
        world = SimulatedRouteWorld()
        nav = TopoNav(graph, world, world, world)
        nav.at = 0
        nav.CONTROL_PERIOD_S = 0.001
        nav.ARRIVE_HOLD_SECONDS = 0.003
        nav.HOP_TIMEOUT_S = 1.0
        self.assertTrue(nav.go(2))
        self.assertEqual(nav.at, 2)
        self.assertEqual(world.targets_seen, [1, 2])
        self.assertTrue(any(vx > 0 for vx, _, _ in world.commands))
        self.assertTrue(any(abs(omega) > 0 for _, _, omega in world.commands))
        self.assertEqual(world.commands[-1], (0, 0, 0))
    def test_directed_map_rejects_missing_return_route(self):
        graph = TopoMap({0: [1], 1: []})
        ok, missing = graph.connected()
        self.assertFalse(ok)
        self.assertIn((1, 0), missing)

    def test_bidirectional_chain_routes_every_way(self):
        graph = TopoMap({0: [1], 1: [0, 2], 2: [1, 3], 3: [2]})
        self.assertEqual(graph.path(0, 3), [1, 2, 3])
        self.assertEqual(graph.path(3, 0), [2, 1, 0])
        self.assertEqual(graph.validate(), [])

    def test_obstacle_is_not_reported_as_arrival(self):
        graph = TopoMap({0: [1], 1: [0]})
        vision = FakeVision({"offset": 0.0, "area_fraction": 0.001})
        drive = FakeDrive(front=50)
        nav = TopoNav(graph, vision, drive, drive)
        nav.at = 0
        nav.BLOCKED_CONFIRM_S = 0.002
        nav.CONTROL_PERIOD_S = 0.001
        with self.assertRaisesRegex(RuntimeError, "route blocked"):
            nav.go(1)
        self.assertEqual(drive.commands[-1], (0, 0, 0))

    def test_arrival_needs_center_area_range_and_hold(self):
        graph = TopoMap({0: [1], 1: [0]})
        vision = FakeVision({"offset": 0.01, "area_fraction": 0.02})
        drive = FakeDrive(front=65)
        nav = TopoNav(graph, vision, drive, drive)
        nav.at = 0
        nav.ARRIVE_HOLD_SECONDS = 0.003
        nav.CONTROL_PERIOD_S = 0.001
        self.assertTrue(nav.go(1))
        self.assertEqual(nav.at, 1)
        self.assertEqual(drive.commands[-1], (0, 0, 0))

    def test_stale_camera_stops_route(self):
        graph = TopoMap({0: [1], 1: [0]})
        vision = FakeVision(fresh=False)
        drive = FakeDrive()
        nav = TopoNav(graph, vision, drive, drive)
        nav.at = 0
        with self.assertRaisesRegex(RuntimeError, "camera"):
            nav.go(1)

    def test_stale_uno_stops_route(self):
        graph = TopoMap({0: [1], 1: [0]})
        vision = FakeVision({"offset": 0, "area_fraction": 0.02})
        drive = FakeDrive(fresh=False)
        nav = TopoNav(graph, vision, drive, drive)
        nav.at = 0
        with self.assertRaisesRegex(RuntimeError, "telemetry"):
            nav.go(1)


class ProtocolTests(unittest.TestCase):
    def test_strict_telemetry_packet(self):
        parse = topo_server.UnoDriveTelemetry.parse_packet
        self.assertEqual(parse("S 65 40 41 42 43 0"),
                         ([65, 40, 41, 42, 43], False))
        self.assertIsNone(parse("us f=65 lf=40"))
        self.assertIsNone(parse("S 65 40 41 42 1"))
        self.assertIsNone(parse("S 65 40 41 42 43 2"))

    def test_firmware_and_server_protocol_match(self):
        firmware = (ROOT / "firmware/tt_fetch_drive/tt_fetch_drive.ino").read_text()
        server = (ROOT / "pi/topo_server.py").read_text()
        self.assertIn('Serial.print("S")', firmware)
        self.assertIn('f"V {vx:.1f} {vy:.1f} {omega:.1f}', server)
        self.assertIn("PACKET_FIELDS = 7", server)

    def test_actual_pin_ledger_has_no_conflicts(self):
        motors = {5, 2, 4, 6, 7, 8, 9, 12, 13, 10, 14, 15}  # A0=14 A1=15
        sonars = {3, 11, 16, 17, 18, 19}                    # A2..A5
        self.assertEqual(len(motors), 12)
        self.assertEqual(len(sonars), 6)
        self.assertTrue(motors.isdisjoint(sonars))
        self.assertEqual(motors | sonars, set(range(2, 20)))

    def test_sonar_repeat_period_meets_datasheet(self):
        firmware = (ROOT / "firmware/tt_fetch_drive/tt_fetch_drive.ino").read_text()
        self.assertIn("SONAR_PERIOD_MS = 65", firmware)
        self.assertNotIn("pulseIn(", firmware)


class ControllerTests(unittest.TestCase):
    def test_preflight_rejects_low_camera_resolution(self):
        graph = TopoMap({0: []})
        vision = FakeVision({"offset": 0, "area_fraction": 0.02},
                            resolution_ok=False)
        drive = FakeDrive()
        nav = TopoNav(graph, vision, drive, drive)
        nav.at = 0
        controller = topo_server.Controller(nav, drive, vision)
        controller.running = False
        with self.assertRaisesRegex(RuntimeError, "1280x720"):
            controller.come(0)

    def test_preflight_rejects_estop(self):
        graph = TopoMap({0: []})
        vision = FakeVision({"offset": 0, "area_fraction": 0.02})
        drive = FakeDrive(estop=True)
        nav = TopoNav(graph, vision, drive, drive)
        nav.at = 0
        controller = topo_server.Controller(nav, drive, vision)
        controller.running = False
        with self.assertRaisesRegex(RuntimeError, "obstacle"):
            controller.come(0)

    def test_phone_watchdog_stops_active_route(self):
        graph = TopoMap({0: [1], 1: [0]})
        vision = FakeVision(detection=None)
        drive = FakeDrive()
        nav = TopoNav(graph, vision, drive, drive)
        nav.at = 0
        nav.CONTROL_PERIOD_S = 0.001
        controller = topo_server.Controller(nav, drive, vision)
        controller.PHONE_TIMEOUT_S = 0.02
        controller.come(1)
        deadline = time.monotonic() + 0.3
        while time.monotonic() < deadline and controller.status()["state"] == "ROUTING":
            time.sleep(0.005)
        status = controller.status()
        controller.running = False
        self.assertEqual(status["state"], "FAILED")
        self.assertEqual(status["error"], "phone heartbeat lost")
        self.assertEqual(drive.commands[-1], (0, 0, 0))


class HTTPIntegrationTests(unittest.TestCase):
    def test_phone_status_come_cancel_and_invalid_zone(self):
        graph = TopoMap({0: []})
        vision = FakeVision({"offset": 0, "area_fraction": 0.02})
        drive = FakeDrive(front=65)
        nav = TopoNav(graph, vision, drive, drive)
        nav.at = 0
        controller = topo_server.Controller(nav, drive, vision)
        server = topo_server.make_server(controller, "127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"

        def call(path, method="GET", payload=None):
            body = None if payload is None else json.dumps(payload).encode()
            request = urllib.request.Request(
                base + path, data=body, method=method,
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(request, timeout=1.0) as response:
                return response.status, json.loads(response.read())

        try:
            status, value = call("/status")
            self.assertEqual(status, 200)
            self.assertEqual(value["camera_resolution"], [1280, 720])

            status, value = call("/come", "POST", {"zone": 0})
            self.assertEqual(status, 202)
            deadline = time.monotonic() + 0.5
            while time.monotonic() < deadline:
                _, value = call("/status")
                if value["state"] == "ARRIVED":
                    break
                time.sleep(0.005)
            self.assertEqual(value["state"], "ARRIVED")

            status, value = call("/cancel", "POST", {})
            self.assertEqual(status, 200)
            self.assertEqual(value["state"], "IDLE")

            with self.assertRaises(urllib.error.HTTPError) as raised:
                call("/come", "POST", {"zone": 99})
            self.assertEqual(raised.exception.code, 400)
        finally:
            controller.running = False
            server.shutdown()
            server.server_close()


class CommissioningRecordTests(unittest.TestCase):
    def test_blank_record_is_rejected_and_complete_record_passes(self):
        template_path = ROOT / "commissioning/acceptance_template.json"
        data = json.loads(template_path.read_text())
        self.assertTrue(all(not passed for _, passed, _
                            in commissioning_validator.validate(data)))

        data.update(robot_id="FETCH-01", test_date="2026-07-23", tester="operator")
        data["rails"].update(
            driver1_idle_v=6.5, driver1_worst_load_v=6.1,
            driver2_idle_v=6.5, driver2_worst_load_v=6.1,
            logic_v=5.0, uno_or_pi_resets=False)
        data["battery"].update(
            resting_full_v=12.5, resting_after_run_v=11.0,
            max_sustained_a=2.8, fuse_3a_survived=True, runtime_min=22,
            battery_max_c=38, connectors_cool=True)
        data["thermal"].update(
            hottest_l298_c=62, hottest_xl4015_c=55,
            motor_odor_or_shutdown=False)
        data["sonar"].update(
            front_max_abs_error_cm=2, left_front_max_abs_error_cm=2,
            right_front_max_abs_error_cm=2, left_rear_max_abs_error_cm=2,
            right_rear_max_abs_error_cm=2, installed_crosstalk_pass=True,
            all_directional_stops_pass=True)
        for key in data["motion"]:
            data["motion"][key] = True
        data["vision_and_routes"].update(
            camera_width=1280, camera_height=720, directed_edges_total=6,
            minimum_successful_runs_per_edge=2,
            all_edges_pass_in_demo_lighting=True)
        data["failure_stops"].update(
            camera_cover_stop_s=0.6, uno_usb_disconnect_stop_s=0.6,
            phone_loss_stop_s=2.2, app_cancel_stop_s=0.4,
            obstacle_not_arrival=True)
        for key in data["arrival"]:
            data["arrival"][key] = True
        data["payload"].update(complete_robot_mass_g=1100, traction_pass=True)
        for key in data["network"]:
            data["network"][key] = True
        data["summons"].update(
            checkpoint_count=4, source_destination_pairs_tested=12,
            all_source_destination_pairs_pass=True)

        gates = commissioning_validator.validate(data)
        self.assertEqual(len(gates), 13)
        self.assertTrue(all(passed for _, passed, _ in gates))


if __name__ == "__main__":
    unittest.main()
