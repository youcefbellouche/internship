#!/usr/bin/env python3
"""
Automated Multi-Scenario Simulation Runner & Diagnostic Engine
for 6 Ground & LEO 5G NR Multi-Connectivity Architectures.

Executes scenarios:
  0: CU_g D1_g D2_g (Ground CU, Ground DU1, Ground DU2) - Baseline Pure Terrestrial
  1: CU_g D1_g D2_L (Ground CU, Ground DU1, LEO Satellite DU2)
  2: CU_g D1_L D2_L (Ground CU, LEO Satellite DU1, LEO Satellite DU2)
  3: CU_L D1_g D2_g (LEO Onboard CU, Ground DU1, Ground DU2)
  4: CU_L D1_L D2_L (LEO Onboard CU, LEO Satellite DU1, LEO Satellite DU2)
  5: CU_L D1_g D2_L (LEO Onboard CU, Ground DU1, LEO Satellite DU2)
"""

import os
import sys
import time
import argparse
import subprocess
import re

BASE_DIR = "/root/internship-repo/project"
SCENARIOS_DIR = os.path.join(BASE_DIR, "scenarios")
OCUDU_BIN = os.path.join(BASE_DIR, "ocudu/build/apps")
SRSRAN_BIN = os.path.join(BASE_DIR, "srsRAN_4G/build/srsue/src/srsue")
DBCTL_BIN = "/root/internship-repo/open5gs-dbctl"

SCENARIO_MAP = {
    "0": "scenario0_cug_d1g_d2g",
    "scenario0": "scenario0_cug_d1g_d2g",
    "cug_d1g_d2g": "scenario0_cug_d1g_d2g",
    "scenario0_cug_d1g_d2g": "scenario0_cug_d1g_d2g",
    "baseline": "scenario0_cug_d1g_d2g",
    "1": "scenario1_cug_d1g_d2l",
    "scenario1": "scenario1_cug_d1g_d2l",
    "scenario1_cug_d1g_d2l": "scenario1_cug_d1g_d2l",
    "2": "scenario2_cug_d1l_d2l",
    "scenario2": "scenario2_cug_d1l_d2l",
    "scenario2_cug_d1l_d2l": "scenario2_cug_d1l_d2l",
    "3": "scenario3_cul_d1g_d2g",
    "scenario3": "scenario3_cul_d1g_d2g",
    "scenario3_cul_d1g_d2g": "scenario3_cul_d1g_d2g",
    "4": "scenario4_cul_d1l_d2l",
    "scenario4": "scenario4_cul_d1l_d2l",
    "scenario4_cul_d1l_d2l": "scenario4_cul_d1l_d2l",
    "5": "scenario5_cul_d1g_d2l",
    "scenario5": "scenario5_cul_d1g_d2l",
    "scenario5_cul_d1g_d2l": "scenario5_cul_d1g_d2l",
}


def parse_args():
    parser = argparse.ArgumentParser(description="5G NR Ground/LEO Multi-Scenario Runner")
    parser.add_argument(
        "--scenario",
        type=str,
        default="0",
        help="Scenario identifier: 0..5, scenario name, or 'all'",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=35,
        help="Max seconds to wait for PDU session establishment (default: 35s)",
    )
    parser.add_argument(
        "--ping-count",
        type=int,
        default=10,
        help="Number of ping ICMP packets to send (default: 10)",
    )
    parser.add_argument(
        "--keep-alive",
        action="store_true",
        help="Keep processes running after test instead of cleaning up",
    )
    return parser.parse_args()


def cleanup():
    """Kill all lingering simulation processes and restore terminal state."""
    subprocess.run("sudo pkill -9 -f ocucp || true", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run("sudo pkill -9 -f ocuup || true", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run("sudo pkill -9 -f odu || true", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run("sudo pkill -9 -f srsue || true", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run("stty sane 2>/dev/null || true", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)


def setup_environment():
    """Ensure Open5GS DB subscribers and network namespaces exist."""
    subprocess.run(
        f"sudo {DBCTL_BIN} add 999700123456780 00112233445566778899aabbccddeeff 63BFA50EE6523365FF14C1F45F88737D || true",
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    subprocess.run(
        f"sudo {DBCTL_BIN} add 999700123456781 00112233445566778899aabbccddeeff 63BFA50EE6523365FF14C1F45F88737D || true",
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Namespaces
    subprocess.run("sudo ip netns add ue_mn || true", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run("sudo ip netns exec ue_mn ip link set lo up || true", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run("sudo ip netns add ue_sn || true", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run("sudo ip netns exec ue_sn ip link set lo up || true", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def diagnose_failure(scenario_name: str) -> str:
    """Inspect node logs to identify root cause of failure."""
    reasons = []

    ue_log = "/tmp/run_ue.log"
    du1_log = f"/tmp/{scenario_name}_du1.log"
    du2_log = f"/tmp/{scenario_name}_du2.log"
    cucp_log = f"/tmp/{scenario_name}_cu_cp.log"

    # 1. Check UE log
    if os.path.exists(ue_log):
        with open(ue_log, "r", errors="ignore") as f:
            u_lines = f.read()
            if "RA procedure failed" in u_lines or "Random Access Response (RAR) timeout" in u_lines:
                reasons.append("UE Random Access (PRACH) timed out (Timing Advance / PRACH window mismatch)")
            if "RRC Setup Request timed out" in u_lines:
                reasons.append("RRC Setup timed out on Master Cell")
            if "Failed to synchronize to cell" in u_lines:
                reasons.append("UE Physical Layer failed to detect primary synchronization signals (PSS/SSS)")

    # 2. Check DU1 & DU2 logs
    for du_name, du_file in [("DU1", du1_log), ("DU2", du2_log)]:
        if os.path.exists(du_file):
            with open(du_file, "r", errors="ignore") as f:
                d_lines = f.read()
                if "F1 Setup Request failed" in d_lines or "Connection refused" in d_lines:
                    reasons.append(f"{du_name} failed F1-C connection to CU-CP")
                if "Disabling HARQ" in d_lines:
                    pass

    # 3. Check CU-CP log
    if os.path.exists(cucp_log):
        with open(cucp_log, "r", errors="ignore") as f:
            c_lines = f.read()
            if "AMF connection failed" in c_lines or "SCTP connect error" in c_lines:
                reasons.append("CU-CP failed SCTP connection to Open5GS AMF (127.0.0.5:38412)")
            if "E1 Setup timeout" in c_lines:
                reasons.append("E1AP connection between CU-CP and CU-UP timed out")

    if not reasons:
        return "PDU Session establishment timed out (tun_srsue did not receive an IPv4 address within deadline)"
    return " | ".join(reasons)


def run_single_scenario(scenario_key: str, timeout: int, ping_count: int, keep_alive: bool) -> dict:
    if scenario_key not in SCENARIO_MAP:
        raise ValueError(f"Unknown scenario: {scenario_key}")

    scenario_name = SCENARIO_MAP[scenario_key]
    scen_dir = os.path.join(SCENARIOS_DIR, scenario_name)

    cu_cp_cfg = os.path.join(scen_dir, "cu_cp.yml")
    cu_up_cfg = os.path.join(scen_dir, "cu_up.yml")
    du1_cfg = os.path.join(scen_dir, "du1.yml")
    du2_cfg = os.path.join(scen_dir, "du2.yml")

    print("\n" + "=" * 75)
    print(f"[*] RUNNING SCENARIO TEST: {scenario_name}")
    print(f"[*] Configuration Path:    {scen_dir}")
    print("=" * 75 + "\n")

    cleanup()
    setup_environment()

    result = {
        "scenario": scenario_name,
        "pdu_connected": False,
        "ip_address": None,
        "ping_success": False,
        "ping_stats": None,
        "duration_sec": 0,
        "diagnosis": "None",
    }

    start_time = time.time()

    try:
        # Phase 1: Launch Infrastructure Nodes
        print("[Phase 1/4] Starting RAN Infrastructure Nodes...")
        print("  -> [1/4] Starting CU-CP...")
        cucp_cmd = f"tail -f /dev/null | sudo {OCUDU_BIN}/cu_cp/ocucp -c {cu_cp_cfg} > /tmp/{scenario_name}_cu_cp.log 2>&1"
        subprocess.Popen(cucp_cmd, shell=True)
        time.sleep(2)

        print("  -> [2/4] Starting CU-UP...")
        cuup_cmd = f"tail -f /dev/null | sudo {OCUDU_BIN}/cu_up/ocuup -c {cu_up_cfg} > /tmp/{scenario_name}_cu_up.log 2>&1"
        subprocess.Popen(cuup_cmd, shell=True)
        time.sleep(1)

        print("  -> [3/4] Starting DU1...")
        du1_cmd = f"tail -f /dev/null | sudo {OCUDU_BIN}/du/odu -c {du1_cfg} --gnb_du_id 1 > /tmp/{scenario_name}_du1.log 2>&1"
        subprocess.Popen(du1_cmd, shell=True)
        time.sleep(3)

        print("  -> [4/4] Starting DU2...")
        du2_cmd = f"tail -f /dev/null | sudo {OCUDU_BIN}/du/odu -c {du2_cfg} --gnb_du_id 2 > /tmp/{scenario_name}_du2.log 2>&1"
        subprocess.Popen(du2_cmd, shell=True)
        time.sleep(8)

        # Phase 2: Launch Monolithic UE
        print("\n[Phase 2/4] Launching Monolithic Dual-Path srsUE...")
        ue_cmd = (
            f"tail -f /dev/null | sudo SRSUE_SN_CONFIG={BASE_DIR}/ue_sn.conf "
            f"{SRSRAN_BIN} {BASE_DIR}/ue_mn.conf > /tmp/run_ue.log 2>&1"
        )
        subprocess.Popen(ue_cmd, shell=True, stdin=subprocess.DEVNULL)

        print(f"[*] Waiting for PDU session establishment (timeout {timeout}s)...")
        connected = False
        assigned_ip = None

        for sec in range(1, timeout + 1):
            chk = subprocess.run(
                "sudo ip netns exec ue_mn ip addr show dev tun_srsue 2>/dev/null",
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )
            m = re.search(r"inet\s+([0-9.]+)", chk.stdout)
            if m:
                connected = True
                assigned_ip = m.group(1)
                print(f"  [+] SUCCESS: PDU Session established at {sec}s! IP: {assigned_ip}\n")
                break
            time.sleep(1)

        result["pdu_connected"] = connected
        result["ip_address"] = assigned_ip

        if connected:
            # Phase 3: Traffic Verification
            print("[Phase 3/4] Executing ICMP Ping Verification...")
            print(f"[*] Sending {ping_count} packets to UPF gateway (10.45.0.1)...\n")
            ping_res = subprocess.run(
                f"sudo ip netns exec ue_mn ping 10.45.0.1 -c {ping_count}",
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )
            ping_out = ping_res.stdout
            print(ping_out.strip() + "\n")

            # Parse ping statistics
            loss_match = re.search(r"(\d+)% packet loss", ping_out)
            rtt_match = re.search(r"rtt min/avg/max/mdev = ([0-9.]+)/([0-9.]+)/([0-9.]+)/([0-9.]+)\s+ms", ping_out)

            loss_pct = int(loss_match.group(1)) if loss_match else 100
            if loss_pct < 100:
                result["ping_success"] = True
                if rtt_match:
                    result["ping_stats"] = {
                        "loss_pct": loss_pct,
                        "min_ms": float(rtt_match.group(1)),
                        "avg_ms": float(rtt_match.group(2)),
                        "max_ms": float(rtt_match.group(3)),
                        "mdev_ms": float(rtt_match.group(4)),
                    }
            else:
                result["diagnosis"] = "PDU Session established but ICMP ping experienced 100% packet loss to 10.45.0.1"
        else:
            result["diagnosis"] = diagnose_failure(scenario_name)
            print(f"  [-] FAILED: {result['diagnosis']}\n")

    finally:
        result["duration_sec"] = round(time.time() - start_time, 2)
        if not keep_alive:
            print("[Phase 4/4] Cleaning up scenario processes...")
            cleanup()
            print("[+] Teardown completed successfully.\n")

    return result


def main():
    subprocess.run("stty sane 2>/dev/null || true", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    args = parse_args()

    scenarios_to_run = []
    if args.scenario.lower() == "all":
        scenarios_to_run = ["0", "1", "2", "3", "4", "5"]
    else:
        scenarios_to_run = [args.scenario]

    results = []
    for sc in scenarios_to_run:
        res = run_single_scenario(
            scenario_key=sc,
            timeout=args.timeout,
            ping_count=args.ping_count,
            keep_alive=args.keep_alive,
        )
        results.append(res)
        time.sleep(2)

    # Print Summary Report
    print("\n" + "=" * 82)
    print("                      SIMULATION TEST SUMMARY REPORT")
    print("=" * 82)
    fmt = "  {:<25} | {:<12} | {:<12} | {:<14} | {:<10}"
    print(fmt.format("Scenario", "PDU Session", "Ping Test", "Avg RTT", "Notes"))
    print("  " + "-" * 78)

    for r in results:
        pdu_str = "CONNECTED" if r["pdu_connected"] else "FAILED"
        ping_str = "PASSED" if r["ping_success"] else ("FAILED" if r["pdu_connected"] else "N/A")
        rtt_str = f"{r['ping_stats']['avg_ms']:.2f} ms" if r["ping_stats"] else "N/A"
        notes = "OK" if r["ping_success"] else r["diagnosis"][:18] + "..."
        print(fmt.format(r["scenario"], pdu_str, ping_str, rtt_str, notes))
    print("=" * 82 + "\n")


if __name__ == "__main__":
    main()
