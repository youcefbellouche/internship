# 📡 5G Space-Terrestrial Multi-Connectivity (MR-DC) Testbed

A fully software-based, containerized, end-to-end 5G Multi-Radio Dual Connectivity (MR-DC) and Non-Terrestrial Network (NTN) simulation environment. 

This testbed integrates an **Open5GS 5G Core**, a **disaggregated 3GPP Release 17 gNodeB (oCUDU CU-CP, CU-UP, DU1, DU2)**, and a **monolithic dual-carrier UE (modified srsRAN 4G)** communicating over virtual ZeroMQ (ZMQ) RF buses. It provides real-time dynamic traffic splitting, URLLC packet duplication, queue-aware link switching, and emulated orbital satellite latency without requiring physical radio equipment.

---

## 🏗️ Architecture Overview

```
                                  +-----------------------+
                                  |   Open5GS 5G Core     |
                                  |   (AMF, SMF, UPF)     |
                                  +-----------+-----------+
                                              | N3 (GTP-U)
                                  +-----------v-----------+
                                  |     oCUDU CU-CP       |
                                  |     & CU-UP Stack     |
                                  +-----+-----------+-----+
                              F1-C/U    |           |    F1-C/U
              +-------------------------+           +-------------------------+
              |                                                               |
  +-----------v-----------+                                       +-----------v-----------+
  |    DU1 (Terrestrial)  |                                       |   DU2 (Satellite NTN) |
  |  - Band 3 (20 MHz)    |                                       |  - Band 2 (20 MHz)    |
  |  - ZeroMQ 2000 / 2001 |                                       |  - ZeroMQ 3000 / 3001 |
  |  - Latency: ~0 ms     |                                       |  - Latency: 7 ms / 120|
  |  - Standard SIB1      |                                       |  - SIB19 + HARQ retx=0|
  +-----------+-----------+                                       +-----------+-----------+
              | Virtual RF                                                    | Virtual RF (delayed)
              +-------------------------+           +-------------------------+
                                        |           |
                                  +-----v-----------v-----+
                                  |   srsRAN Dual-Stack   |
                                  |      Unified UE       |
                                  |  RLC1 (MN)  RLC2 (SN) |
                                  |     \         /       |
                                  |     rlc_split_bridge  |
                                  |     (Unified PDCP)    |
                                  |           |           |
                                  |   tun_srsue (IP Dev)  |
                                  +-----------------------+
```

### Protocol Components
1. **5G Core Network (Open5GS)**: Provides 3GPP Rel-16/17 Standalone 5G Core services (AMF, SMF, UPF, NRF, UDM, UDR, AUSF, BSF, PCF) backed by MongoDB. User-plane egress terminates on the Linux kernel TUN interface `ogstun` (`10.45.0.1/16`).
2. **Disaggregated gNodeB (oCUDU)**:
   - **CU-CP**: Central Unit Control Plane executing 3GPP RRC, E1AP, and F1AP signaling.
   - **CU-UP**: Central Unit User Plane terminating N3 (GTP-U) and bridging F1-U user-plane tunnels.
   - **$\mathbf{DU_1}$ (Terrestrial Master Node)**: Terrestrial 5G cell operating on NR Band 3 ($f_c = 1747.5\text{ MHz}$, DL ARFCN `368500`, 20 MHz, 106 PRBs, SCS 15 kHz, nominal ground latency $\approx 0\text{ ms}$).
   - **$\mathbf{DU_2}$ (Satellite Secondary Node)**: Spaceborne cell operating on NR Band 2 ($f_c = 1960.0\text{ MHz}$, DL ARFCN `386000`, 20 MHz, 106 PRBs, SCS 15 kHz) with emulated orbital propagation delay ($7\text{ ms}$ one-way LEO or $120\text{ ms}$ GEO), SIB19 ephemeris broadcasting, and disabled MAC HARQ retransmissions (`max_nof_harq_retxs = 0`).
3. **Monolithic Dual-Carrier UE (`srsue`)**: A custom-engineered dual-stack terminal process. It instantiates two concurrent lower physical, MAC, and RLC stacks (`stack_mn` on $\mathrm{DU}_1$ and `stack_sn` on $\mathrm{DU}_2$) cross-linked in memory to a single master PDCP entity via `rlc_split_bridge`.
4. **Virtual RF Bus (ZeroMQ)**: Emulates digital I/Q baseband radio interfaces over loopback TCP streams at $f_s = 23.04\text{ MHz}$ (Band 3 on `2000`/`2001`, Band 2 on `3000`/`3001`), with sample queue buffering for satellite latency emulation.

---

## 🔀 Multi-Connectivity Forwarding Modes

Forwarding behavior is controlled dynamically at the PDCP layer without interrupting established radio connections or re-attaching:

| Forwarding Mode | Ratio / Command | Description | Target Use Case |
| :--- | :---: | :--- | :--- |
| **Traffic Splitting ($1:1$)** | `1:1` | Alternates consecutive PDUs evenly between ground ($\mathrm{DU}_1$) and satellite ($\mathrm{DU}_2$). | Bandwidth aggregation & load balancing |
| **Uneven Splitting ($M:N$)** | `3:1` / `2:1` | Routes $M$ consecutive packets to $\mathrm{DU}_1$, then $N$ packets to $\mathrm{DU}_2$. | Asymmetric link capacity optimization |
| **Packet Duplication** | `dup` | Clones identical PDCP PDUs simultaneously across both terrestrial and space links. Duplicate copies are discarded by COUNT on reception. | URLLC high-reliability & zero-loss failover |
| **Pure Terrestrial Link** | `1:0` | Directs 100% of traffic through ground node $\mathrm{DU}_1$ ($0\text{ ms}$ latency). | Standard terrestrial operation |
| **Pure Satellite Link** | `0:1` | Directs 100% of traffic through satellite node $\mathrm{DU}_2$ ($7\text{ ms}$ delay). | Terrestrial outage / remote fallback |

### Live Runtime Switching
You can hot-switch the multi-connectivity policy at runtime on the very next packet by writing to the IPC control file:
```bash
# Switch to Packet Duplication (URLLC)
echo "dup" > /root/internship-repo/project/pdcp_split_ratio

# Switch to Traffic Splitting (1:1)
echo "1:1" > /root/internship-repo/project/pdcp_split_ratio

# Switch to Pure Satellite fallback (0:1)
echo "0:1" > /root/internship-repo/project/pdcp_split_ratio

# Switch back to Pure Terrestrial (1:0)
echo "1:0" > /root/internship-repo/project/pdcp_split_ratio
```
The internal switching time is less than $1\text{ ms}$ ($50\text{--}150\ \mu\text{s}$ CPU time) with zero packet drops because both radio paths remain physically synchronized and attached.

---

## 💻 System Prerequisites

* **Operating System**: Linux Ubuntu 22.04 or 24.04 LTS (x86_64 architecture). WSL2 on Windows 10/11 is fully supported.
* **CPU / Memory**: Multi-core processor (8+ physical cores recommended), 16 GB+ RAM.
* **Dependencies**:
  ```bash
  sudo apt update && sudo apt install -y \
      build-essential cmake libfftw3-dev libmbedtls-dev \
      libboost-program-options-dev libboost-thread-dev libconfig++-dev \
      libsctp-dev libzmq3-dev net-tools iproute2 iptables curl wget \
      software-properties-common python3 python3-pip iperf3
  ```

---

## 🚀 How to Start and Run Everything

### Method 1: Interactive Simulation Studio (Recommended for Live Demos & Videos)

An all-in-one terminal dashboard providing real-time ASCII telemetry (instantaneous DL/UL throughput, RTT, jitter, packet loss, CPU utilization) and live keyboard hot-keys:

```bash
cd /root/internship-repo/project
sudo ./run_interactive.sh
```

**Interactive Hot-Keys:**
* `[s]` : Switch live to **Traffic Splitting (`1:1`)**
* `[d]` : Switch live to **Packet Duplication (`dup`)**
* `[t]` : Switch live to **Pure Terrestrial (`1:0`)**
* `[n]` : Switch live to **Pure Satellite (`0:1`)**
* `[p]` : Execute 10-packet **ICMP Ping test** to UPF
* `[b]` : Trigger **5 MB HTTP Bulk Download** benchmark
* `[u]` : Trigger **5 MB HTTP POST Uplink Burst** benchmark
* `[c]` : Run **UDP Constant Bitrate (CBR)** stress test
* `[q]` : Cleanly exit and terminate all background processes

---

### Method 2: Automated Benchmark Suite

To execute reproducible multi-run benchmarks (ICMP ping, HTTP file transfer, HTTP streaming, and UDP CBR tests) with statistical output tables:

```bash
cd /root/internship-repo/project
sudo python3 scripts/run_mrdc_tn_ntn_benchmark.py --ratio 1:1 --samples 10
```

Results are automatically saved to `project/results/` in JSON and formatted summary tables.

---

### Method 3: Automated One-Shot Script

To boot the entire stack (Open5GS DB, CU-CP, CU-UP, DU1, DU2, and srsUE), establish the PDU session, execute a 15-packet ping verification, and exit cleanly:

```bash
cd /root/internship-repo/project
chmod +x run_simulation.sh
./run_simulation.sh
```

---

### Method 4: Manual Multi-Terminal CLI Execution (Step-by-Step)

If you need to observe individual layer logs in separate terminals, follow this strict execution sequence:

#### Terminal 1: Core Network (Open5GS) & TUN Routing
Ensure the Open5GS AMF and UPF are running, and set up the IP routing bridge:
```bash
# Verify services
sudo systemctl restart open5gs-amfd open5gs-upfd

# Create TUN device if not already present
sudo ip tuntap add name ogstun mode tun 2>/dev/null || true
sudo ip addr add 10.45.0.1/16 dev ogstun 2>/dev/null || true
sudo ip link set ogstun up
sudo iptables -t nat -A POSTROUTING -s 10.45.0.0/16 ! -o ogstun -j MASQUERADE

# Watch Core AMF signaling log
tail -f /var/log/open5gs/amf.log
```

#### Terminal 2: Register Subscribers in Database
Inject the IMSI records for both the Primary ($\text{DU}_1$) and Secondary ($\text{DU}_2$) legs:
```bash
cd /root/internship-repo
sudo ./open5gs-dbctl add 999700123456780 00112233445566778899aabbccddeeff 63BFA50EE6523365FF14C1F45F88737D
sudo ./open5gs-dbctl add 999700123456781 00112233445566778899aabbccddeeff 63BFA50EE6523365FF14C1F45F88737D
```

#### Terminal 3: Launch CU-CP (Control Plane)
```bash
sudo /root/internship-repo/project/ocudu/build/apps/cu_cp/ocucp \
    -c /root/internship-repo/project/scenarios/mrdc_tn_ntn_20mhz/cu_cp.yml
```
*Wait until you see: `F1AP and E1AP services initialized`.*

#### Terminal 4: Launch CU-UP (User Plane)
```bash
sudo /root/internship-repo/project/ocudu/build/apps/cu_up/ocuup \
    -c /root/internship-repo/project/scenarios/mrdc_tn_ntn_20mhz/cu_up.yml
```

#### Terminal 5: Launch $\mathrm{DU}_1$ (Terrestrial Band 3)
```bash
sudo /root/internship-repo/project/ocudu/build/apps/du/odu \
    -c /root/internship-repo/project/scenarios/mrdc_tn_ntn_20mhz/du1.yml --gnb_du_id 1
```

#### Terminal 6: Launch $\mathrm{DU}_2$ (Satellite Band 2, 7 ms Delay)
```bash
sudo /root/internship-repo/project/ocudu/build/apps/du/odu \
    -c /root/internship-repo/project/scenarios/mrdc_tn_ntn_20mhz/du2.yml --gnb_du_id 2
```

#### Terminal 7: Launch Monolithic Dual-Carrier srsUE
```bash
sudo ip netns add ue_mn 2>/dev/null || true
sudo ip netns exec ue_mn ip link set lo up

sudo PDCP_SPLIT_RATIO=1:1 \
     SRSUE_SN_CONFIG=/root/internship-repo/project/scenarios/mrdc_tn_ntn_20mhz/ue_sn.conf \
     /root/internship-repo/project/srsRAN_4G/build/srsue/src/srsue \
     /root/internship-repo/project/scenarios/mrdc_tn_ntn_20mhz/ue_mn.conf
```
*Wait until you see: `Monolithic Stack: Linked SN RLC directly to MN PDCP via C++ pointers` followed by `PDU Session Establishment successful. IP: 10.45.0.X`.*

#### Terminal 8: User-Plane Data Testing
```bash
# Test ICMP ping across the multi-connectivity tunnel
sudo ip netns exec ue_mn ping 10.45.0.1 -c 10

# Test iperf3 throughput (Start server on host first: iperf3 -s -D)
sudo ip netns exec ue_mn iperf3 -c 10.45.0.1 -t 10
```

---

## 🧹 Complete Environment Cleanup

When switching scenarios or resolving frozen processes, always run the master cleanup script:
```bash
sudo /root/internship-repo/project/scripts/cleanup.sh
```

---

## 🛠️ Troubleshooting & Known Bugs Guide

### 1. ZeroMQ Port Conflicts / Address Already in Use (`EADDRINUSE`)
* **Symptom**: `odu` or `srsue` fails at startup with:
  `Assertion 'rc == 0' failed: Address already in use (ZMQ error 98)`.
* **Root Cause**: A previous simulation process crashed or was terminated with `Ctrl+C` without closing background threads, leaving ZeroMQ sockets bound to TCP ports `2000`, `2001`, `3000`, or `3001`.
* **Solution**:
  ```bash
  sudo pkill -9 -f "ocucp|ocuup|odu|srsue|iperf3"
  sleep 1
  # Verify ports are clear:
  ss -tuln | grep -E '2000|2001|3000|3001'
  ```

---

### 2. Network Namespace Conflicts (`RTNETLINK answers: File exists`)
* **Symptom**: `sudo ip netns add ue_mn` fails, or `srsue` cannot bind `tun_srsue`.
* **Root Cause**: Stale network namespace records persist in `/var/run/netns/` after abrupt process termination.
* **Solution**:
  ```bash
  sudo ip netns del ue_mn 2>/dev/null || true
  sudo ip netns del ue_sn 2>/dev/null || true
  sudo ip netns add ue_mn
  sudo ip netns exec ue_mn ip link set lo up
  ```

---

### 3. Subscriber Authentication Rejection (`5GMM Cause: 0x03 - Illegal UE`)
* **Symptom**: UE logs report `NAS 5GMM Registration Reject: Illegal UE`, and Open5GS AMF logs state `[amf] WARNING: Unknown IMSI`.
* **Root Cause**: The subscriber entries for the primary IMSI (`999700123456780`) or secondary IMSI (`999700123456781`) were wiped or missing in the MongoDB database.
* **Solution**: Re-inject the credentials into Open5GS:
  ```bash
  cd /root/internship-repo
  sudo ./open5gs-dbctl add 999700123456780 00112233445566778899aabbccddeeff 63BFA50EE6523365FF14C1F45F88737D
  sudo ./open5gs-dbctl add 999700123456781 00112233445566778899aabbccddeeff 63BFA50EE6523365FF14C1F45F88737D
  ```

---

### 4. Space Link Stop-and-Wait HARQ Buffer Freezing
* **Symptom**: When routing traffic through $\mathrm{DU}_2$ (satellite leg), uplink or downlink collapses to $0\text{ Mbps}$ with continuous timeout logs.
* **Root Cause**: Standard 3GPP MAC Stop-and-Wait HARQ processes have a fixed round-trip timeout. In high-delay NTN environments ($14\text{ ms}$ RTT for LEO, $540\text{ ms}$ for GEO), the transmitter exhausts its HARQ processes before the first ACK/NACK returns, completely stalling the transmission window.
* **Solution**: Verify that MAC HARQ retransmissions are disabled on $\mathrm{DU}_2$ in `du2.yml`:
  ```yaml
  pdsch:
    max_nof_harq_retxs: 0
  pusch:
    max_nof_harq_retxs: 0
  prach:
    max_msg3_harq_retx: 0
  ```
  Unacknowledged transmission at MAC is compensated by RLC AM and PDCP reordering recovery at higher layers.

---

### 5. RRC Connection Setup Timeout on Satellite Link
* **Symptom**: During initial attach on $\mathrm{DU}_2$, the gNodeB logs `RRC procedure guard timer expired` and drops the RRC connection.
* **Root Cause**: The default 3GPP RRC procedure guard timer ($2\text{ s}$) expires before the satellite-delayed `RRCSetupComplete` message traverses the high-latency link.
* **Solution**: In `cu_cp.yml`, ensure the RRC procedure guard timer is extended:
  ```yaml
  cu_cp:
    rrc:
      rrc_procedure_guard_time_ms: 12800  # 12.8 seconds
  ```

---

### 6. Out-of-Order Packet Drops During Split Mode ($1:1$)
* **Symptom**: When switching from pure terrestrial (`1:0`) to split mode (`1:1`), TCP transfers suffer severe throughput collapse or packet loss.
* **Root Cause**: The $7\text{ ms}$ delay skew between terrestrial $\mathrm{DU}_1$ and satellite $\mathrm{DU}_2$ causes ground packets to arrive ahead of satellite packets. If the PDCP $t_{\text{reordering}}$ timer is too small (e.g., standard $10\text{--}20\text{ ms}$), the receiver prematurely delivers packets out of order, triggering TCP Fast Retransmit.
* **Solution**: Ensure `t_reordering` is configured to at least $100\text{ ms}$ in `cu_cp.yml`:
  ```yaml
  qos:
    - five_qi: 9
      pdcp:
        rx:
          t_reordering: 100
  ```

---

### 7. Terminal TTY Glitch / Staircase Effect
* **Symptom**: After stopping `interactive_runner.py` with `Ctrl+C`, bash output exhibits a broken "staircase" indent effect.
* **Root Cause**: The terminal raw-mode flags were not fully restored on abrupt termination.
* **Solution**: Type `stty sane` and press Enter:
  ```bash
  stty sane
  ```

---

## 📁 Repository Directory Structure

```
├── Adaptive Cross-Layer Recovery.../  # IEEE research paper LaTeX source & figures
├── generate_architecture_diagram.py   # Script to generate TikZ/PNG architecture diagram
├── generate_uml_diagram.py           # Standardized UML 2.0 class diagram generator
├── open5gs-dbctl                     # Open5GS MongoDB subscriber injection CLI
├── project/
│   ├── docs/                         # In-depth architectural guides & manuals
│   │   ├── HOWTO_RUN_TESTS.md        # Protocol testing manual
│   │   ├── INTERACTIVE_SIMULATION_GUIDE.md  # Video presentation & CLI studio guide
│   │   ├── NTN_GEO_MRDC_GUIDE.md     # GEO & LEO satellite configuration guide
│   │   └── SCENARIOS_AND_TESTING_GUIDE.md   # Benchmark scenarios documentation
│   ├── ocudu/                        # 3GPP Rel-17 Disaggregated gNodeB (CU-CP, CU-UP, DU)
│   ├── pdcp_split_ratio              # Live runtime IPC control file (1:1, dup, 1:0, 0:1)
│   ├── results/                      # Empirical benchmark results & JSON traces
│   ├── run_interactive.sh            # Launch script for the interactive simulation HUD
│   ├── run_simulation.sh             # Launch script for automated end-to-end simulation
│   ├── scenarios/
│   │   ├── mrdc_tn_ntn_20mhz/        # Primary Band 3 (TN) + Band 2 (NTN) scenario configs
│   │   ├── scenario0_cug_d1g_d2g/    # Dual ground DUs baseline
│   │   ├── scenario1_cug_d1g_d2l/    # Ground CU + Ground DU1 + LEO DU2
│   │   └── single_tn_20mhz/          # Single-carrier terrestrial baseline
│   ├── scripts/
│   │   ├── cleanup.sh                # Master process and namespace cleanup utility
│   │   ├── dc_test_sender.py         # UDP traffic generator for split/duplication testing
│   │   ├── interactive_runner.py     # Real-time ASCII telemetry HUD & demo controller
│   │   ├── ran_resource_monitor.py   # Multi-core CPU & memory consumption tracker
│   │   ├── run_mrdc_tn_ntn_benchmark.py # Automated statistical benchmark orchestrator
│   │   ├── test_dc_pdcp_stack.py     # Standalone unit test suite for PDCP reordering/dup
│   │   └── ue_benchmark_client.py    # Nanosecond latency, throughput, and jitter client
│   ├── srsRAN_4G/                    # Modified monolithic dual-stack srsUE codebase
│   │   ├── lib/include/srsran/upper/pdcp.h # rlc_split_bridge & dynamic switching C++ logic
│   │   └── srsue/src/main.cc         # Cross-stack pointer linking initialization
│   └── web_server/                   # Local HTTP/UDP benchmark server (10.45.0.1:8080)
└── readme.md                         # Main repository README
```

---

## 📜 Citation & License

This project integrates software released under open-source licenses:
- `oCUDU`: BSD-3-Clause-Open-MPI / Software Radio Systems Limited
- `srsRAN_4G`: AGPLv3
- `Open5GS`: AGPLv3

For academic citations regarding the adaptive cross-layer recovery mechanisms, refer to:
> *"Adaptive Cross-Layer Recovery for PDCP Split Bearers in Space-Terrestrial Multi-Connectivity"*, 2026.