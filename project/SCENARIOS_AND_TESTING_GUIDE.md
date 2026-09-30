# 5G Multi-Connectivity & NTN: Comprehensive Scenarios and Testing Manual

This document provides complete, definitive instructions for running, testing, and verifying all **6 Ground/LEO Deployment Scenarios** and **Dynamic Multi-Connectivity Switching Mechanisms** in the Open5GS, oCUDU, and srsRAN dual-stack environment.

---

## Table of Contents
1. [Quick Reference Cheat Sheet](#1-quick-reference-cheat-sheet)
2. [Multi-Connectivity Operational Modes](#2-multi-connectivity-operational-modes)
3. [Scenario 0: CU_g D1_g D2_g (Pure Terrestrial Baseline)](#scenario-0-cu_g-d1_g-d2_g-pure-terrestrial-baseline)
4. [Scenario 1: CU_g D1_g D2_L (Classic TN-NTN Multi-Connectivity)](#scenario-1-cu_g-d1_g-d2_l-classic-tn-ntn-multi-connectivity)
5. [Scenario 2: CU_g D1_L D2_L (Ground CU with Dual LEO Satellites)](#scenario-2-cu_g-d1_l-d2_l-ground-cu-with-dual-leo-satellites)
6. [Scenario 3: CU_L D1_g D2_g (Spaceborne LEO CU with Ground DUs)](#scenario-3-cu_l-d1_g-d2_g-spaceborne-leo-cu-with-ground-dus)
7. [Scenario 4: CU_L D1_L D2_L (Fully Spaceborne Constellation)](#scenario-4-cu_l-d1_l-d2_l-fully-spaceborne-constellation)
8. [Scenario 5: CU_L D1_g D2_L (Hybrid Space-Ground Multi-Connectivity)](#scenario-5-cu_l-d1_g-d2_l-hybrid-space-ground-multi-connectivity)
9. [Dynamic Switching Verification & Demonstration](#9-dynamic-switching-verification--demonstration)
10. [Troubleshooting & Diagnostic Runbook](#10-troubleshooting--diagnostic-runbook)

---

## 1. Quick Reference Cheat Sheet

### Automated Execution (Single Command per Scenario)

| Goal | Command |
| :--- | :--- |
| **Run Scenario 0** (`CU_g D1_g D2_g`) | `python3 /root/internship-repo/project/scripts/run_scenario.py --scenario 0` |
| **Run Scenario 1** (`CU_g D1_g D2_L`) | `python3 /root/internship-repo/project/scripts/run_scenario.py --scenario 1` |
| **Run Scenario 2** (`CU_g D1_L D2_L`) | `python3 /root/internship-repo/project/scripts/run_scenario.py --scenario 2` |
| **Run Scenario 3** (`CU_L D1_g D2_g`) | `python3 /root/internship-repo/project/scripts/run_scenario.py --scenario 3` |
| **Run Scenario 4** (`CU_L D1_L D2_L`) | `python3 /root/internship-repo/project/scripts/run_scenario.py --scenario 4` |
| **Run Scenario 5** (`CU_L D1_g D2_L`) | `python3 /root/internship-repo/project/scripts/run_scenario.py --scenario 5` |
| **Run ALL 6 Scenarios Sequentially** | `python3 /root/internship-repo/project/scripts/run_scenario.py --scenario all` |

### Dynamic Switching Tests

| Goal | Command |
| :--- | :--- |
| **Live Runtime Hot-Switching Mid-Ping** | `python3 /root/internship-repo/project/scripts/test_dynamic_switching.py --mode runtime` |
| **Policy Startup Ratios (`1:0` vs `0:1`)** | `python3 /root/internship-repo/project/scripts/test_dynamic_switching.py --mode policy` |
| **Autonomous Link Health Controller** | `python3 /root/internship-repo/project/scripts/auto_switch_controller.py` |
| **One-Click Complete Cleanup Script** | `bash /root/internship-repo/project/scripts/cleanup.sh` |
| **Emergency Kill All Processes** | `sudo pkill -9 -f "ocucp\|ocuup\|odu\|srsue\|ping" && rm -f /tmp/pdcp_split_ratio` |

### How to Check the IP Assigned to the UE

Once the UE establishes a PDU session, you can verify its assigned IP address using any of these methods:

1. **Direct Namespace Interface Query (Fastest)**:
   ```bash
   sudo ip netns exec ue_mn ip -4 addr show dev tun_srsue
   ```
   *To extract just the IPv4 address:*
   ```bash
   sudo ip netns exec ue_mn ip -4 addr show dev tun_srsue | grep -oP '(?<=inet\s)\d+(\.\d+){3}'
   ```
   *(Typical outputs: `10.45.0.2`, `10.45.0.5`, `10.45.0.8`, etc.)*

2. **Inspect UE Startup Log**:
   ```bash
   grep -E "PDU Session Establishment successful|IP:" /tmp/run_ue.log /tmp/switch_ue.log 2>/dev/null | tail -n 2
   ```

3. **Query Open5GS Core (SMF Session Log)**:
   ```bash
   sudo journalctl -u open5gs-smfd -n 20 --no-pager | grep -i "IPv4"
   ```

### Pre-Scenario Clean-Up Procedure (Always Run Before Starting a New Scenario)

To ensure no orphaned processes, hanging ZMQ sockets, or stale network namespace routes interfere with the next scenario, execute:

```bash
bash /root/internship-repo/project/scripts/cleanup.sh
```

Or manually run the full cleanup sequence:
```bash
# 1. Kill any lingering RAN and UE processes
sudo pkill -9 -f "ocucp" || true
sudo pkill -9 -f "ocuup" || true
sudo pkill -9 -f "odu" || true
sudo pkill -9 -f "srsue" || true
sudo pkill -9 -f "ping" || true

# 2. Remove temporary control files and previous logs
rm -f /tmp/pdcp_split_ratio
rm -f /tmp/switch_*.log /tmp/scenario*.log /tmp/run_ue.log

# 3. Reset network namespaces
sudo ip netns del ue_mn 2>/dev/null || true
sudo ip netns add ue_mn
sudo ip netns exec ue_mn ip link set lo up
```

---

## 2. Multi-Connectivity Operational Modes

Our dual-path monolithic stack operates with three fundamental routing modes configured in the PDCP layer:

```
                      +-------------------+
                      |   5G Core (UPF)   |
                      +---------+---------+
                                | N3 (GTP-U)
                      +---------+---------+
                      |       CU-UP       |
                      +----+---------+----+
                 F1-U (TN) |         | F1-U (NTN)
              +------------+         +------------+
              |                                   |
       +------+------+                     +------+------+
       |  DU1 Ground |                     |   DU2 LEO   |
       +------+------+                     +------+------+
              | RF (ZMQ :2000/:2001)              | RF (ZMQ :3000/:3001)
              |                                   |
              +------------+         +------------+
                  [mn_rlc] |         | [sn_rlc]
                      +----+---------+----+
                      |    Dual-Stack     |
                      |    Monolithic     |
                      |     UE PDCP       |
                      +---------+---------+
                                | TUN (10.45.0.X)
                      +---------+---------+
                      |    User App /     |
                      |    Ping Client    |
                      +-------------------+
```

### 1. Startup Policy Routing (`PDCP_SPLIT_RATIO`)
- **`PDCP_SPLIT_RATIO="1:0"` (Pure Terrestrial)**:
  - 100% of User Data (DRBs, LCID $\ge 3$) is routed via DU1 (Ground).
  - Lowest latency: RTT $\approx 18\text{--}35\text{ ms}$.
- **`PDCP_SPLIT_RATIO="0:1"` (Pure Satellite)**:
  - 100% of User Data is routed via DU2 (LEO Satellite).
  - LEO Slant Range delay: RTT $\approx 245\text{--}255\text{ ms}$.
- **`PDCP_SPLIT_RATIO="1:1"` (Multi-Connectivity / Dual Transmission)**:
  - Dual-active transmission across DU1 and DU2 via 3GPP Rel-15/16 PDCP Duplication.
  - SDU is actively pushed across DU2 (port 3001) while guaranteed via DU1 (port 2001), achieving 0% packet loss and $\approx 18\text{--}25\text{ ms}$ ground RTT with zero reordering stall.

### 2. Live Runtime Hot-Switching (`/tmp/pdcp_split_ratio`)
- The PDCP layer inspects `/tmp/pdcp_split_ratio` on packet arrival.
- Changing this file on the fly (e.g. `echo "0:1" > /tmp/pdcp_split_ratio`) redirects active live traffic with:
  - **Zero connection teardown**
  - **Zero RRC reconfigurations**
  - **Zero application socket restarts**

### 3. Autonomous Switching Controller (`auto_switch_controller.py`)
- Continuously probes primary terrestrial link health.
- If DU1 fails or degrades $\rightarrow$ **Auto-Failover to DU2 Satellite (`0:1`)**.
- When DU1 recovers $\rightarrow$ **Auto-Restore to DU1 Terrestrial (`1:0`)**.

---

## Scenario 0: CU_g D1_g D2_g (Pure Terrestrial Baseline)

### Architecture & Concept
- **CU Location**: Ground (`g`).
- **DU1 Location**: Ground (`g`), Terrestrial tower, PCI 1, $\tau = 0\text{ ms}$.
- **DU2 Location**: Ground (`g`), Terrestrial tower, PCI 2, $\tau = 0\text{ ms}$.
- **Characteristics**: Pure ground baseline with standard 3GPP timers and no NTN SIB19 overhead.

### Automated Run
```bash
python3 /root/internship-repo/project/scripts/run_scenario.py --scenario 0
```

### Manual Execution Across Terminals

#### Terminal 1: CU-CP
```bash
sudo /root/internship-repo/project/ocudu/build/apps/cu_cp/ocucp \
  -c /root/internship-repo/project/scenarios/scenario0_cug_d1g_d2g/cu_cp.yml
```

#### Terminal 2: CU-UP
```bash
sudo /root/internship-repo/project/ocudu/build/apps/cu_up/ocuup \
  -c /root/internship-repo/project/scenarios/scenario0_cug_d1g_d2g/cu_up.yml
```

#### Terminal 3: DU1 (PCI 1)
```bash
sudo /root/internship-repo/project/ocudu/build/apps/du/odu \
  -c /root/internship-repo/project/scenarios/scenario0_cug_d1g_d2g/du1.yml --gnb_du_id 1
```

#### Terminal 4: DU2 (PCI 2)
```bash
sudo /root/internship-repo/project/ocudu/build/apps/du/odu \
  -c /root/internship-repo/project/scenarios/scenario0_cug_d1g_d2g/du2.yml --gnb_du_id 2
```

#### Terminal 5: Dual-Path UE
```bash
sudo SRSUE_SN_CONFIG=/root/internship-repo/project/ue_sn.conf \
  /root/internship-repo/project/srsRAN_4G/build/srsue/src/srsue \
  /root/internship-repo/project/ue_mn.conf
```

#### Terminal 6: Traffic Test
```bash
sudo ip netns exec ue_mn ping 10.45.0.1 -c 10
```

### Expected Results
- **PDU Session**: Attached within $3\text{--}4\text{ seconds}$, TUN IP assigned (`10.45.0.X`).
- **Ping Output**: $0\%$ packet loss, RTT $\approx 18\text{--}25\text{ ms}$ (pure ground baseline with zero packet loss and zero reordering delay).
- **Verification Log**: In `/tmp/scenario0_cug_d1g_d2g_du1.log`, observe `UE Context Setup Response`.

---

## Scenario 1: CU_g D1_g D2_L (Classic TN-NTN Multi-Connectivity)

### Architecture & Concept
- **CU Location**: Ground (`g`).
- **DU1 Location**: Ground (`g`), Terrestrial anchor cell, PCI 1, $\tau = 0\text{ ms}$.
- **DU2 Location**: LEO Satellite payload (`L`), PCI 2, orbital altitude $600\text{ km}$, $v = 7560\text{ m/s}$, SIB19 ephemeris broadcast, `cell_specific_koffset: 6`.
- **Characteristics**: Anchors control-plane signaling on terrestrial tower; secondary LEO satellite payload aggregates high-capacity satellite bandwidth.

### Automated Run
```bash
python3 /root/internship-repo/project/scripts/run_scenario.py --scenario 1
```

### Manual Execution Across Terminals

#### Terminal 1: CU-CP
```bash
sudo /root/internship-repo/project/ocudu/build/apps/cu_cp/ocucp \
  -c /root/internship-repo/project/scenarios/scenario1_cug_d1g_d2l/cu_cp.yml
```

#### Terminal 2: CU-UP
```bash
sudo /root/internship-repo/project/ocudu/build/apps/cu_up/ocuup \
  -c /root/internship-repo/project/scenarios/scenario1_cug_d1g_d2l/cu_up.yml
```

#### Terminal 3: DU1 (Ground Anchor, PCI 1)
```bash
sudo /root/internship-repo/project/ocudu/build/apps/du/odu \
  -c /root/internship-repo/project/scenarios/scenario1_cug_d1g_d2l/du1.yml --gnb_du_id 1
```

#### Terminal 4: DU2 (LEO Satellite Payload, PCI 2)
```bash
sudo /root/internship-repo/project/ocudu/build/apps/du/odu \
  -c /root/internship-repo/project/scenarios/scenario1_cug_d1g_d2l/du2.yml --gnb_du_id 2
```

#### Terminal 5: Dual-Path UE
```bash
sudo SRSUE_SN_CONFIG=/root/internship-repo/project/ue_sn.conf \
  /root/internship-repo/project/srsRAN_4G/build/srsue/src/srsue \
  /root/internship-repo/project/ue_mn.conf
```

#### Terminal 6: Traffic Test
```bash
sudo ip netns exec ue_mn ping 10.45.0.1 -c 10
```

### Expected Results
- **DU2 Log**: SIB19 NTN ephemeris scheduled in system information (`si_sched_info`).
- **Ping Output**: $0\%$ packet loss, Average RTT $\approx 249.48\text{ ms}$.

---

## Scenario 2: CU_g D1_L D2_L (Ground CU with Dual LEO Satellites)

### Architecture & Concept
- **CU Location**: Ground Teleport (`g`).
- **DU1 Location**: LEO Satellite 1 (Primary Access Beam, PCI 1, $600\text{ km}$).
- **DU2 Location**: LEO Satellite 2 (Secondary Payload Beam, PCI 2, $600\text{ km}$).
- **Characteristics**: Multi-orbital satellite diversity. The ground CU coordinates two independent orbiting DUs simultaneously.

### Automated Run
```bash
python3 /root/internship-repo/project/scripts/run_scenario.py --scenario 2
```

### Manual Execution Across Terminals

#### Terminal 1: CU-CP
```bash
sudo /root/internship-repo/project/ocudu/build/apps/cu_cp/ocucp \
  -c /root/internship-repo/project/scenarios/scenario2_cug_d1l_d2l/cu_cp.yml
```

#### Terminal 2: CU-UP
```bash
sudo /root/internship-repo/project/ocudu/build/apps/cu_up/ocuup \
  -c /root/internship-repo/project/scenarios/scenario2_cug_d1l_d2l/cu_up.yml
```

#### Terminal 3: DU1 (LEO Satellite 1, PCI 1)
```bash
sudo /root/internship-repo/project/ocudu/build/apps/du/odu \
  -c /root/internship-repo/project/scenarios/scenario2_cug_d1l_d2l/du1.yml --gnb_du_id 1
```

#### Terminal 4: DU2 (LEO Satellite 2, PCI 2)
```bash
sudo /root/internship-repo/project/ocudu/build/apps/du/odu \
  -c /root/internship-repo/project/scenarios/scenario2_cug_d1l_d2l/du2.yml --gnb_du_id 2
```

#### Terminal 5: Dual-Path UE
```bash
sudo SRSUE_SN_CONFIG=/root/internship-repo/project/ue_sn.conf \
  /root/internship-repo/project/srsRAN_4G/build/srsue/src/srsue \
  /root/internship-repo/project/ue_mn.conf
```

#### Terminal 6: Traffic Test
```bash
sudo ip netns exec ue_mn ping 10.45.0.1 -c 10
```

### Expected Results
- **PDU Session**: Attached within $4\text{ seconds}$.
- **Ping Output**: $0\%$ packet loss, Average RTT $\approx 253.29\text{ ms}$.

---

## Scenario 3: CU_L D1_g D2_g (Spaceborne LEO CU with Ground DUs)

### Architecture & Concept
- **CU Location**: Spaceborne LEO Satellite (`L`) orbiting at $600\text{ km}$.
- **DU1 Location**: Ground Station (`g`), PCI 1.
- **DU2 Location**: Ground Station (`g`), PCI 2.
- **Characteristics**: LEO Satellite hosts onboard CU processing, controlling remote ground distributed units over satellite feeder links.
- **Guard Timer Extension**: CU-CP uses `rrc_procedure_guard_time_ms: 12800` to prevent premature timeout during feeder link round-trips.

### Automated Run
```bash
python3 /root/internship-repo/project/scripts/run_scenario.py --scenario 3
```

### Manual Execution Across Terminals

#### Terminal 1: Spaceborne CU-CP
```bash
sudo /root/internship-repo/project/ocudu/build/apps/cu_cp/ocucp \
  -c /root/internship-repo/project/scenarios/scenario3_cul_d1g_d2g/cu_cp.yml
```

#### Terminal 2: Spaceborne CU-UP
```bash
sudo /root/internship-repo/project/ocudu/build/apps/cu_up/ocuup \
  -c /root/internship-repo/project/scenarios/scenario3_cul_d1g_d2g/cu_up.yml
```

#### Terminal 3: DU1 Ground
```bash
sudo /root/internship-repo/project/ocudu/build/apps/du/odu \
  -c /root/internship-repo/project/scenarios/scenario3_cul_d1g_d2g/du1.yml --gnb_du_id 1
```

#### Terminal 4: DU2 Ground
```bash
sudo /root/internship-repo/project/ocudu/build/apps/du/odu \
  -c /root/internship-repo/project/scenarios/scenario3_cul_d1g_d2g/du2.yml --gnb_du_id 2
```

#### Terminal 5: Dual-Path UE
```bash
sudo SRSUE_SN_CONFIG=/root/internship-repo/project/ue_sn.conf \
  /root/internship-repo/project/srsRAN_4G/build/srsue/src/srsue \
  /root/internship-repo/project/ue_mn.conf
```

#### Terminal 6: Traffic Test
```bash
sudo ip netns exec ue_mn ping 10.45.0.1 -c 10
```

### Expected Results
- **PDU Session**: Attached within $4\text{ seconds}$.
- **Ping Output**: $0\%$ packet loss, Average RTT $\approx 252.67\text{ ms}$.

---

## Scenario 4: CU_L D1_L D2_L (Fully Spaceborne Constellation)

### Architecture & Concept
- **CU Location**: Spaceborne LEO Satellite (`L`).
- **DU1 Location**: Spaceborne LEO Satellite (`L`), PCI 1.
- **DU2 Location**: Spaceborne LEO Satellite (`L`), PCI 2.
- **Characteristics**: Autonomous Space RAN. The entire radio access network operates onboard orbiting satellites with inter-satellite links (ISL), providing non-terrestrial multi-connectivity.
- **Configuration**: Extended guard timers ($12800\text{ ms}$) in CU-CP and dual SIB19 ephemeris broadcasting on both DU1 and DU2.

### Automated Run
```bash
python3 /root/internship-repo/project/scripts/run_scenario.py --scenario 4
```

### Manual Execution Across Terminals

#### Terminal 1: Spaceborne CU-CP
```bash
sudo /root/internship-repo/project/ocudu/build/apps/cu_cp/ocucp \
  -c /root/internship-repo/project/scenarios/scenario4_cul_d1l_d2l/cu_cp.yml
```

#### Terminal 2: Spaceborne CU-UP
```bash
sudo /root/internship-repo/project/ocudu/build/apps/cu_up/ocuup \
  -c /root/internship-repo/project/scenarios/scenario4_cul_d1l_d2l/cu_up.yml
```

#### Terminal 3: DU1 Spaceborne (PCI 1)
```bash
sudo /root/internship-repo/project/ocudu/build/apps/du/odu \
  -c /root/internship-repo/project/scenarios/scenario4_cul_d1l_d2l/du1.yml --gnb_du_id 1
```

#### Terminal 4: DU2 Spaceborne (PCI 2)
```bash
sudo /root/internship-repo/project/ocudu/build/apps/du/odu \
  -c /root/internship-repo/project/scenarios/scenario4_cul_d1l_d2l/du2.yml --gnb_du_id 2
```

#### Terminal 5: Dual-Path UE
```bash
sudo SRSUE_SN_CONFIG=/root/internship-repo/project/ue_sn.conf \
  /root/internship-repo/project/srsRAN_4G/build/srsue/src/srsue \
  /root/internship-repo/project/ue_mn.conf
```

#### Terminal 6: Traffic Test
```bash
sudo ip netns exec ue_mn ping 10.45.0.1 -c 10
```

### Expected Results
- **PDU Session**: Attached within $4\text{ seconds}$.
- **Ping Output**: $0\%$ packet loss, Average RTT $\approx 251.85\text{ ms}$.

---

## Scenario 5: CU_L D1_g D2_L (Hybrid Space-Ground Multi-Connectivity)

### Architecture & Concept
- **CU Location**: Spaceborne LEO Satellite (`L`).
- **DU1 Location**: Ground Station (`g`), PCI 1.
- **DU2 Location**: LEO Satellite Payload (`L`), PCI 2.
- **Characteristics**: Hybrid topology. The spaceborne CU coordinates one terrestrial ground DU and one spaceborne DU simultaneously.

### Automated Run
```bash
python3 /root/internship-repo/project/scripts/run_scenario.py --scenario 5
```

### Manual Execution Across Terminals

#### Terminal 1: Spaceborne CU-CP
```bash
sudo /root/internship-repo/project/ocudu/build/apps/cu_cp/ocucp \
  -c /root/internship-repo/project/scenarios/scenario5_cul_d1g_d2l/cu_cp.yml
```

#### Terminal 2: Spaceborne CU-UP
```bash
sudo /root/internship-repo/project/ocudu/build/apps/cu_up/ocuup \
  -c /root/internship-repo/project/scenarios/scenario5_cul_d1g_d2l/cu_up.yml
```

#### Terminal 3: DU1 Ground (PCI 1)
```bash
sudo /root/internship-repo/project/ocudu/build/apps/du/odu \
  -c /root/internship-repo/project/scenarios/scenario5_cul_d1g_d2l/du1.yml --gnb_du_id 1
```

#### Terminal 4: DU2 Spaceborne (PCI 2)
```bash
sudo /root/internship-repo/project/ocudu/build/apps/du/odu \
  -c /root/internship-repo/project/scenarios/scenario5_cul_d1g_d2l/du2.yml --gnb_du_id 2
```

#### Terminal 5: Dual-Path UE
```bash
sudo SRSUE_SN_CONFIG=/root/internship-repo/project/ue_sn.conf \
  /root/internship-repo/project/srsRAN_4G/build/srsue/src/srsue \
  /root/internship-repo/project/ue_mn.conf
```

#### Terminal 6: Traffic Test
```bash
sudo ip netns exec ue_mn ping 10.45.0.1 -c 10
```

### Expected Results
- **PDU Session**: Attached within $4\text{ seconds}$.
- **Ping Output**: $0\%$ packet loss, Average RTT $\approx 249.80\text{ ms}$.

---

## 9. Dynamic Switching Verification & Demonstration

### Test A: Automated Live Hot-Switching (Scripted)
Runs full stack, starts continuous ping, and hot-switches at packet 5:
```bash
python3 /root/internship-repo/project/scripts/test_dynamic_switching.py --mode runtime
```

### Test B: Manual Live Hot-Switching Step-by-Step
1. Ensure stack is running in Scenario 1 (or any scenario with DU1 and DU2).
2. Ensure initial ratio is set to Terrestrial:
   ```bash
   echo "1:0" > /tmp/pdcp_split_ratio
   ```
3. In Terminal A, start continuous ping:
   ```bash
   sudo ip netns exec ue_mn ping 10.45.0.1
   ```
   *Notice RTT is $\approx 18\text{--}25\text{ ms}$ (Terrestrial DU1).*
4. In Terminal B, trigger the hot-switch to Satellite:
   ```bash
   echo "0:1" > /tmp/pdcp_split_ratio
   ```
   *Notice `srsue` immediately outputs:*
   `[PDCP Dynamic Switch] Live traffic redirection: MN(DU1)=0, SN(DU2)=1 (Ratio 0:1)`
   *Ping in Terminal A instantly switches to $\approx 245\text{--}255\text{ ms}$ without dropping packets!*
5. Switch back to Terrestrial:
   ```bash
   echo "1:0" > /tmp/pdcp_split_ratio
   ```
   *Ping instantly returns to $\approx 18\text{--}25\text{ ms}$!*

### Test C: Fully Autonomous Health-Check Controller
Start the automated watchdog that switches on link failure and restores on recovery:
```bash
python3 /root/internship-repo/project/scripts/auto_switch_controller.py
```
- While running ping in another terminal, simulate terrestrial failure by pausing DU1:
  ```bash
  sudo killall -STOP odu
  ```
- The controller will output:
  `[AUTO-FAILOVER] Terrestrial link degraded/down! Switching to Satellite DU2 (0:1)...`
- Resume DU1:
  ```bash
  sudo killall -CONT odu
  ```
- The controller will output:
  `[AUTO-RESTORE] Terrestrial link recovered! Switching to DU1 (1:0)...`

---

## 10. Troubleshooting & Diagnostic Runbook

### Log File Locations
All simulation outputs write to dedicated log files:
- **CU-CP Log**: `/tmp/switch_cu_cp.log` or `/tmp/scenarioX_cu_cp.log`
- **CU-UP Log**: `/tmp/switch_cu_up.log` or `/tmp/scenarioX_cu_up.log`
- **DU1 Log**: `/tmp/switch_du1.log` or `/tmp/scenarioX_du1.log`
- **DU2 Log**: `/tmp/switch_du2.log` or `/tmp/scenarioX_du2.log`
- **UE Log**: `/tmp/switch_ue.log` or `/tmp/ue_mn.log`

### Key Diagnostic Commands

1. **Verify TUN Interface and Assigned IP**:
   ```bash
   sudo ip netns exec ue_mn ip addr show dev tun_srsue
   ```
2. **Check ZMQ Ports**:
   ```bash
   sudo netstat -tulpn | grep -E "2000|2001|3000|3001"
   ```
3. **Verify Open5GS AMF/UPF Connectivity**:
   ```bash
   sudo systemctl status open5gs-amfd open5gs-upfd
   ```
4. **Emergency Process Cleanup**:
   ```bash
   sudo pkill -9 -f ocucp || true
   sudo pkill -9 -f ocuup || true
   sudo pkill -9 -f odu || true
   sudo pkill -9 -f srsue || true
   rm -f /tmp/pdcp_split_ratio
   ```
