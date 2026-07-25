#!/usr/bin/env python3
"""Create a remappable FETCH checkpoint graph without coordinates.

Example for a corridor chain with one branch:
  python3 tools/make_topo_map.py --edges 0-1,1-2,2-3,2-4 --output topo_map.json
"""
import argparse
import json


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--edges", required=True,
                    help="comma-separated visible pairs, e.g. 0-1,1-2,2-3")
    ap.add_argument("--output", default="topo_map.json")
    args = ap.parse_args()
    adj = {}
    for item in args.edges.split(","):
        try:
            a, b = (int(v.strip()) for v in item.split("-", 1))
        except ValueError as exc:
            raise SystemExit(f"bad edge {item!r}; expected ID-ID") from exc
        if a == b:
            raise SystemExit(f"self-edge {a}-{b} is not useful")
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)
    if not adj:
        raise SystemExit("map has no checkpoints")
    root = next(iter(adj))
    seen, stack = {root}, [root]
    while stack:
        for nxt in adj[stack.pop()]:
            if nxt not in seen:
                seen.add(nxt); stack.append(nxt)
    missing = sorted(set(adj) - seen)
    if missing:
        raise SystemExit(f"map disconnected; unreachable checkpoints: {missing}")
    data = {
        "_README": "Topological checkpoint graph. Edge A-B means each poster can be acquired from the other checkpoint.",
        "adj": {str(k): sorted(v) for k, v in sorted(adj.items())},
        "names": {str(k): f"ZONE {k}" for k in sorted(adj)},
    }
    with open(args.output, "w") as fp:
        json.dump(data, fp, indent=2)
    print(f"wrote {args.output}: {len(adj)} checkpoints, {sum(map(len, adj.values())) // 2} edges")


if __name__ == "__main__":
    main()
