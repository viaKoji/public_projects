#!/usr/bin/env python3
"""Check for old jobs with parsing issues"""

import sqlite3
from datetime import datetime

conn = sqlite3.connect('data/jobs.db')
cursor = conn.cursor()

print("=== CHECKING OLD JOBS WITH PARSING ISSUES ===\n")

# Check all jobs with location as company
cursor.execute("""
    SELECT id, title, company, location, found_date, status
    FROM jobs 
    WHERE LOWER(company) IN ('united states', 'usa', 'us', 'canada', 'uk', 'united kingdom', 
                             'remote', 'hybrid', 'onsite', 'on-site')
    ORDER BY id DESC
""")

bad_jobs = cursor.fetchall()
print(f"Total jobs with location as company: {len(bad_jobs)}\n")

if bad_jobs:
    # Group by date
    by_date = {}
    for job in bad_jobs:
        date = job[4].split('T')[0] if job[4] else 'Unknown'
        if date not in by_date:
            by_date[date] = []
        by_date[date].append(job)
    
    print("Breakdown by date:")
    for date in sorted(by_date.keys(), reverse=True)[:5]:  # Show last 5 days
        print(f"\n{date}: {len(by_date[date])} jobs")
        for job in by_date[date][:3]:  # Show first 3 examples
            print(f"  ID {job[0]}: {job[1][:40]}...")
            print(f"    Company: '{job[2]}', Location: '{job[3]}', Status: {job[5]}")

# Check what statuses these jobs have
print("\n\nStatus breakdown of problematic jobs:")
cursor.execute("""
    SELECT status, COUNT(*) as count
    FROM jobs 
    WHERE LOWER(company) IN ('united states', 'usa', 'us', 'canada', 'uk', 'united kingdom', 
                             'remote', 'hybrid', 'onsite', 'on-site')
    GROUP BY status
    ORDER BY count DESC
""")

status_counts = cursor.fetchall()
for status, count in status_counts:
    print(f"  {status}: {count} jobs")

# Offer to fix or hide them
print("\n\nOptions to fix this:")
print("1. Update these old jobs to set company = 'Unknown Company'")
print("2. Mark them as 'archived' status so they don't show in main view")
print("3. Delete them entirely")
print("4. Manually fix them one by one")

conn.close()