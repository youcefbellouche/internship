# 3GPP Release 17 NTN GEO Multi-Connectivity (MR-DC) Comprehensive Manual

This manual provides complete documentation of the 5G Standalone Multi-Radio Dual Connectivity (MR-DC) testbed integrating a **Terrestrial Master Node (DU1)** and a **Geostationary Satellite (GEO NTN) Secondary Node (DU2)** over virtual ZeroMQ RF loopbacks.

---

## Table of Contents
1. [Architecture Overview](#1-architecture-overview)
2. [Configuration Files & Parameter Customization](#2-configuration-files--parameter-customization)
   - [endc_du2_geo.yml (GEO Satellite Node)](#21-endc_du2_geoyml-geo-satellite-node)
   - [endc_cu_cp_geo.yml (Control Plane Node)](#22-endc_cu_cp_geoyml-control-plane-node)
   - [endc_du1.yml (Terrestrial Node)](#23-endc_du1yml-terrestrial-node)
   - [endc_cu_up.yml (User Plane Node)](#24-endc_cu_upyml-user-plane-node)
   - [ue_mn.conf & ue_sn.conf (Multi-Connectivity UE Stack)](#25-ue_mnconf--ue_snconf-multi-connectivity-ue-stack)
3. [Execution Method 1: Manual Multi-Terminal CLI (Interactive)](#3-execution-method-1-manual-multi-terminal-cli-interactive)
4. [Execution Method 2: Automated Scripting](#4-execution-method-2-automated-scripting)
5. [Testing & Traffic Verification](#5-testing--traffic-verification)
   - [Testing WITHOUT Python Scripts (Pure Linux Networking)](#51-testing-without-python-scripts-pure-linux-networking)
   - [Testing WITH Python Scripts](#52-testing-with-python-scripts)
6. [Troubleshooting & Common Gotchas](#6-troubleshooting--common-gotchas)

---

## 1. Architecture Overview

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
  |    DU1 (Terrestrial)  |                                       |   DU2 (GEO Satellite) |
  |  - ZeroMQ 2000/2001   |                                       |  - ZeroMQ 3000/3001   |
  |  - Latency: ~0 ms     |                                       |  - Latency: 120 ms    |
  |  - Standard SIB1      |                                       |  - SIB19 + koffset=150|
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

* **Core Network**: Open5GS provides the 5G Core functions. User plane traffic enters through the kernel TUN interface `ogstun` (`10.45.0.1`).
* **Central Unit (CU)**: Splits into CU-CP (Control Plane running RRC and E1AP/F1AP) and CU-UP (User Plane running SDAP, PDCP, and GTP-U).
* **Distributed Units (DUs)**:
  * **DU1 (ID 1)**: Emulates a terrestrial gNodeB cell (`PCI=1`, latency $\approx 0\text{ ms}$).
  * **DU2 (ID 2)**: Emulates a 3GPP Release 17 NTN geostationary satellite orbit cell (`PCI=2`, one-way propagation delay $= 120\text{ ms}$).
* **User Equipment (UE)**: A custom monolithic dual-carrier srsRAN instance. It anchors two independent lower physical/MAC/RLC stacks to a single unified PDCP entity with configurable traffic splitting and duplicate discarding.

---

## 2. Configuration Files & Parameter Customization

### 2.1 `endc_du2_geo.yml` (GEO Satellite Node)
File location: [`project/ocudu/configs/endc_du2_geo.yml`](file:///root/internship-repo/project/ocudu/configs/endc_du2_geo.yml)

This file controls the secondary DU acting as the geostationary satellite cell.

```yaml
gnb_du_id: 2
f1ap:
  addrs: 127.0.10.1
  bind_addrs: 127.0.10.3
f1u:
  socket:
    - bind_addr: 127.0.10.3
ru_sdr:
  device_driver: zmq
  device_args: tx_port=tcp://127.0.0.1:3000,rx_port=tcp://127.0.0.1:3001,base_srate=11.52e6,rx_offset=1382400
  srate: 11.52
cell_cfg:
  sector_id: 2
  dl_arfcn: 368500
  band: 3
  channel_bandwidth_MHz: 10
  common_scs: 15
  plmn: "99970"
  tac: 1
  pci: 2
  ntn:
    cell_specific_koffset: 150
    epoch_timestamp: "2026-01-01T00:00:00"
    ta_info:
      ta_common: 0
    ephemeris_info_ecef:
      pos_x: 20922195
      pos_y: 1967783
      pos_z: 19770302
      vel_x: 0
      vel_y: 0
      vel_z: 0
  sib:
    si_window_length: 5
    si_sched_info:
      - si_period: 16
        sib_mapping: [2]
      - si_period: 16
        sib_mapping: [19]
        si_window_position: 2
    sib2:
      q_hyst: 3
      thresh_serving_low_p: 0
      cell_reselection_priority: 6
      q_rx_lev_min: -70
      s_intra_search_p: 62
      t_reselection_nr: 1
  pucch:
    sr_period_ms: 320
  csi:
    csi_rs_period: 80
  pdcch:
    common:
      ss0_index: 0
      coreset0_index: 6
    dedicated:
      ss2_type: common
      dci_format_0_1_and_1_1: false
  prach:
    prach_config_index: 1
    total_nof_ra_preambles: 64
    nof_ssb_per_ro: 1
    nof_cb_preambles_per_ssb: 64
    max_msg3_harq_retx: 0
  pdsch:
    mcs_table: qam64
    max_nof_harq_retxs: 0
  pusch:
    mcs_table: qam64
log:
  filename: /tmp/endc_du2.log
  all_level: debug
```

#### What can be changed and how to deal with it:
1. **Propagation Delay (`ru_sdr.device_args: rx_offset`)**:
   - The sample offset emulates the physical distance travel time:
     $$\text{rx\_offset} = \text{delay (seconds)} \times \text{sampling\_rate (Hz)}$$
   - For GEO (altitude $\approx 35,786\text{ km}$), delay $\approx 120\text{ ms}$:
     $$0.120\text{ s} \times 11.52\times 10^6\text{ Hz} = \mathbf{1,382,400\text{ samples}}$$
   - If you want to simulate a **LEO satellite (10 ms delay)**:
     $$0.010\text{ s} \times 11.52\times 10^6\text{ Hz} = \mathbf{115,200\text{ samples}}$$
   - Change `rx_offset=1382400` in `device_args` accordingly.
2. **Scheduling Offset (`cell_specific_koffset: 150`)**:
   - In 3GPP NTN, `cell_specific_koffset` extends slot timing (K0, K1, K2 offsets) to account for the long round-trip propagation time and avoid scheduling collisions. Keep this set to `150` for GEO delays.
3. **Satellite Ephemeris & Epoch (`epoch_timestamp` and `ephemeris_info_ecef`)**:
   - `epoch_timestamp: "2026-01-01T00:00:00"` provides the reference epoch for orbital propagation.
   - `pos_x`, `pos_y`, `pos_z` represent the Earth-Centered Earth-Fixed (ECEF) coordinates of the satellite in meters.
   - `vel_x`, `vel_y`, `vel_z` represent satellite velocity in m/s (set to 0 for geostationary orbit).
4. **HARQ Deactivation (`max_nof_harq_retxs: 0`)**:
   - Due to the ~250 ms RTT of satellite links, MAC-layer HARQ stop-and-wait retransmissions waste capacity and stall buffers. HARQ retransmissions are disabled in both `pdsch` and `prach`; error recovery is handled by RLC AM.
5. **SIB Scheduling Rules (3GPP Rel-17 requirement)**:
   - SIB19 must be scheduled in `si_sched_info` with an explicit `si_window_position: 2`.
   - SIB19 requires at least one SIB with ID $< 15$ (such as SIB2) to be scheduled before it, along with its `sib2:` configuration section.

---

### 2.2 `endc_cu_cp_geo.yml` (Control Plane Node)
File location: [`project/ocudu/configs/endc_cu_cp_geo.yml`](file:///root/internship-repo/project/ocudu/configs/endc_cu_cp_geo.yml)

```yaml
cu_cp:
  rrc:
    rrc_procedure_guard_time_ms: 12800
  inactivity_timer: 7200
  amf:
    addrs: 127.0.0.5
    bind_addrs: 127.0.0.1
    supported_tracking_areas:
      - tac: 1
        plmn_list:
          - plmn: "99970"
            tai_slice_support_list:
              - sst: 1
  e1ap:
    bind_addrs: 127.0.20.1
  f1ap:
    bind_addrs: 127.0.10.1
log:
  filename: /tmp/endc_cu_cp.log
  all_level: debug
```

#### What can be changed and how to deal with it:
1. **`rrc_procedure_guard_time_ms: 12800`**:
   - Sets the guard timer for RRC procedures to 12.8 seconds. This is critical for NTN because standard terrestrial timers (500 ms) would timeout during satellite handshakes.
2. **`inactivity_timer: 7200`**:
   - Configures the inactivity timer before the gNB tears down the DRB user-plane session. The default value is `120` seconds (2 minutes). Setting it to `7200` (2 hours) ensures the connection remains active while you perform manual terminal testing.

---

### 2.3 `endc_du1.yml` (Terrestrial Node)
File location: [`project/ocudu/configs/endc_du1.yml`](file:///root/internship-repo/project/ocudu/configs/endc_du1.yml)

Operates on ZMQ ports `2000/2001`, `PCI=1`, `gnb_du_id=1` with standard zero-delay parameters.

---

### 2.4 `endc_cu_up.yml` (User Plane Node)
File location: [`project/ocudu/configs/endc_cu_up.yml`](file:///root/internship-repo/project/ocudu/configs/endc_cu_up.yml)

Manages the SDAP/PDCP user plane and bridges F1-U (`127.0.10.1`) with the N3 GTP-U core interface (`127.0.0.1`).

---

### 2.5 `ue_mn.conf` & `ue_sn.conf` (Multi-Connectivity UE Stack)
* **Master Leg (`project/ue_mn.conf`)**:
  - Connects to DU1 (ZMQ `tx_port=tcp://127.0.0.1:2001,rx_port=tcp://127.0.0.1:2000`).
  - Sets up the Linux network namespace and tunnel device:
    ```ini
    [gw]
    netns = ue_mn
    ip_devname = tun_srsue
    ```
* **Secondary Leg (`project/ue_sn.conf`)**:
  - Connects to DU2 (ZMQ `tx_port=tcp://127.0.0.1:3001,rx_port=tcp://127.0.0.1:3000`).
* **Traffic Split Ratio (`PDCP_SPLIT_RATIO`)**:
  - Defined in the terminal environment before launching the UE:
    ```bash
    export PDCP_SPLIT_RATIO="2:7"
    ```
  - For every $2+7=9$ packets, 2 are sent via DU1 (terrestrial) and 7 are sent via DU2 (satellite).
  - To test equal splitting, use `export PDCP_SPLIT_RATIO="1:1"`.

---

## 3. Execution Method 1: Manual Multi-Terminal CLI (Interactive)

> **Important Note**: Manual interactive testing requires **7 separate terminal windows or tabs**. Each node must remain running in its own terminal to observe live log outputs.

### Pre-Flight Setup (Main Terminal)
Run this once to configure subscribers, create namespaces, and ensure clean ports:
```bash
# Register subscribers in Open5GS DB
sudo /root/internship-repo/open5gs-dbctl add 999700123456780 00112233445566778899aabbccddeeff 63BFA50EE6523365FF14C1F45F88737D || true
sudo /root/internship-repo/open5gs-dbctl add 999700123456781 00112233445566778899aabbccddeeff 63BFA50EE6523365FF14C1F45F88737D || true

# Create network namespaces
sudo ip netns add ue_mn || true
sudo ip netns exec ue_mn ip link set lo up || true
sudo ip netns add ue_sn || true
sudo ip netns exec ue_sn ip link set lo up || true

# Kill any lingering instances
sudo pkill -9 -f ocucp || true
sudo pkill -9 -f ocuup || true
sudo pkill -9 -f odu || true
sudo pkill -9 -f srsue || true
```

---

### Step-by-Step Terminal Execution Order

#### **Terminal 1: Start CU-CP**
```bash
sudo /root/internship-repo/project/ocudu/build/apps/cu_cp/ocucp \
  -c /root/internship-repo/project/ocudu/configs/endc_cu_cp_geo.yml
```

#### **Terminal 2: Start CU-UP**
*(Wait 2 seconds after Terminal 1)*
```bash
sudo /root/internship-repo/project/ocudu/build/apps/cu_up/ocuup \
  -c /root/internship-repo/project/ocudu/configs/endc_cu_up.yml
```

#### **Terminal 3: Start DU1 (Terrestrial Node)**
*(Wait 1 second after Terminal 2)*
```bash
sudo /root/internship-repo/project/ocudu/build/apps/du/odu \
  -c /root/internship-repo/project/ocudu/configs/endc_du1.yml \
  --gnb_du_id 1
```

#### **Terminal 4: Start DU2 (GEO Satellite Node)**
*(Wait 3 seconds after Terminal 3)*
```bash
sudo /root/internship-repo/project/ocudu/build/apps/du/odu \
  -c /root/internship-repo/project/ocudu/configs/endc_du2_geo.yml \
  --gnb_du_id 2
```

#### **Terminal 5: Start Dual-Stack srsRAN UE**
*(Wait 5 seconds after Terminal 4)*
```bash
export PDCP_SPLIT_RATIO="2:7"
sudo SRSUE_SN_CONFIG=/root/internship-repo/project/ue_sn.conf \
     PDCP_SPLIT_RATIO="$PDCP_SPLIT_RATIO" \
     /root/internship-repo/project/srsRAN_4G/build/srsue/src/srsue \
     /root/internship-repo/project/ue_mn.conf
```

Wait until Terminal 5 outputs:
`PDU Session Establishment successful. IP: 10.45.0.X`

---

#### **Terminal 6: Check Active UE IP & Start Packet Listener**
First, check which IP address was assigned to the UE:
```bash
UE_IP=$(sudo ip netns exec ue_mn ip -4 addr show dev tun_srsue | grep -oP '(?<=inet\s)\d+(\.\d+){3}')
echo "Active UE IP: $UE_IP"
```

Start the packet sniffer on port 5001:
```bash
sudo ip netns exec ue_mn tcpdump -i tun_srsue -n -A 'udp port 5001'
```

#### **Terminal 7: Traffic Injection**
Proceed to [Section 5](#5-testing--traffic-verification) to send packets and watch them arrive in Terminal 6.

---

## 4. Execution Method 2: Automated Scripting

If you prefer to run the entire stack automatically from a **single terminal window**, you can use the automated test runner scripts.

### Option A: Background Bash Launcher
Starts all background processes and validates connection automatically:
```bash
cd /root/internship-repo/project
chmod +x run_simulation.sh
./run_simulation.sh
```

### Option B: NTN GEO Multi-Connectivity Python Runner
Runs the dedicated NTN simulation orchestrator with dynamic delay parameters:
```bash
# Run MR-DC mode with 120 ms GEO propagation delay
python3 /root/internship-repo/project/run_ntn_geo_mrdc.py --mode mrdc --delay_ms 120.0

# Run Single-Connectivity GEO mode (single satellite DU)
python3 /root/internship-repo/project/run_ntn_geo_mrdc.py --mode single --delay_ms 120.0
```

---

## 5. Testing & Traffic Verification

### 5.1 Testing WITHOUT Python Scripts (Pure Linux Networking)

All tests can be performed directly using native Linux CLI tools (`ping`, `bash /dev/udp`, `tcpdump`):

#### Test 1: Round-Trip Latency Verification (Ping)
Because GEO packets have an RTT of $\approx 257\text{ ms}$, use `-W 2` (2-second response timeout) so satellite packets are not dropped:
```bash
sudo ip netns exec ue_mn ping 10.45.0.1 -c 10 -W 2
```
* **Observation**: You will see dual-path latency in the output:
  * Packets over DU1 return in **~21 ms**.
  * Packets over DU2 return in **~257 ms** ($120\text{ ms}\times 2 + \text{processing}$).

#### Test 2: Sequential Packet Splitting (Pure Bash)
Send 8 numbered UDP packets into the core network:
```bash
UE_IP=$(sudo ip netns exec ue_mn ip -4 addr show dev tun_srsue | grep -oP '(?<=inet\s)\d+(\.\d+){3}')

for seq in {1..8}; do
  echo "MANUAL_SPLIT_PACKET_#$seq" > /dev/udp/$UE_IP/5001
  echo "Sent Packet #$seq"
  sleep 0.1
done
```
* **Observation**: Watch Terminal 6 (`tcpdump`). You will see all 8 packets arrive.

#### Test 3: Native C++ PDCP Layer Verification
Execute the native compiled srsRAN unit test binary (zero Python required):
```bash
/root/internship-repo/project/srsRAN_4G/build/lib/test/pdcp/pdcp_nr_test_rx
```
* **Observation**: Confirms `t-Reordering` timer expiration, out-of-order queue buffering, and duplicate PDU discarding.

---

### 5.2 Testing WITH Python Scripts

#### Test 1: Split Bearer Test ([`dc_test_sender.py`](file:///root/internship-repo/project/dc_test_sender.py))
Sends 8 tagged UDP packets with sequence numbers:
```bash
UE_IP=$(sudo ip netns exec ue_mn ip -4 addr show dev tun_srsue | grep -oP '(?<=inet\s)\d+(\.\d+){3}')
python3 /root/internship-repo/project/dc_test_sender.py --ip $UE_IP --port 5001 --test split
```

#### Test 2: Packet Duplication Test ([`dc_test_sender.py`](file:///root/internship-repo/project/dc_test_sender.py))
Sends 4 duplicated packets across both legs:
```bash
UE_IP=$(sudo ip netns exec ue_mn ip -4 addr show dev tun_srsue | grep -oP '(?<=inet\s)\d+(\.\d+){3}')
python3 /root/internship-repo/project/dc_test_sender.py --ip $UE_IP --port 5001 --test duplication
```

#### Test 3: Standalone Protocol Stack Test ([`test_dc_pdcp_stack.py`](file:///root/internship-repo/project/test_dc_pdcp_stack.py))
Tests the Python-based PDCP state machine and ratio parsing:
```bash
python3 /root/internship-repo/project/test_dc_pdcp_stack.py -v
```

---

## 6. Troubleshooting & Common Gotchas

### Gotcha 1: Dynamic IP Address Allocation
* **Symptom**: `tcpdump` captures 0 packets even though the sender script completes.
* **Cause**: Open5GS SMF assigns IPs dynamically from the pool (`10.45.0.2`, `10.45.0.3`, `10.45.0.4`...). If you restart the UE, its IP may change.
* **Fix**: Always query the active IP before sending traffic:
  ```bash
  sudo ip netns exec ue_mn ip addr show dev tun_srsue
  ```

### Gotcha 2: User-Inactivity Disconnection
* **Symptom**: `ping` works right after starting the UE, but after 2 minutes of idle time, packets stop arriving.
* **Cause**: Default `inactivity_timer` in `ocudu` is 120 seconds. If no user-plane packets flow, the CU-CP sends `rrcRelease` with cause `user-inactivity`.
* **Fix**: Ensure `endc_cu_cp_geo.yml` contains `inactivity_timer: 7200`.

### Gotcha 3: SIB19 Validation Errors
* **Symptom**: `odu` exits with `The SIB19 must be configured with SI-window position`.
* **Cause**: In 3GPP Rel-17 TS 38.331, SIBs with ID $\ge 15$ require an explicit `si_window_position` and must be preceded by at least one SIB with ID $< 15$ (SIB2).
* **Fix**: Ensure `endc_du2_geo.yml` schedules SIB2 at position 1 and SIB19 at position 2.

### Gotcha 4: High Ping Packet Loss with Asymmetric Ratios
* **Symptom**: `ping 10.45.0.1` reports 60%–70% packet loss.
* **Cause**: When using an asymmetric ratio like `2:7`, 70% of packets travel over the 257 ms satellite path. Standard `ping` has a 1-second timeout and flags out-of-order satellite replies as lost.
* **Fix**: Add `-W 2` to ping (`ping 10.45.0.1 -c 10 -W 2`) or use a balanced ratio (`export PDCP_SPLIT_RATIO="1:1"`).
