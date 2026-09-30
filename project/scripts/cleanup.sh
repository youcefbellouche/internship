#!/bin/bash
# Complete clean-up script for 5G SA Multi-Connectivity simulation

echo ""
echo "========================================================================"
echo "                   5G SIMULATION CLEANUP UTILITY"
echo "========================================================================"
echo ""
echo "[*] Terminating running 5G processes (CU-CP, CU-UP, DU1, DU2, srsUE)..."
sudo pkill -9 -f "ocucp" >/dev/null 2>&1 || true
sudo pkill -9 -f "ocuup" >/dev/null 2>&1 || true
sudo pkill -9 -f "odu" >/dev/null 2>&1 || true
sudo pkill -9 -f "srsue" >/dev/null 2>&1 || true
sudo pkill -9 -f "ping" >/dev/null 2>&1 || true
sudo pkill -9 -f "auto_switch" >/dev/null 2>&1 || true
sleep 1

echo "[*] Removing temporary control files and scenario logs (/tmp)..."
rm -f /tmp/pdcp_split_ratio
rm -f /tmp/switch_*.log /tmp/run_ue.log /tmp/scenario*.log

echo "[*] Resetting UE network namespaces (ue_mn, ue_sn)..."
sudo ip netns del ue_mn >/dev/null 2>&1 || true
sudo ip netns del ue_sn >/dev/null 2>&1 || true
sudo ip netns add ue_mn
sudo ip netns exec ue_mn ip link set lo up

# Restore terminal tty flags (fix staircase effect from interrupted raw mode)
stty sane 2>/dev/null || true

echo ""
echo "[+] Cleanup complete! Ready to start a new scenario."
echo "========================================================================"
echo ""
