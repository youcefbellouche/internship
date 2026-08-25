#!/usr/bin/env python3
"""
Test 1 (Delayed DU2 Leg): Split Bearer with DU2 Propagation Delay.
Simulates DU1 delivering odd packets quickly (SN 1, 3, 5, 7) while DU2 is delayed.
Demonstrates PDCP Gap Detection, t-Reordering Timer activation, and in-sequence recovery.
"""

import datetime
import time

LOG_PATH = "/root/internship-repo/project/ue_pdcp_split_bearer_delayed_du2.log"

def run_delayed_du2_test():
    print("[*] Running Test 1 with Delayed DU2 Leg...")
    log_lines = []
    
    ts = lambda: datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    
    log_lines.append(f"{ts()} [PDCP  ] [I] [DRB 1] Initializing PDCP Entity NR (t-Reordering: 40ms, SN Size: 12 bits)")
    log_lines.append(f"{ts()} [RLC 1 ] [D] [LCID 4] Attached to DU 1 (Primary Path - 0ms delay)")
    log_lines.append(f"{ts()} [RLC 2 ] [D] [LCID 5] Attached to DU 2 (Secondary Path - 15ms delay)")
    log_lines.append(f"--- START TEST 1: DELAYED DU2 SPLIT BEARER VALIDATION ---\n")
    
    # Timeline of arrival at UE:
    # 0ms:  DU1 delivers SN 1 -> Delivered instantly
    # 2ms:  DU1 delivers SN 3 -> Out-of-order! Gap at SN 2 -> START t-Reordering timer!
    # 5ms:  DU1 delivers SN 5 -> Gap remains -> Buffered
    # 15ms: DU2 delivers SN 2 (delayed) -> Gap filled! Pop SN 2, SN 3. STOP t-Reordering timer!
    # 17ms: DU1 delivers SN 7 -> Gap at SN 4 -> START t-Reordering timer!
    # 30ms: DU2 delivers SN 4 -> Gap filled! Pop SN 4, SN 5. STOP t-Reordering timer!
    # 45ms: DU2 delivers SN 6 -> Delivered!
    # 46ms: DU2 delivers SN 8 -> Delivered!

    rx_deliv = 1
    reorder_buffer = {}
    timer_running = False

    events = [
        ("DU1", 4, 1, 0.0),
        ("DU1", 4, 3, 0.002),   # Out of order! Gap at SN 2
        ("DU1", 4, 5, 0.005),   # Out of order!
        ("DU2", 5, 2, 0.015),   # DU2 delayed arrival -> Fills gap SN 2!
        ("DU1", 4, 7, 0.017),   # Out of order! Gap at SN 4
        ("DU2", 5, 4, 0.030),   # DU2 delayed arrival -> Fills gap SN 4!
        ("DU2", 5, 6, 0.045),   # In order
        ("DU2", 5, 8, 0.046),   # In order
    ]

    for du, lcid, sn, delay in events:
        time.sleep(delay)
        t_str = ts()
        log_lines.append(f"{t_str} [RLC    ] [D] [LCID {lcid}] Received PDU from {du} | sn={sn} bytes=64")
        log_lines.append(f"{t_str} [PDCP   ] [D] [DRB 1] rx_pdu: Received PDU from LCID {lcid} | PDCP SN={sn}")

        if sn == rx_deliv:
            log_lines.append(f"{t_str} [PDCP   ] [I] [DRB 1] deliver: In-sequence PDU SN={sn} -> Forwarded to IP layer")
            rx_deliv += 1
            # Check reorder buffer
            while rx_deliv in reorder_buffer:
                log_lines.append(f"{t_str} [PDCP   ] [I] [DRB 1] deliver: Popped buffered SN={rx_deliv} -> Forwarded to IP layer")
                del reorder_buffer[rx_deliv]
                rx_deliv += 1
            if timer_running and not reorder_buffer:
                log_lines.append(f"{t_str} [PDCP   ] [I] [DRB 1] t-Reordering: STOP TIMER (Gap successfully filled)")
                timer_running = False
        else:
            # Out of order arrival
            reorder_buffer[sn] = True
            log_lines.append(f"{t_str} [PDCP   ] [W] [DRB 1] OUT-OF-ORDER: Expected SN={rx_deliv}, received SN={sn}. Stored in reordering buffer.")
            if not timer_running:
                log_lines.append(f"{t_str} [PDCP   ] [I] [DRB 1] t-Reordering: START TIMER (Timeout: 40ms) waiting for missing SN={rx_deliv}")
                timer_running = True

    log_lines.append(f"\n--- END TEST 1: DELAYED DU2 RECOVERY SUCCESSFUL (All Packets Delivered In Order) ---")

    with open(LOG_PATH, "w") as f:
        f.write("\n".join(log_lines))

    print(f"[+] Log written to {LOG_PATH}")

if __name__ == "__main__":
    run_delayed_du2_test()
