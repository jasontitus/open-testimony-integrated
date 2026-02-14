#!/usr/bin/env python3
"""
Search analytics — shows top search terms, search mode breakdown, and trends.

Queries the search_queries table in postgres directly.

Usage:
    python3 scripts/search-analytics.py
    python3 scripts/search-analytics.py --days 7
    python3 scripts/search-analytics.py --json
    python3 scripts/search-analytics.py --top 20
"""

import argparse
import json
import os
import sys
from collections import defaultdict

try:
    import psycopg2
except ImportError:
    print("ERROR: psycopg2 not installed. Run: pip install psycopg2-binary", file=sys.stderr)
    sys.exit(1)


def get_connection():
    """Connect to the Open Testimony postgres database."""
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=os.environ.get("DB_PORT", "5432"),
        dbname=os.environ.get("DB_NAME", "opentestimony"),
        user=os.environ.get("DB_USER", "admin"),
        password=os.environ.get("DB_PASSWORD", "admin"),
    )


def main():
    p = argparse.ArgumentParser(description="Search analytics for Open Testimony")
    p.add_argument("--days", type=int, default=None,
                   help="Only show queries from the last N days (default: all)")
    p.add_argument("--top", type=int, default=10,
                   help="Number of top queries to show (default: 10)")
    p.add_argument("--json", action="store_true", dest="json_output",
                   help="Output as JSON")
    args = p.parse_args()

    conn = get_connection()
    cur = conn.cursor()

    # Check if table exists
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = 'search_queries'
        )
    """)
    if not cur.fetchone()[0]:
        print("No search_queries table found. Start the bridge to create it.")
        return

    time_filter = ""
    if args.days:
        time_filter = f"WHERE created_at >= NOW() - INTERVAL '{args.days} days'"

    # Total searches
    cur.execute(f"SELECT COUNT(*) FROM search_queries {time_filter}")
    total = cur.fetchone()[0]

    if total == 0:
        print("No search queries recorded yet.")
        return

    # Top search terms (case-insensitive, grouped)
    cur.execute(f"""
        SELECT LOWER(query_text) AS term, COUNT(*) AS cnt,
               ROUND(AVG(result_count)) AS avg_results,
               ROUND(AVG(duration_ms)) AS avg_ms
        FROM search_queries
        {time_filter}
        GROUP BY LOWER(query_text)
        ORDER BY cnt DESC
        LIMIT %s
    """, (args.top,))
    top_terms = cur.fetchall()

    # Search mode breakdown
    cur.execute(f"""
        SELECT search_mode, COUNT(*) AS cnt,
               ROUND(AVG(duration_ms)) AS avg_ms
        FROM search_queries
        {time_filter}
        GROUP BY search_mode
        ORDER BY cnt DESC
    """)
    mode_breakdown = cur.fetchall()

    # Zero-result queries (potential gaps in the index)
    cur.execute(f"""
        SELECT LOWER(query_text) AS term, COUNT(*) AS cnt
        FROM search_queries
        {"WHERE" if not time_filter else time_filter + " AND"} result_count = 0
        GROUP BY LOWER(query_text)
        ORDER BY cnt DESC
        LIMIT %s
    """.replace("WHERE WHERE", "WHERE"), (args.top,))
    zero_result = cur.fetchall()

    # Searches per day (last 14 days)
    cur.execute("""
        SELECT DATE(created_at) AS day, COUNT(*) AS cnt
        FROM search_queries
        WHERE created_at >= NOW() - INTERVAL '14 days'
        GROUP BY DATE(created_at)
        ORDER BY day
    """)
    daily = cur.fetchall()

    cur.close()
    conn.close()

    if args.json_output:
        result = {
            "total_searches": total,
            "top_terms": [
                {"term": t[0], "count": t[1], "avg_results": int(t[2] or 0), "avg_ms": int(t[3] or 0)}
                for t in top_terms
            ],
            "mode_breakdown": [
                {"mode": m[0], "count": m[1], "avg_ms": int(m[2] or 0)}
                for m in mode_breakdown
            ],
            "zero_result_queries": [
                {"term": z[0], "count": z[1]}
                for z in zero_result
            ],
            "daily_volume": [
                {"date": str(d[0]), "count": d[1]}
                for d in daily
            ],
        }
        print(json.dumps(result, indent=2))
        return

    # Human-readable output
    period = f"last {args.days} days" if args.days else "all time"
    print("=" * 64)
    print(f"  Open Testimony Search Analytics ({period})")
    print("=" * 64)
    print(f"  Total searches: {total}")
    print()

    print("-" * 64)
    print(f"  Top {args.top} Search Terms")
    print("-" * 64)
    print(f"  {'#':<4} {'Count':<8} {'Avg Results':<13} {'Avg ms':<9} {'Term'}")
    print(f"  {'-'*3} {'-'*7} {'-'*12} {'-'*8} {'-'*30}")
    for i, (term, cnt, avg_res, avg_ms) in enumerate(top_terms, 1):
        print(f"  {i:<4} {cnt:<8} {int(avg_res or 0):<13} {int(avg_ms or 0):<9} {term}")

    print()
    print("-" * 64)
    print("  Search Mode Breakdown")
    print("-" * 64)
    print(f"  {'Mode':<20} {'Count':<10} {'Avg ms':<10} {'%'}")
    print(f"  {'-'*19} {'-'*9} {'-'*9} {'-'*6}")
    for mode, cnt, avg_ms in mode_breakdown:
        pct = cnt / total * 100
        print(f"  {mode:<20} {cnt:<10} {int(avg_ms or 0):<10} {pct:.1f}%")

    if zero_result:
        print()
        print("-" * 64)
        print("  Zero-Result Queries (potential index gaps)")
        print("-" * 64)
        for term, cnt in zero_result:
            print(f"  {cnt:>4}x  {term}")

    if daily:
        print()
        print("-" * 64)
        print("  Daily Search Volume (last 14 days)")
        print("-" * 64)
        max_cnt = max(d[1] for d in daily)
        bar_width = 30
        for day, cnt in daily:
            bar = "#" * int(cnt / max_cnt * bar_width) if max_cnt else ""
            print(f"  {day}  {cnt:>5}  {bar}")

    print()
    print("=" * 64)


if __name__ == "__main__":
    main()
