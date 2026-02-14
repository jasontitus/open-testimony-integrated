#!/usr/bin/env python3
"""
Scan the API access log and flag requests from IPs outside the local LAN.

Usage:
    # Copy API log and scan together with local bridge log:
    docker compose cp api:/app/logs/access.jsonl ./api-access.jsonl
    python3 scripts/scan-access-log.py ./api-access.jsonl bridge/logs/access.jsonl

    # Or just one log file:
    python3 scripts/scan-access-log.py bridge/logs/access.jsonl

    # With options:
    python3 scripts/scan-access-log.py access.jsonl --lan 10.0.0.0/8 --lan 192.168.1.0/24 --json

By default the following ranges are considered "local LAN":
    127.0.0.0/8, 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, ::1/128, fe80::/10
"""

import argparse
import ipaddress
import json
import sys
from collections import defaultdict

# RFC 1918 + loopback + link-local ranges
DEFAULT_LAN_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    # IPv6
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fe80::/10"),
]


def is_lan_ip(ip_str: str, lan_networks: list) -> bool:
    """Return True if ip_str falls within any of the given LAN networks."""
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return any(addr in net for net in lan_networks)


def parse_args():
    p = argparse.ArgumentParser(
        description="Scan Open Testimony API access logs for non-LAN requests."
    )
    p.add_argument(
        "logfile",
        nargs="+",
        help="Path(s) to access.jsonl log file(s). Multiple files are merged.",
    )
    p.add_argument(
        "--lan",
        action="append",
        metavar="CIDR",
        help="Additional CIDR range to treat as local LAN (can be repeated). "
        "The default RFC-1918 ranges are always included.",
    )
    p.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output results as JSON instead of a human-readable table.",
    )
    p.add_argument(
        "--all",
        action="store_true",
        dest="show_all",
        help="Show all requests, not just non-LAN ones.",
    )
    p.add_argument(
        "--summary",
        action="store_true",
        help="Show only a summary of non-LAN IPs and request counts.",
    )
    return p.parse_args()


def main():
    args = parse_args()

    # Build the LAN network list
    lan_networks = list(DEFAULT_LAN_NETWORKS)
    if args.lan:
        for cidr in args.lan:
            try:
                lan_networks.append(ipaddress.ip_network(cidr, strict=False))
            except ValueError:
                print(f"WARNING: Invalid CIDR '{cidr}', skipping.", file=sys.stderr)

    # Read and parse the log file(s)
    entries = []
    line_num = 0
    for logfile in args.logfile:
        with open(logfile) as f:
            for line in f:
                line_num += 1
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    entries.append(entry)
                except json.JSONDecodeError:
                    print(f"WARNING: Skipping malformed line {line_num}", file=sys.stderr)

    if not entries:
        print("No log entries found.")
        return

    # Classify entries
    non_lan_entries = []
    ip_stats = defaultdict(lambda: {"count": 0, "paths": defaultdict(int)})

    for entry in entries:
        ip = entry.get("ip", "unknown")
        is_local = is_lan_ip(ip, lan_networks)

        if not is_local:
            non_lan_entries.append(entry)
            ip_stats[ip]["count"] += 1
            path = entry.get("path", "?")
            query = entry.get("query")
            full_path = f"{path}?{query}" if query else path
            ip_stats[ip]["paths"][full_path] += 1

        if args.show_all and is_local:
            # Still collect for --all mode
            pass

    total = len(entries)
    external = len(non_lan_entries)
    unique_ips = len(ip_stats)

    # --- Output ---
    if args.json_output:
        result = {
            "total_requests": total,
            "non_lan_requests": external,
            "unique_non_lan_ips": unique_ips,
            "by_ip": {
                ip: {
                    "count": data["count"],
                    "paths": dict(data["paths"]),
                }
                for ip, data in sorted(ip_stats.items(), key=lambda x: -x[1]["count"])
            },
            "requests": non_lan_entries if not args.summary else [],
        }
        print(json.dumps(result, indent=2))
        return

    # Human-readable output
    print("=" * 72)
    print("  Open Testimony Access Log — Non-LAN IP Report")
    print("=" * 72)
    print(f"  Total requests scanned : {total}")
    print(f"  Non-LAN requests       : {external}")
    print(f"  Unique non-LAN IPs     : {unique_ips}")
    print()

    if external == 0:
        print("  All requests came from local LAN addresses.")
        print("=" * 72)
        return

    # Per-IP summary
    print("-" * 72)
    print("  Non-LAN IPs Summary")
    print("-" * 72)
    for ip, data in sorted(ip_stats.items(), key=lambda x: -x[1]["count"]):
        print(f"\n  IP: {ip}  ({data['count']} requests)")
        for path, count in sorted(data["paths"].items(), key=lambda x: -x[1]):
            print(f"      {count:>4}x  {path}")

    if not args.summary:
        # Full request detail
        print()
        print("-" * 72)
        print("  Non-LAN Request Details")
        print("-" * 72)
        print(f"  {'Timestamp':<26} {'IP':<18} {'Method':<7} {'Status':<6} {'Path'}")
        print(f"  {'-'*25} {'-'*17} {'-'*6} {'-'*5} {'-'*30}")
        for e in non_lan_entries:
            ts = e.get("ts", "?")[:25]
            ip = e.get("ip", "?")
            method = e.get("method", "?")
            status = e.get("status", "?")
            path = e.get("path", "?")
            query = e.get("query")
            if query:
                path = f"{path}?{query}"
            print(f"  {ts:<26} {ip:<18} {method:<7} {status:<6} {path}")

    print()
    print("=" * 72)


if __name__ == "__main__":
    main()
