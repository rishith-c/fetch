#!/usr/bin/env python3
"""Validate measured evidence for the assembled FETCH robot.

This intentionally rejects the blank template. A green result is meaningful
only when the operator copied the template and entered observations from the
exact robot and final demo layout. It does not manufacture physical evidence.
"""

import argparse
import json
from pathlib import Path


def get(data, path):
    value = data
    for key in path.split("."):
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    return value


def number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def all_true(data, paths):
    return all(get(data, path) is True for path in paths)


def validate(data):
    gates = []

    def gate(name, passed, detail):
        gates.append((name, bool(passed), detail))

    identity_ok = all(isinstance(get(data, key), str) and get(data, key).strip()
                      for key in ("robot_id", "test_date", "tester"))
    gate("identified measured record", identity_ok,
         "robot_id, test_date, and tester are required")

    rail_values = [number(get(data, f"rails.{key}")) for key in (
        "driver1_idle_v", "driver2_idle_v")]
    load_values = [number(get(data, f"rails.{key}")) for key in (
        "driver1_worst_load_v", "driver2_worst_load_v")]
    rail_ok = (all(value is not None and 6.3 <= value <= 6.7 for value in rail_values)
               and all(value is not None and value >= 5.8 for value in load_values))
    gate("two motor rails", rail_ok,
         f"idle={rail_values}, worst_load={load_values}; need 6.3-6.7 V idle and >=5.8 V load")

    logic_v = number(get(data, "rails.logic_v"))
    logic_ok = (logic_v is not None and 4.8 <= logic_v <= 5.2
                and get(data, "rails.uno_or_pi_resets") is False)
    gate("logic rail and resets", logic_ok,
         f"logic={logic_v}; need 4.8-5.2 V and no resets")

    current = number(get(data, "battery.max_sustained_a"))
    current_ok = (current is not None and current <= 3.0
                  and get(data, "battery.fuse_3a_survived") is True)
    gate("battery current and fuse", current_ok,
         f"max sustained={current}; need <=3.0 A and surviving 3 A fuse")

    sonar_paths = [
        "sonar.front_max_abs_error_cm",
        "sonar.left_front_max_abs_error_cm",
        "sonar.right_front_max_abs_error_cm",
        "sonar.left_rear_max_abs_error_cm",
        "sonar.right_rear_max_abs_error_cm",
    ]
    sonar_errors = [number(get(data, path)) for path in sonar_paths]
    sonar_ok = (all(value is not None and 0 <= value <= 3 for value in sonar_errors)
                and all_true(data, ["sonar.installed_crosstalk_pass",
                                    "sonar.all_directional_stops_pass"]))
    gate("five sonars and cross-talk", sonar_ok,
         f"max errors={sonar_errors}; need <=3 cm plus installed cross-talk and stop passes")

    motion_paths = [
        "motion.forward", "motion.backward", "motion.left_strafe",
        "motion.right_strafe", "motion.clockwise",
        "motion.counterclockwise", "motion.fixed_heading_circle",
    ]
    gate("mecanum motion primitives", all_true(data, motion_paths),
         "F/B/L/R/CW/CCW/fixed-heading-circle must all be true")

    width = number(get(data, "vision_and_routes.camera_width"))
    height = number(get(data, "vision_and_routes.camera_height"))
    edge_count = number(get(data, "vision_and_routes.directed_edges_total"))
    edge_runs = number(get(data, "vision_and_routes.minimum_successful_runs_per_edge"))
    route_ok = (width is not None and width >= 1280 and height is not None and height >= 720
                and edge_count is not None and edge_count >= 1
                and edge_runs is not None and edge_runs >= 2
                and get(data, "vision_and_routes.all_edges_pass_in_demo_lighting") is True)
    gate("camera and every directed edge", route_ok,
         f"camera={width}x{height}, edges={edge_count}, min runs={edge_runs}")

    stop_limits = {
        "failure_stops.camera_cover_stop_s": 1.0,
        "failure_stops.uno_usb_disconnect_stop_s": 1.0,
        "failure_stops.phone_loss_stop_s": 2.5,
        "failure_stops.app_cancel_stop_s": 1.0,
    }
    stops = {path: number(get(data, path)) for path in stop_limits}
    stops_ok = (all(stops[path] is not None and 0 <= stops[path] <= limit
                    for path, limit in stop_limits.items())
                and get(data, "failure_stops.obstacle_not_arrival") is True)
    gate("all failure stops", stops_ok,
         f"measured seconds={stops}; obstacle_not_arrival must be true")

    arrival_ok = all_true(data, [
        "arrival.correct_tag_required",
        "arrival.center_area_range_hold_required",
        "arrival.wrong_checkpoint_rejected",
    ])
    gate("arrival integrity", arrival_ok,
         "correct tag, combined gate, and wrong-checkpoint rejection required")

    mass = number(get(data, "payload.complete_robot_mass_g"))
    payload_ok = (mass is not None and 0 < mass <= 1500
                  and get(data, "payload.traction_pass") is True)
    gate("payload and traction", payload_ok,
         f"mass={mass} g; need <=1500 g and traction pass")

    runtime = number(get(data, "battery.runtime_min"))
    battery_temp = number(get(data, "battery.battery_max_c"))
    l298_temp = number(get(data, "thermal.hottest_l298_c"))
    xl_temp = number(get(data, "thermal.hottest_xl4015_c"))
    after_v = number(get(data, "battery.resting_after_run_v"))
    runtime_ok = (
        runtime is not None and runtime >= 20
        and battery_temp is not None and battery_temp <= 45
        and l298_temp is not None and l298_temp <= 70
        and xl_temp is not None and xl_temp <= 70
        and after_v is not None and after_v >= 10.5
        and get(data, "battery.connectors_cool") is True
        and get(data, "thermal.motor_odor_or_shutdown") is False
    )
    gate("20-minute thermal/runtime", runtime_ok,
         f"runtime={runtime} min, battery={battery_temp} C, L298={l298_temp} C, "
         f"XL4015={xl_temp} C, rested after={after_v} V")

    network_ok = all_true(data, [
        "network.private_network_used",
        "network.full_route_coverage_pass",
        "network.phone_and_pi_client_to_client_pass",
    ])
    gate("private network full-route coverage", network_ok,
         "private network, coverage, and client-to-client communication required")

    checkpoints = number(get(data, "summons.checkpoint_count"))
    pairs = number(get(data, "summons.source_destination_pairs_tested"))
    expected_pairs = None if checkpoints is None else int(checkpoints * (checkpoints - 1))
    summons_ok = (checkpoints is not None and checkpoints >= 2
                  and pairs is not None and pairs >= expected_pairs
                  and get(data, "summons.all_source_destination_pairs_pass") is True)
    gate("every source-to-destination summon", summons_ok,
         f"checkpoints={checkpoints}, tested pairs={pairs}, required={expected_pairs}")

    return gates


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("record", type=Path,
                        help="completed JSON copied from commissioning/acceptance_template.json")
    args = parser.parse_args()
    with args.record.open(encoding="utf-8") as handle:
        data = json.load(handle)
    gates = validate(data)
    for name, passed, detail in gates:
        print(f"{'PASS' if passed else 'FAIL'}  {name}: {detail}")
    failed = [name for name, passed, _ in gates if not passed]
    print(f"\n{len(gates) - len(failed)}/{len(gates)} physical acceptance gates pass")
    if failed:
        print("NOT DEMO-READY; unresolved gates:")
        for name in failed:
            print(" -", name)
        raise SystemExit(1)
    print("PHYSICAL ACCEPTANCE RECORD PASSES for the identified robot and layout.")


if __name__ == "__main__":
    main()
