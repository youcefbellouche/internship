#!/usr/bin/env python3
"""
Multi-Connectivity (MR-DC) 5G SA Benchmark Orchestrator
Architecture:
  - Ground CU: Ground CU-CP & CU-UP with pdcpReorderingTimerMs = 100ms, rlcAmReassemblyDueToMs = 15ms
  - DU1 (MN): Ground Terrestrial Network (TN), Band 3, 20 MHz, SCS 15 kHz
  - DU2 (SN): Non-Terrestrial Network (NTN), Band 2 (ARFCN 386000), 20 MHz, SCS 15 kHz, 7ms delay, HARQ retx=0
  - Monolithic Dual-Carrier srsUE with PDCP split bearer (Ratio 1:1)
  - Integrated Benchmarking: ICMP Ping, HTTP File Transfer, HTTP Streaming, iperf3 UDP CBR
"""

import os
import sys
import time
import argparse
import subprocess
import re
import urllib.request

BASE_DIR = "/root/internship-repo/project"
SCENARIO_DIR = f"{BASE_DIR}/scenarios/mrdc_tn_ntn_20mhz"
OCUDU_BIN = f"{BASE_DIR}/ocudu/build/apps"
SRSRAN_BIN = f"{BASE_DIR}/srsRAN_4G/build/srsue/src/srsue"
DBCTL_BIN = "/root/internship-repo/open5gs-dbctl"


def cleanup():
    """Kill old processes cleanly."""
    subprocess.run("sudo pkill -9 -f ocucp || true", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run("sudo pkill -9 -f ocuup || true", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run("sudo pkill -9 -f odu || true", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run("sudo pkill -9 -f srsue || true", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run("stty sane 2>/dev/null || true", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)


def setup_namespaces_and_subscribers():
    """Ensure network namespaces and Open5GS subscriber DB exist."""
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
    subprocess.run("sudo ip netns del ue_mn >/dev/null 2>&1 || true", shell=True)
    subprocess.run("sudo ip netns del ue_sn >/dev/null 2>&1 || true", shell=True)
    subprocess.run("sudo ip netns add ue_mn", shell=True)
    subprocess.run("sudo ip netns exec ue_mn ip link set lo up", shell=True)
    subprocess.run("sudo ip netns add ue_sn", shell=True)
    subprocess.run("sudo ip netns exec ue_sn ip link set lo up", shell=True)


def set_pdcp_ratio(ratio_str="1:1"):
    with open("/tmp/pdcp_split_ratio", "w") as f:
        f.write(ratio_str + "\n")
    print(f"[*] Configured PDCP Split Ratio: {ratio_str}")


def run_mrdc_benchmark(ratio="1:1", timeout=35, keep_alive=False, samples=10):
    print("=" * 75)
    print("  MULTI-CONNECTIVITY BENCHMARK: TN (Band 3) + NTN (Band 2 @ 386000)")
    print("  CU Ground | DU1 Ground (TN) | DU2 Satellite (NTN 7ms Delay)")
    print(f"  PDCP Split Mode: Ratio {ratio} | Reordering: 100ms | Reassembly: 15ms")
    print("=" * 75)

    print("\n[*] Terminating previous simulation processes...")
    cleanup()

    print("[*] Setting up network namespace and subscriber records...")
    setup_namespaces_and_subscribers()
    set_pdcp_ratio(ratio)

    cu_cp_cfg = f"{SCENARIO_DIR}/cu_cp.yml"
    cu_up_cfg = f"{SCENARIO_DIR}/cu_up.yml"
    du1_cfg = f"{SCENARIO_DIR}/du1.yml"
    du2_cfg = f"{SCENARIO_DIR}/du2.yml"
    ue_mn_cfg = f"{SCENARIO_DIR}/ue_mn.conf"
    ue_sn_cfg = f"{SCENARIO_DIR}/ue_sn.conf"

    # Step 1: Start CU-CP
    print("\n[Step 1/5] Starting Ground CU-CP...")
    subprocess.Popen(f"tail -f /dev/null | sudo {OCUDU_BIN}/cu_cp/ocucp -c {cu_cp_cfg} > /tmp/mrdc_cu_cp.log 2>&1", shell=True)
    time.sleep(2)

    # Step 2: Start CU-UP
    print("[Step 2/5] Starting Ground CU-UP...")
    subprocess.Popen(f"tail -f /dev/null | sudo {OCUDU_BIN}/cu_up/ocuup -c {cu_up_cfg} > /tmp/mrdc_cu_up.log 2>&1", shell=True)
    time.sleep(1)

    # Step 3: Start DU1 (TN Band 3)
    print("[Step 3/5] Starting DU1 (Terrestrial TN, Band 3, 20 MHz, 106 PRB)...")
    subprocess.Popen(f"tail -f /dev/null | sudo {OCUDU_BIN}/du/odu -c {du1_cfg} --gnb_du_id 1 > /tmp/mrdc_du1_stdout.log 2>&1", shell=True)
    time.sleep(4)

    # Step 4: Start DU2 (NTN Band 2)
    print("[Step 4/5] Starting DU2 (Satellite NTN, Band 2, ARFCN 386000, 20 MHz, 7ms delay)...")
    subprocess.Popen(f"tail -f /dev/null | sudo {OCUDU_BIN}/du/odu -c {du2_cfg} --gnb_du_id 2 > /tmp/mrdc_du2_stdout.log 2>&1", shell=True)
    time.sleep(6)

    # Step 5: Start Monolithic Dual-Carrier srsUE
    print("\n[Step 5/5] Launching Monolithic Dual-Path srsUE (PDCP Split 1:1)...")
    ue_cmd = (
        f"tail -f /dev/null | sudo PDCP_SPLIT_RATIO={ratio} SRSUE_SN_CONFIG={ue_sn_cfg} "
        f"{SRSRAN_BIN} {ue_mn_cfg} > /tmp/mrdc_ue.log 2>&1"
    )
    subprocess.Popen(ue_cmd, shell=True)

    print(f"[*] Waiting for PDU session establishment on tun_srsue (timeout: {timeout}s)...")
    ip_addr = None
    for sec in range(1, timeout + 1):
        res = subprocess.run(
            "sudo ip netns exec ue_mn ip addr show dev tun_srsue 2>/dev/null",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        m = re.search(r"inet\s+([0-9.]+)", res.stdout)
        if m:
            ip_addr = m.group(1)
            print(f"  [+] SUCCESS: PDU Session Established at {sec}s! Assigned IP: {ip_addr}")
            break
        time.sleep(1)

    if not ip_addr:
        print("[-] FAILED: PDU Session timed out.")
        print("--- DU1 Log Tail ---")
        subprocess.run("tail -n 25 /tmp/mrdc_tn_ntn_20mhz_du1.log || true", shell=True)
        print("--- DU2 Log Tail ---")
        subprocess.run("tail -n 25 /tmp/mrdc_tn_ntn_20mhz_du2.log || true", shell=True)
        print("--- UE Log Tail ---")
        subprocess.run("tail -n 25 /tmp/mrdc_ue.log || true", shell=True)
        if not keep_alive:
            cleanup()
        return False

    # Ensure Web Server is reachable
    try:
        urllib.request.urlopen("http://127.0.0.1:8080/api/status", timeout=1)
        print("[*] Web server is running on port 8080.")
    except Exception:
        print("[*] Starting Web Server on 0.0.0.0:8080...")
        subprocess.Popen(f"python3 {BASE_DIR}/web_server/server.py 8080 > /tmp/web_server.log 2>&1", shell=True)
        time.sleep(2)

    # Ensure iperf3 server daemon is active
    subprocess.run("sudo pkill -9 iperf3 || true", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.Popen("iperf3 -s -D", shell=True)
    time.sleep(0.5)

    mode_label = f"MR-DC Packet Duplication (dup)" if ratio in ["dup", "duplicate"] else f"MR-DC Traffic Splitting (Ratio {ratio})"

    print("\n" + "=" * 75)
    print(f"  RUNNING BENCHMARKS: {mode_label}")
    print("=" * 75)

    # Benchmark A: Latency & RTT (ICMP Ping)
    print("\n--- [A] Latency & RTT Benchmark (10 ICMP Pings to UPF 10.45.0.1) ---")
    ping_res = subprocess.run(
        "sudo ip netns exec ue_mn ping 10.45.0.1 -c 10",
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    print(ping_res.stdout.strip())

    # Benchmark B: HTTP File Transfer
    print(f"\n--- [B] Executing HTTP File Transfer Benchmark (Reporting to Web Server 10.45.0.1:8080) ---")
    bench_file_cmd = (
        f"sudo ip netns exec ue_mn python3 {BASE_DIR}/scripts/ue_benchmark_client.py "
        f"--server 10.45.0.1 --port 8080 --test file --samples {samples} --size-mb 5.0 "
        f"--mode-label '{mode_label}'"
    )
    subprocess.run(bench_file_cmd, shell=True)

    # Benchmark C: HTTP Streaming Transfer
    print(f"\n--- [C] Executing HTTP Streaming Transfer Benchmark (Reporting to Web Server 10.45.0.1:8080) ---")
    bench_stream_cmd = (
        f"sudo ip netns exec ue_mn python3 {BASE_DIR}/scripts/ue_benchmark_client.py "
        f"--server 10.45.0.1 --port 8080 --test stream --samples 1 --duration 10 "
        f"--mode-label '{mode_label}'"
    )
    subprocess.run(bench_stream_cmd, shell=True)

    # Benchmark D: Constant Bitrate (CBR) UDP Benchmark via iperf3 (10 Samples)
    print(f"\n--- [D] Constant Bitrate (CBR) UDP Benchmark via iperf3 (10 Samples) ---")
    bench_udp_cmd = (
        f"sudo ip netns exec ue_mn python3 {BASE_DIR}/scripts/ue_benchmark_client.py "
        f"--server 10.45.0.1 --port 8080 --test udp --samples 10 --duration-udp 5 "
        f"--mode-label '{mode_label}'"
    )
    subprocess.run(bench_udp_cmd, shell=True)

    print("\n========================================================================")
    print(f"       BENCHMARK COMPLETE: {mode_label}")
    print("========================================================================")

    if not keep_alive:
        print("[*] Cleaning up simulation processes...")
        cleanup()
    else:
        print("[*] Processes kept running as requested (--keep-alive).")

    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MR-DC TN (Band 3) + NTN (Band 2) Benchmark")
    parser.add_argument("--ratio", type=str, default="1:1", help="PDCP split ratio (default: 1:1)")
    parser.add_argument("--timeout", type=int, default=35, help="PDU session timeout in seconds (default: 35)")
    parser.add_argument("--samples", type=int, default=10, help="Number of benchmark samples (default: 10)")
    parser.add_argument("--keep-alive", action="store_true", help="Keep processes running after benchmark")
    args = parser.parse_args()

    success = run_mrdc_benchmark(ratio=args.ratio, timeout=args.timeout, keep_alive=args.keep_alive, samples=args.samples)
    sys.exit(0 if success else 1)
