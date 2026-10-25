#!/usr/bin/env python3
"""
Single-Connectivity 20MHz TN Benchmark Runner
Evaluates 20MHz (106 PRB, Numerology 0, Band 3 FDD) Ground Leg performance.
Runs:
  1. Infrastructure: CU-CP, CU-UP, DU1 (20MHz, SCS 15kHz, 106 PRBs)
  2. Single UE: srsUE configured for 20MHz, 106 PRBs, srate 23.04MHz
  3. PDU Session verification
  4. Ping latency and jitter
  5. File transfer throughput test (DL & UL) against Web Server (10.45.0.1:8080)
"""

import os
import sys
import time
import subprocess
import re
import json
import argparse
import urllib.request
import urllib.parse

BASE_DIR = "/root/internship-repo/project"
OCUDU_BIN = os.path.join(BASE_DIR, "ocudu/build/apps")
SRSRAN_BIN = os.path.join(BASE_DIR, "srsRAN_4G/build/srsue/src/srsue")
DBCTL_BIN = "/root/internship-repo/open5gs-dbctl"



def cleanup():
    print("[*] Terminating previous simulation processes...")
    subprocess.run("sudo pkill -9 -f ocucp || true", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run("sudo pkill -9 -f ocuup || true", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run("sudo pkill -9 -f odu || true", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run("sudo pkill -9 -f srsue || true", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)


def setup_env():
    print("[*] Setting up network namespace and subscriber...")
    subprocess.run(
        f"sudo {DBCTL_BIN} add 999700123456780 00112233445566778899aabbccddeeff 63BFA50EE6523365FF14C1F45F88737D || true",
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    subprocess.run("sudo ip netns del ue_mn || true", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run("sudo ip netns add ue_mn", shell=True, check=True)
    subprocess.run("sudo ip netns exec ue_mn ip link set lo up", shell=True, check=True)


def run_benchmark(band: int = 3, bw: int = 20, ntn: bool = False, samples: int = 10):
    if ntn:
        scen_dir = os.path.join(BASE_DIR, "scenarios/single_ntn_20mhz")
        ue_conf = os.path.join(BASE_DIR, "ue_tn_20mhz.conf")
        mode_label = f"Single-NTN Band {band} (20MHz, 7ms Delay)"
        print("\n" + "=" * 70)
        print(f"  BENCHMARK: Single-Connectivity NTN Band {band} (20 MHz, 7ms Delay, HARQ retx=0)")
        print("=" * 70)
    elif bw == 40:
        scen_dir = os.path.join(BASE_DIR, "scenarios/single_tn_40mhz")
        ue_conf = os.path.join(BASE_DIR, "ue_tn_40mhz.conf")
        mode_label = f"Single-TN Band {band} (40MHz)"
        print("\n" + "=" * 70)
        print(f"  BENCHMARK: Single-Connectivity TN Band {band} (40 MHz, 216 PRB)")
        print("=" * 70)
    elif band == 7:
        scen_dir = os.path.join(BASE_DIR, "scenarios/single_tn_band7_20mhz")
        ue_conf = os.path.join(BASE_DIR, "ue_tn_band7.conf")
        mode_label = f"Single-TN Band 7 (20MHz)"
        print("\n" + "=" * 70)
        print("  BENCHMARK: Single-Connectivity TN Band 7 (2655 MHz DL, 20 MHz, 106 PRB)")
        print("=" * 70)
    elif band == 2:
        scen_dir = os.path.join(BASE_DIR, "scenarios/single_tn_band2_20mhz")
        ue_conf = os.path.join(BASE_DIR, "ue_tn_band2.conf")
        mode_label = f"Single-TN Band 2 (20MHz)"
        print("\n" + "=" * 70)
        print("  BENCHMARK: Single-Connectivity TN Band 2 (1960 MHz DL, 20 MHz, 106 PRB)")
        print("=" * 70)
    else:
        scen_dir = os.path.join(BASE_DIR, "scenarios/single_tn_20mhz")
        ue_conf = os.path.join(BASE_DIR, "ue_tn_20mhz.conf")
        mode_label = f"Single-TN Band {band} (20MHz)"
        print("\n" + "=" * 70)
        print("  BENCHMARK: Single-Connectivity TN Band 3 (1842.5 MHz DL, 20 MHz, 106 PRB)")
        print("=" * 70)

    cleanup()
    setup_env()

    # Step 1: Start CU-CP
    print("\n[Step 1/5] Starting CU-CP...")
    cucp_cmd = f"tail -f /dev/null | sudo {OCUDU_BIN}/cu_cp/ocucp -c {scen_dir}/cu_cp.yml > /tmp/single_tn_20mhz_cu_cp.log 2>&1"
    subprocess.Popen(cucp_cmd, shell=True)
    time.sleep(2)

    # Step 2: Start CU-UP
    print("[Step 2/5] Starting CU-UP...")
    cuup_cmd = f"tail -f /dev/null | sudo {OCUDU_BIN}/cu_up/ocuup -c {scen_dir}/cu_up.yml > /tmp/single_tn_20mhz_cu_up.log 2>&1"
    subprocess.Popen(cuup_cmd, shell=True)
    time.sleep(1)

    # Step 3: Start DU1 (20MHz, 106 PRBs)
    print(f"[Step 3/5] Starting DU1 (Band {band}, 20 MHz, 106 PRBs, SCS 15 kHz)...")
    du1_cmd = f"tail -f /dev/null | sudo {OCUDU_BIN}/du/odu -c {scen_dir}/du1.yml --gnb_du_id 1 > /tmp/single_tn_20mhz_du1.log 2>&1"
    subprocess.Popen(du1_cmd, shell=True)
    time.sleep(4)

    # Step 4: Start srsUE (20MHz, 106 PRBs)
    print(f"[Step 4/5] Starting srsUE in ue_mn namespace (Band {band}, 20 MHz, 106 PRBs)...")
    ue_cmd = f"tail -f /dev/null | sudo {SRSRAN_BIN} {ue_conf} > /tmp/single_tn_20mhz_ue.log 2>&1"
    subprocess.Popen(ue_cmd, shell=True)


    # Wait for PDU session
    print("[*] Waiting for PDU session establishment on tun_srsue...")
    ip_addr = None
    for sec in range(1, 40):
        chk = subprocess.run(
            "sudo ip netns exec ue_mn ip addr show dev tun_srsue 2>/dev/null",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        m = re.search(r"inet\s+([0-9.]+)", chk.stdout)
        if m:
            ip_addr = m.group(1)
            print(f"  [+] SUCCESS: PDU Session Established at {sec}s! Assigned IP: {ip_addr}")
            break
        time.sleep(1)

    if not ip_addr:
        print("[-] FAILED: PDU Session timed out.")
        print("--- DU1 Log Tail ---")
        subprocess.run("tail -n 25 /tmp/single_tn_20mhz_du1.log || true", shell=True)
        print("--- UE Log Tail ---")
        subprocess.run("tail -n 25 /tmp/single_tn_20mhz_ue.log || true", shell=True)
        cleanup()
        return False

    # Ensure Web Server is running
    try:
        urllib.request.urlopen("http://127.0.0.1:8080/api/status", timeout=1)
        print("[*] Web server is already running on port 8080.")
    except Exception:
        print("[*] Starting Web Server on 0.0.0.0:8080...")
        subprocess.Popen(f"python3 {BASE_DIR}/web_server/server.py 8080 > /tmp/web_server.log 2>&1", shell=True)
        time.sleep(2)

    # Ensure iperf3 server daemon is running on host
    subprocess.run("sudo pkill -9 iperf3 || true", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.Popen("iperf3 -s -D", shell=True)
    time.sleep(0.5)

    # Step 5: Traffic Benchmarks
    print("\n[Step 5/5] Running Network Performance Benchmarks & Reporting to Web Server...")

    # A: Ping test
    print("\n--- [A] Latency & RTT Benchmark (10 ICMP Pings to UPF 10.45.0.1) ---")
    ping_res = subprocess.run(
        "sudo ip netns exec ue_mn ping 10.45.0.1 -c 10",
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    print(ping_res.stdout.strip())

    # B: HTTP File Transfer Benchmark
    print(f"\n--- [B] Executing HTTP File Transfer Benchmark (Reporting to Web Server 10.45.0.1:8080) ---")
    bench_file_cmd = (
        f"sudo ip netns exec ue_mn python3 {BASE_DIR}/scripts/ue_benchmark_client.py "
        f"--server 10.45.0.1 --port 8080 --test file --samples {samples} --size-mb 5.0 "
        f"--mode-label '{mode_label}'"
    )
    subprocess.run(bench_file_cmd, shell=True)

    # C: HTTP Streaming Transfer Benchmark
    print(f"\n--- [C] Executing HTTP Streaming Transfer Benchmark (Reporting to Web Server 10.45.0.1:8080) ---")
    bench_stream_cmd = (
        f"sudo ip netns exec ue_mn python3 {BASE_DIR}/scripts/ue_benchmark_client.py "
        f"--server 10.45.0.1 --port 8080 --test stream --samples 1 --duration 10 "
        f"--mode-label '{mode_label}'"
    )
    subprocess.run(bench_stream_cmd, shell=True)

    # D: Constant Bitrate (CBR) UDP Benchmark via iperf3 (10 Samples)
    print(f"\n--- [D] Constant Bitrate (CBR) UDP Benchmark via iperf3 (10 Samples) ---")
    bench_udp_cmd = (
        f"sudo ip netns exec ue_mn python3 {BASE_DIR}/scripts/ue_benchmark_client.py "
        f"--server 10.45.0.1 --port 8080 --test udp --samples 10 --duration-udp 5 "
        f"--mode-label '{mode_label}'"
    )
    subprocess.run(bench_udp_cmd, shell=True)

    # E: Inspect DU log for MCS verification
    print(f"\n--- [E] MAC Scheduler MCS Distribution Verification ---")
    try:
        du_log_file = f"/tmp/single_ntn_20mhz_du1.log" if ntn else f"/tmp/single_tn_20mhz_du1.log"
        with open(du_log_file, "r", errors="ignore") as f:
            du_log = f.read()
        pdsch_mcs = re.findall(r"UE PDSCH:.*?mcs=(\d+)", du_log)
        pusch_mcs = re.findall(r"UE PUSCH:.*?mcs=(\d+)", du_log)
        if pdsch_mcs:
            from collections import Counter
            counts = Counter(pdsch_mcs)
            total = len(pdsch_mcs)
            print(f"  DL (PDSCH) Total Grants: {total}")
            for mcs_val, c in sorted(counts.items(), key=lambda x: int(x[0])):
                pct = (c / total) * 100
                print(f"    - MCS {mcs_val}: {c} grants ({pct:.1f}%)")
        else:
            # Check for scheduler metrics
            sched_mcs = re.findall(r"dl_mcs=(\d+)", du_log)
            if sched_mcs:
                from collections import Counter
                counts = Counter(sched_mcs)
                total = len(sched_mcs)
                print(f"  DL Metrics Samples: {total}")
                for mcs_val, c in sorted(counts.items(), key=lambda x: int(x[0])):
                    print(f"    - MCS {mcs_val}: {c} samples ({(c / total) * 100:.1f}%)")
            else:
                print("  (Note: MCS debug entries not explicitly matched in log)")
    except Exception as e:
        print(f"  Could not parse DU log for MCS: {e}")

    print("\n========================================================================")
    print(f"       BENCHMARK COMPLETE: {mode_label}")
    print("========================================================================")
    cleanup()
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run single-connectivity TN/NTN benchmark")
    parser.add_argument("--band", type=int, default=3, choices=[2, 3, 7, 38, 41], help="Operating band (2, 3, 7, 38, 41, default: 3)")
    parser.add_argument("--bw", type=int, default=20, choices=[20, 40], help="Channel bandwidth in MHz (20 or 40, default: 20)")
    parser.add_argument("--ntn", action="store_true", help="Enable NTN mode (7ms delay, mac_allowed_tx=1, pdcp/rlc timers)")
    parser.add_argument("--samples", type=int, default=10, help="Number of benchmark samples (default: 10)")
    args = parser.parse_args()
    success = run_benchmark(band=args.band, bw=args.bw, ntn=args.ntn, samples=args.samples)
    sys.exit(0 if success else 1)


