#!/usr/bin/env python3
"""
Verification script for PDCP Ratio-Based Traffic Splitting.
Simulates packet routing to DU1 and DU2 for different configured ratios.
"""

import sys

def simulate_ratio_split(ratio_str, total_packets=18):
    try:
        mn, sn = map(int, ratio_str.split(':'))
    except ValueError:
        print("Invalid ratio format. Use MN:SN (e.g. 2:7)")
        return
        
    total_ratio = mn + sn
    print(f"\n--- Simulating PDCP Split Ratio: {ratio_str} (Total Cycle: {total_ratio}) ---")
    
    du1_count = 0
    du2_count = 0
    
    du1_packets = []
    du2_packets = []
    
    for count in range(total_packets):
        # Emulating the C++ logic:
        # uint32_t count = packet_counter++ % total_ratio;
        # bool route_to_mn = (count < ratio_mn);
        step = count % total_ratio
        route_to_mn = (step < mn)
        
        packet_id = count + 1
        if route_to_mn:
            du1_count += 1
            du1_packets.append(packet_id)
        else:
            du2_count += 1
            du2_packets.append(packet_id)
            
    print(f"Total packets transmitted: {total_packets}")
    print(f"  -> DU1 (MN) Packets ({du1_count}): {du1_packets}")
    print(f"  -> DU2 (SN) Packets ({du2_count}): {du2_packets}")
    print(f"Actual ratio achieved: {du1_count}:{du2_count} ({du1_count/total_packets*100:.1f}% / {du2_count/total_packets*100:.1f}%)")

if __name__ == "__main__":
    ratios = ["2:7", "3:4", "1:1"]
    for r in ratios:
        simulate_ratio_split(r)
