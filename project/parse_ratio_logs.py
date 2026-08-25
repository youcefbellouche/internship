#!/usr/bin/env python3
"""
Parses srsUE logs to check the ratio of packets received by LCID 4 vs LCID 5.
"""

import sys
import re

def parse_logs(log_path):
    print(f"[*] Parsing logs from: {log_path}")
    
    lcid_4_count = 0
    lcid_5_count = 0
    
    # Example log lines:
    # RX DRB1 PDU (64 B) on LCID 4
    # Received PDU from LCID 4
    with open(log_path, 'r', errors='ignore') as f:
        for line in f:
            if "Received PDU from LCID 4" in line or "lcid=4" in line or "LCID 4" in line:
                lcid_4_count += 1
            elif "Received PDU from LCID 5" in line or "lcid=5" in line or "LCID 5" in line:
                lcid_5_count += 1
                
    total = lcid_4_count + lcid_5_count
    print(f"[*] Analysis:")
    print(f"  Total user plane packets routed: {total}")
    print(f"  DU1 (LCID 4) packets: {lcid_4_count}")
    print(f"  DU2 (LCID 5) packets: {lcid_5_count}")
    if total > 0:
        print(f"  Distribution: {lcid_4_count/total*100:.1f}% / {lcid_5_count/total*100:.1f}%")
    else:
        print("  No packets found in log.")

if __name__ == "__main__":
    path = "/tmp/run_ue_ratio.log"
    if len(sys.argv) > 1:
        path = sys.argv[1]
    parse_logs(path)
