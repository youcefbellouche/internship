#!/usr/bin/env python3
"""
Dynamic Switching Verification Suite for 5G Standalone Multi-Connectivity.

Tests both switching mechanisms:
  Mechanism 1 (Policy-based): Startup path selection with PDCP_SPLIT_RATIO="1:0" (Terrestrial) vs "0:1" (Satellite)
  Mechanism 2 (Live Runtime Hot-Switching): Dynamic on-the-fly path redirection via /tmp/pdcp_split_ratio during active ping
"""

import os
import sys
import time
import argparse
import subprocess
import re

BASE_DIR = "/root/internship-repo/project"
SCENARIO_DIR = os.path.join(BASE_DIR, "scenarios/scenario1_cug_d1g_d2l")
OCUDU_BIN = os.path.join(BASE_DIR, "ocudu/build/apps")
SRSRAN_BIN = os.path.join(BASE_DIR, "srsRAN_4G/build/srsue/src/srsue")
DBCTL_BIN = "/root/internship-repo/open5gs-dbctl"


def cleanup():
    subprocess.run("sudo pkill -9 -f ocucp || true", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run("sudo pkill -9 -f ocuup || true", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run("sudo pkill -9 -f odu || true", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run("sudo pkill -9 -f srsue || true", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run("rm -f /tmp/pdcp_split_ratio", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run("stty sane 2>/dev/null || true", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)


def setup_env():
    subprocess.run(f"sudo {DBCTL_BIN} add 999700123456780 00112233445566778899aabbccddeeff 63BFA50EE6523365FF14C1F45F88737D || true", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(f"sudo {DBCTL_BIN} add 999700123456781 00112233445566778899aabbccddeeff 63BFA50EE6523365FF14C1F45F88737D || true", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run("sudo ip netns add ue_mn || true", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run("sudo ip netns exec ue_mn ip link set lo up || true", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def start_nodes(split_ratio_env=None):
    cleanup()
    setup_env()

    cu_cp_cfg = os.path.join(SCENARIO_DIR, "cu_cp.yml")
    cu_up_cfg = os.path.join(SCENARIO_DIR, "cu_up.yml")
    du1_cfg = os.path.join(SCENARIO_DIR, "du1.yml")
    du2_cfg = os.path.join(SCENARIO_DIR, "du2.yml")

    print("  -> [1/5] Launching CU-CP...")
    subprocess.Popen(f"tail -f /dev/null | sudo {OCUDU_BIN}/cu_cp/ocucp -c {cu_cp_cfg} > /tmp/switch_cu_cp.log 2>&1", shell=True)
    time.sleep(2)

    print("  -> [2/5] Launching CU-UP...")
    subprocess.Popen(f"tail -f /dev/null | sudo {OCUDU_BIN}/cu_up/ocuup -c {cu_up_cfg} > /tmp/switch_cu_up.log 2>&1", shell=True)
    time.sleep(1)

    print("  -> [3/5] Launching DU1 (Terrestrial leg)...")
    subprocess.Popen(f"tail -f /dev/null | sudo {OCUDU_BIN}/du/odu -c {du1_cfg} --gnb_du_id 1 > /tmp/switch_du1.log 2>&1", shell=True)
    time.sleep(3)

    print("  -> [4/5] Launching DU2 (LEO Satellite leg)...")
    subprocess.Popen(f"tail -f /dev/null | sudo {OCUDU_BIN}/du/odu -c {du2_cfg} --gnb_du_id 2 > /tmp/switch_du2.log 2>&1", shell=True)
    time.sleep(8)

    print("  -> [5/5] Launching Monolithic Dual-Path srsue...")
    env_str = f"PDCP_SPLIT_RATIO={split_ratio_env} " if split_ratio_env else ""
    ue_cmd = f"tail -f /dev/null | sudo {env_str}SRSUE_SN_CONFIG={BASE_DIR}/ue_sn.conf {SRSRAN_BIN} {BASE_DIR}/ue_mn.conf > /tmp/switch_ue.log 2>&1"
    subprocess.Popen(ue_cmd, shell=True, stdin=subprocess.DEVNULL)

    print("\n  [*] Waiting for PDU session establishment...")
    for sec in range(1, 35):
        chk = subprocess.run("sudo ip netns exec ue_mn ip addr show dev tun_srsue 2>/dev/null", shell=True, stdout=subprocess.PIPE, universal_newlines=True)
        m = re.search(r"inet\s+([0-9.]+)", chk.stdout)
        if m:
            print(f"  [+] PDU Session established at {sec}s! IP: {m.group(1)}\n")
            return True
        time.sleep(1)

    print("  [-] PDU Session timeout!\n")
    return False


def test_mechanism1_policy():
    print("\n" + "=" * 75)
    print("  TEST MECHANISM 1: Policy-Based Switching via Startup Ratio (1:0 vs 0:1)")
    print("=" * 75 + "\n")

    results = {}

    # 1. Test 1:0 (100% Terrestrial DU1)
    print("--- Test 1.1: Activating Terrestrial Path Only (PDCP_SPLIT_RATIO='1:0') ---\n")
    if start_nodes(split_ratio_env="1:0"):
        time.sleep(1)
        print("[*] Pinging UPF gateway 10.45.0.1 (5 packets)...\n")
        ping = subprocess.run("sudo ip netns exec ue_mn ping 10.45.0.1 -c 5", shell=True, stdout=subprocess.PIPE, universal_newlines=True)
        print(ping.stdout.strip() + "\n")
        rtt = re.search(r"rtt min/avg/max/mdev = ([0-9.]+)/([0-9.]+)/([0-9.]+)/([0-9.]+)\s+ms", ping.stdout)
        results["1:0 (Terrestrial)"] = float(rtt.group(2)) if rtt else "N/A"
    cleanup()

    # 2. Test 0:1 (100% Satellite DU2)
    print("\n--- Test 1.2: Activating Satellite Path Only (PDCP_SPLIT_RATIO='0:1') ---\n")
    if start_nodes(split_ratio_env="0:1"):
        time.sleep(7)
        print("[*] Pinging UPF gateway 10.45.0.1 (5 packets)...\n")
        ping = subprocess.run("sudo ip netns exec ue_mn ping 10.45.0.1 -c 5", shell=True, stdout=subprocess.PIPE, universal_newlines=True)
        print(ping.stdout.strip() + "\n")
        rtt = re.search(r"rtt min/avg/max/mdev = ([0-9.]+)/([0-9.]+)/([0-9.]+)/([0-9.]+)\s+ms", ping.stdout)
        results["0:1 (Satellite)"] = float(rtt.group(2)) if rtt else "N/A"
    cleanup()

    print("\n" + "=" * 60)
    print("             Mechanism 1 Results Summary")
    print("=" * 60)
    for mode, rtt in results.items():
        print(f"  Mode {mode:<22} -> Average RTT: {rtt} ms")
    print("=" * 60 + "\n")


def test_mechanism2_runtime():
    print("\n" + "=" * 75)
    print("  TEST MECHANISM 2: Live Runtime Hot-Switching via /tmp/pdcp_split_ratio")
    print("=" * 75 + "\n")

    # Pre-set to 1:0 (Terrestrial DU1)
    with open("/tmp/pdcp_split_ratio", "w") as f:
        f.write("1:0\n")

    print("[*] Booting stack with initial path: DU1 Terrestrial (1:0)...\n")
    if not start_nodes():
        cleanup()
        return

    time.sleep(2)
    print("[*] Initiating continuous ping (10 packets to 10.45.0.1)...")
    print("[*] Switching command will be executed live at Packet 5!\n")

    # Start ping in background
    ping_proc = subprocess.Popen(
        "sudo ip netns exec ue_mn ping 10.45.0.1 -c 10",
        shell=True,
        stdout=subprocess.PIPE,
        universal_newlines=True
    )

    # Wait for 5 packets (~5 seconds), then execute hot-switch
    time.sleep(5)
    print("\n>>> [TRIGGERING RUNTIME SWITCH]: Redirecting user traffic to DU2 Satellite (0:1) <<<")
    with open("/tmp/pdcp_split_ratio", "w") as f:
        f.write("0:1\n")
    print(">>> Updated /tmp/pdcp_split_ratio to '0:1' <<<\n")

    stdout, _ = ping_proc.communicate()
    print(stdout.strip() + "\n")

    cleanup()
    print("[+] Mechanism 2 Test Complete!\n")


if __name__ == "__main__":
    subprocess.run("stty sane 2>/dev/null || true", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    parser = argparse.ArgumentParser(description="5G SA Dynamic Switching Verification")
    parser.add_argument("--mode", choices=["policy", "runtime", "all"], default="all", help="Which mechanism to test")
    args = parser.parse_args()

    if args.mode in ["policy", "all"]:
        test_mechanism1_policy()
    if args.mode in ["runtime", "all"]:
        test_mechanism2_runtime()
