# 5G MR-DC Web Server & Benchmarking Guide

This directory contains the dual-accessible HTTP web server, the live telemetry dashboard, and the benchmarking tools designed to evaluate 5G Standalone Multi-Connectivity (Ground Terrestrial + Non-Terrestrial LEO Satellite) user-plane performance.

The web server is engineered to be **simultaneously accessible** from:
1. **The Host Environment**: `http://localhost:8080` (for engineers and researchers using a local browser).
2. **The 5G User Equipment (UE)**: `http://10.45.0.1:8080` (routing actual user-plane traffic over the `tun_srsue` radio bearer interface inside the `ue_mn` network namespace).

---

## Table of Contents
1. [Architecture Overview](#1-architecture-overview)
2. [Manual Step-by-Step Setup & Launch of oCUDU and srsUE](#2-manual-step-by-step-setup--launch-of-ocudu-and-srsue)
   - [2.1 Core Services & Subscriber Provisioning](#21-core-services--subscriber-provisioning)
   - [2.2 Network Namespaces Setup](#22-network-namespaces-setup)
   - [2.3 Building oCUDU and srsRAN from Source](#23-building-ocudu-and-srsran-from-source)
   - [2.4 Terminal-by-Terminal Manual Launch Sequence](#24-terminal-by-terminal-manual-launch-sequence)
   - [2.5 Verifying the Radio Link & PDU Session](#25-verifying-the-radio-link--pdu-session)
   - [2.6 Alternative: Automated Single-Command Scenario Launch](#26-alternative-automated-single-command-scenario-launch)
3. [Running the Web Server](#3-running-the-web-server)
4. [Method 1: Running Tests via Automated Scripts (Recommended)](#4-method-1-running-tests-via-automated-scripts-recommended)
5. [Method 2: Running Tests Manually](#5-method-2-running-tests-manually)
6. [API Endpoints Reference](#6-api-endpoints-reference)
7. [Extracted Metrics & Statistical Formulas](#7-extracted-metrics--statistical-formulas)
8. [Teardown & Cleanup](#8-teardown--cleanup)
9. [Troubleshooting & FAQs](#9-troubleshooting--faqs)

---

## 1. Architecture Overview

```
                      [ Host Browser ]
                             │ (localhost:8080)
                             ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   Dual-Accessible HTTP Web Server                     │
│                           (0.0.0.0:8080)                               │
│  - Live Telemetry Dashboard & HTML5 Canvas Real-Time Chart             │
│  - File Download / Upload API with Nanosecond Timestamp Framing       │
│  - Continuous Streaming Engine & Dynamic PDCP Ratio Hot-Switcher       │
└────────────────────────────────────────────────────────────────────────┘
                             ▲
                             │ (10.45.0.1:8080 over ogstun)
┌────────────────────────────────────────────────────────────────────────┐
│                        Open5GS 5G Core (UPF)                           │
│                          Gateway: 10.45.0.1                            │
└────────────────────────────────────────────────────────────────────────┘
                             ▲
                             │ (N3 GTP-U Tunnel)
┌────────────────────────────────────────────────────────────────────────┐
│                  O-RAN CU-UP (In-Memory PDCP Delegate)                 │
│                 Dynamic Split: /tmp/pdcp_split_ratio                   │
└──────────────────┬──────────────────────────────────┬──────────────────┘
                   │ (F1-U / RLC MCG)                 │ (F1-U / RLC SCG)
                   ▼                                  ▼
         ┌───────────────────┐              ┌───────────────────┐
         │     O-RAN DU1     │              │     O-RAN DU2     │
         │  (Ground Leg / TN)│              │ (LEO Satellite/NTN│
         └─────────┬─────────┘              └─────────┬─────────┘
                   │                                  │
                   └─────────────────┬────────────────┘
                                     │ (RF / ZMQ)
                                     ▼
         ┌──────────────────────────────────────────────────────┐
         │        Monolithic Dual-Path srsUE (ue_mn namespace)  │
         │             Assigned IP: 10.45.0.x on tun_srsue      │
         └──────────────────────────────────────────────────────┘
```

The system evaluates two core workloads:
- **Workload A: Standard File Transfer (DL & UL)** – 1 MB to 10 MB payload bulk transfer evaluating throughput, transfer duration, and TCP retransmissions.
- **Workload B: Continuous Data Streaming (DL & UL)** – Sustained stream of binary frames with per-second instantaneous throughput time series and nanosecond one-way latency.

Each test is benchmarked across two operational modes:
- **Single-Connectivity (Without MR-DC, `1:0`)**: 100% terrestrial traffic via Ground DU1.
- **Multi-Connectivity (With MR-DC, `1:1`)**: In-memory PDCP delegate split and duplication across Ground DU1 (TN) and LEO Satellite DU2 (NTN).

---

## 2. Manual Step-by-Step Setup & Launch of oCUDU and srsUE

To understand or debug the individual nodes, you can set up and run each component manually in separate terminal windows (or using `tmux`/`screen`).

### 2.1 Core Services & Subscriber Provisioning

Ensure the Open5GS Core Network daemons are running:
```bash
sudo systemctl status open5gs-upfd open5gs-amfd open5gs-smfd
```
*(If stopped, start them with: `sudo systemctl start open5gs-upfd open5gs-amfd open5gs-smfd open5gs-nrfd open5gs-nssf`)*.

Provision the Master and Secondary SIM subscribers in MongoDB:
```bash
# Provision Master Subscriber (IMSI: 999700123456780)
sudo /root/internship-repo/open5gs-dbctl add 999700123456780 00112233445566778899aabbccddeeff 63BFA50EE6523365FF14C1F45F88737D

# Provision Secondary Subscriber (IMSI: 999700123456781)
sudo /root/internship-repo/open5gs-dbctl add 999700123456781 00112233445566778899aabbccddeeff 63BFA50EE6523365FF14C1F45F88737D
```

---

### 2.2 Network Namespaces Setup

Create isolated network namespaces for the dual-path UE:
```bash
sudo ip netns add ue_mn
sudo ip netns exec ue_mn ip link set lo up

sudo ip netns add ue_sn
sudo ip netns exec ue_sn ip link set lo up
```

---

### 2.3 Building oCUDU and srsRAN from Source

If you make modifications to the C++ source code in `ocudu` or `srsRAN_4G`:

#### Build `ocudu` (CU-CP, CU-UP, DU):
```bash
cd /root/internship-repo/project/ocudu
mkdir -p build && cd build
cmake .. -DCMAKE_BUILD_TYPE=RelWithDebInfo
make -j$(nproc) ocucp ocuup odu
```
Binaries will be placed in:
- `build/apps/cu_cp/ocucp`
- `build/apps/cu_up/ocuup`
- `build/apps/du/odu`

#### Build `srsRAN_4G` (Dual-Path Monolithic `srsue`):
```bash
cd /root/internship-repo/project/srsRAN_4G
mkdir -p build && cd build
cmake .. -DCMAKE_BUILD_TYPE=RelWithDebInfo
make -j$(nproc) srsue
```
Binary will be placed in:
- `build/srsue/src/srsue`

---

### 2.4 Terminal-by-Terminal Manual Launch Sequence

The launch sequence is strictly ordered: **CU-CP $\rightarrow$ CU-UP $\rightarrow$ DU1 $\rightarrow$ DU2 $\rightarrow$ srsUE**. Open separate terminal tabs for each step:

#### Terminal 1: Launch O-RAN CU Control Plane (`ocucp`)
CU-CP establishes the NGAP connection with Open5GS AMF (`127.0.0.5:38412`) and opens listening sockets for E1AP (from CU-UP) and F1AP (from DU1 and DU2):
```bash
sudo /root/internship-repo/project/ocudu/build/apps/cu_cp/ocucp \
  -c /root/internship-repo/project/scenarios/scenario1_cug_d1g_d2l/cu_cp.yml
```
*Wait ~2 seconds for CU-CP to print:*
```text
[NGAP] Connected to AMF at 127.0.0.5:38412
[E1AP] Server listening on 127.0.0.5:38462
[F1AP] Server listening on 127.0.0.5:38472
```

---

#### Terminal 2: Launch O-RAN CU User Plane (`ocuup`)
CU-UP connects to CU-CP via E1AP, binds to the Open5GS UPF via GTP-U, and initializes the in-memory PDCP delegate bridge:
```bash
sudo /root/internship-repo/project/ocudu/build/apps/cu_up/ocuup \
  -c /root/internship-repo/project/scenarios/scenario1_cug_d1g_d2l/cu_up.yml
```
*Wait ~1-2 seconds for CU-UP to print:*
```text
[E1AP] E1 Setup Request sent
[E1AP] E1 Setup Response received - SUCCESS
[GTPU] Bound to UPF interface
```

---

#### Terminal 3: Launch O-RAN DU1 (Master Cell Group / Ground Terrestrial Leg)
DU1 connects to CU-CP via F1-C, to CU-UP via F1-U, and activates the terrestrial RF carrier (ZMQ):
```bash
sudo /root/internship-repo/project/ocudu/build/apps/du/odu \
  -c /root/internship-repo/project/scenarios/scenario1_cug_d1g_d2l/du1.yml \
  --gnb_du_id 1
```
*Wait ~3 seconds for DU1 to print:*
```text
[F1AP] F1 Setup Request sent (gNB-DU ID: 1)
[F1AP] F1 Setup Response received - SUCCESS
[PHY] Radio carrier initialized on ZMQ port 2000
```

---

#### Terminal 4: Launch O-RAN DU2 (Secondary Cell Group / LEO Satellite NTN Leg)
DU2 connects to CU-CP via F1-C, to CU-UP via F1-U, and activates the satellite NTN leg configured with LEO channel delay modeling:
```bash
sudo /root/internship-repo/project/ocudu/build/apps/du/odu \
  -c /root/internship-repo/project/scenarios/scenario1_cug_d1g_d2l/du2.yml \
  --gnb_du_id 2
```
*Wait ~6-8 seconds for DU2 to print:*
```text
[F1AP] F1 Setup Request sent (gNB-DU ID: 2)
[F1AP] F1 Setup Response received - SUCCESS
[PHY] Radio carrier initialized on ZMQ port 2001
```

---

#### Terminal 5: Launch Monolithic Dual-Path srsUE
Launch the dual-carrier UE inside the host environment. The master carrier config is passed as the primary argument, and the secondary carrier config is passed via `SRSUE_SN_CONFIG`:
```bash
sudo SRSUE_SN_CONFIG=/root/internship-repo/project/ue_sn.conf \
  /root/internship-repo/project/srsRAN_4G/build/srsue/src/srsue \
  /root/internship-repo/project/ue_mn.conf
```
*Watch the UE terminal as it attaches:*
1. Physical layer synchronizes to DU1 and DU2 carriers (`PSS/SSS detected`).
2. Random Access procedure succeeds on Master Cell (`RA procedure successful`).
3. 5G NAS Authentication and Security Mode Command complete with Open5GS AMF.
4. RRC Reconfiguration adds the Secondary Cell Group (DU2) for Dual Connectivity.
5. PDU Session establishment completes:
```text
[NAS] PDU Session Establishment Accept
[IP] Interface tun_srsue created in namespace ue_mn with IP 10.45.0.x
[STATE] Connected! User plane ready.
```

---

### 2.5 Verifying the Radio Link & PDU Session

In **Terminal 6**, verify that the UE is online and can reach the 5G Core UPF gateway:

1. **Verify Interface and Assigned IP**:
   ```bash
   sudo ip netns exec ue_mn ip addr show dev tun_srsue
   ```
   *Expected output:*
   ```text
   3: tun_srsue: <POINTOPOINT,MULTICAST,NOARP,UP,LOWER_UP> mtu 1500 ...
       inet 10.45.0.3/24 scope global tun_srsue
   ```

2. **Verify ICMP Ping to UPF Gateway (10.45.0.1)**:
   ```bash
   sudo ip netns exec ue_mn ping 10.45.0.1 -c 5
   ```
   *Expected output:* `5 packets transmitted, 5 received, 0% packet loss`.

---

### 2.6 Alternative: Automated Single-Command Scenario Launch

If you prefer to start all 5 components in one command with automatic dependency timing and `--keep-alive`:
```bash
python3 /root/internship-repo/project/scripts/run_scenario.py --scenario 1 --keep-alive
```
This automatically handles database subscriber checks, namespace initialization, orderly node launching, PDU verification, and keeps all nodes running in the background.

---

## 3. Running the Web Server

Once the radio link is established, start the web server so that both the host user and the UE can interact with it.

### 3.1 Start Server in Foreground
```bash
python3 /root/internship-repo/project/web_server/server.py 8080
```

### 3.2 Start Server in Background (Daemon)
```bash
nohup python3 /root/internship-repo/project/web_server/server.py 8080 > /tmp/web_server.log 2>&1 &
```

### 3.3 Verify Server Accessibility
- **From Host Browser**: Open [http://localhost:8080](http://localhost:8080)
- **From Host CLI**:
  ```bash
  curl -s http://127.0.0.1:8080/api/status
  ```
- **From 5G UE (inside `ue_mn`)**:
  ```bash
  sudo ip netns exec ue_mn curl -s http://10.45.0.1:8080/api/status
  ```

---

## 4. Method 1: Running Tests via Automated Scripts (Recommended)

The automated orchestrator runs the entire benchmark suite without manual intervention, collects 10 samples of each workload for both Single-Connectivity and Multi-Connectivity, samples RAN CPU every 200 ms, formats an ASCII comparison matrix, and exports results to JSON and CSV.

### 4.1 Execute 10-Sample Benchmark Suite
```bash
python3 /root/internship-repo/project/scripts/run_mrdc_benchmarks.py 10
```

### 4.2 What the Script Automates:
1. **Radio Bearer Check**: Checks if `tun_srsue` is active inside `ue_mn`. If active, automatically routes traffic across the 5G radio interface via `sudo ip netns exec ue_mn` targeting `10.45.0.1:8080`.
2. **Phase 1: Single-Connectivity (`1:0` Pure Terrestrial)**:
   - Sets `/tmp/pdcp_split_ratio` to `1:0`.
   - Starts the background `RANResourceMonitor`.
   - Executes 10 samples of Workload A (File Transfer DL & UL).
   - Executes 10 samples of Workload B (Continuous Data Streaming DL & UL).
   - Stops the monitor and computes Single-Connectivity RAN CPU stats.
3. **Phase 2: Multi-Connectivity (`1:1` TN + NTN Split/Duplication)**:
   - Sets `/tmp/pdcp_split_ratio` to `1:1`.
   - Starts the background `RANResourceMonitor`.
   - Executes 10 samples of Workload A (File Transfer DL & UL).
   - Executes 10 samples of Workload B (Continuous Data Streaming DL & UL).
   - Stops the monitor and computes Multi-Connectivity RAN CPU stats.
4. **Statistical Aggregation**:
   - Calculates Mean, Standard Deviation, Min, Max, and 95th Percentile (p95) for all metrics.
   - Calculates normalized and total RAN CPU utilization and the delta overhead.
5. **Output Generation**:
   - Saves complete JSON summary to: `project/results/benchmark_summary.json`
   - Saves CSV matrix to: `project/results/benchmark_summary.csv`
   - Updates the live web dashboard history table and charts in real time.

---

## 5. Method 2: Running Tests Manually

You can also run individual workloads or manual HTTP transfers on demand.

### 5.1 Using the Dedicated UE Benchmark Client (`ue_benchmark_client.py`)

The benchmark client embeds nanosecond timestamps into binary frame headers (`!QQ` format: Sequence number + TX nanoseconds) and queries Linux kernel socket stats via `getsockopt(SOL_TCP, TCP_INFO)`.

#### Run a Single File Transfer (DL & UL):
```bash
sudo ip netns exec ue_mn python3 /root/internship-repo/project/scripts/ue_benchmark_client.py \
    --server 10.45.0.1 \
    --port 8080 \
    --test file \
    --samples 1 \
    --size-mb 1.0 \
    --mode-label "Manual-Test"
```

#### Run a Continuous Streaming Test (3 Seconds DL & UL):
```bash
sudo ip netns exec ue_mn python3 /root/internship-repo/project/scripts/ue_benchmark_client.py \
    --server 10.45.0.1 \
    --port 8080 \
    --test stream \
    --samples 1 \
    --duration 3 \
    --mode-label "Manual-Test"
```

#### Run Both Tests with Multiple Iterations:
```bash
sudo ip netns exec ue_mn python3 /root/internship-repo/project/scripts/ue_benchmark_client.py \
    --server 10.45.0.1 \
    --port 8080 \
    --test all \
    --samples 5 \
    --size-mb 1.0 \
    --duration 3 \
    --mode-label "Multi-Conn-Batch"
```

---

### 5.2 Dynamic Live Hot-Switching (Without Restarting Nodes)

You can switch the PDCP split policy at any time during active traffic:

- **Switch to Pure Terrestrial (Single-Connectivity `1:0`)**:
  ```bash
  echo "1:0" > /tmp/pdcp_split_ratio
  ```
  *Or via HTTP API:*
  ```bash
  curl -s -X POST http://127.0.0.1:8080/api/set_mode -d '{"ratio": "1:0"}'
  ```

- **Switch to Multi-Connectivity Split/Duplication (`1:1` TN + NTN)**:
  ```bash
  echo "1:1" > /tmp/pdcp_split_ratio
  ```
  *Or via HTTP API:*
  ```bash
  curl -s -X POST http://127.0.0.1:8080/api/set_mode -d '{"ratio": "1:1"}'
  ```

- **Switch to Pure Satellite (NTN Only `0:1`)**:
  ```bash
  echo "0:1" > /tmp/pdcp_split_ratio
  ```
  *Or via HTTP API:*
  ```bash
  curl -s -X POST http://127.0.0.1:8080/api/set_mode -d '{"ratio": "0:1"}'
  ```

---

### 5.3 Manual Testing via Standard Tools (`curl`, `dd`, `ping`)

#### Test ICMP Round-Trip Latency and Packet Loss:
```bash
sudo ip netns exec ue_mn ping 10.45.0.1 -c 10
```

#### Test Downlink Throughput via `curl`:
```bash
sudo ip netns exec ue_mn curl -o /dev/null -s -w \
  "Time: %{time_total}s | Speed: %{speed_download} B/s | Size: %{size_download} bytes\n" \
  http://10.45.0.1:8080/api/download?size_mb=1
```

#### Test Uplink Throughput via `curl`:
```bash
# Generate 1 MB random payload
dd if=/dev/urandom of=/tmp/upload_test.bin bs=1M count=1 2>/dev/null

# Upload to server
sudo ip netns exec ue_mn curl -s -X POST \
  --data-binary @/tmp/upload_test.bin \
  -H "Content-Type: application/octet-stream" \
  http://10.45.0.1:8080/api/upload
```

---

### 5.4 Manual RAN Resource Profiling

To measure the CPU usage of all active RAN components (`srsue`, `ocucp`, `ocuup`, `odu`):
```bash
python3 /root/internship-repo/project/scripts/ran_resource_monitor.py 5
```
*(Runs for 5 seconds and prints a JSON summary of average and peak CPU for each component).*

---

## 6. API Endpoints Reference

| Method | Endpoint | Description | Query / Body Parameters |
| :--- | :--- | :--- | :--- |
| `GET` | `/` | Web Dashboard UI | None |
| `GET` | `/api/status` | Server status, active ratio, interface IPs | None |
| `GET` | `/api/download` | Downlink file transfer stream with timestamps | `size_mb` (float, e.g. `1.0`) |
| `POST` | `/api/upload` | Uplink file transfer consumer | Raw binary payload |
| `GET` | `/api/stream_down` | Downlink sustained data stream | `duration` (sec), `chunk_kb` (int) |
| `POST` | `/api/stream_up` | Uplink sustained data stream | Continuous binary stream |
| `POST` | `/api/set_mode` | Dynamic hot-switch of PDCP split ratio | `{"ratio": "1:0"}` |
| `POST` | `/api/record_result`| Records client telemetry to live dashboard | JSON result object |
| `GET` | `/api/metrics` | Returns full benchmark history and CPU stats | None |

---

## 7. Extracted Metrics & Statistical Formulas

### 1. Throughput (Mbps)
Calculated separately for Downlink (Server $\rightarrow$ UE) and Uplink (UE $\rightarrow$ Server):
$$\text{Throughput (Mbps)} = \frac{\text{Bytes Transferred} \times 8}{\text{Duration (seconds)} \times 10^6}$$

### 2. Instantaneous Throughput Time Series
Bytes transferred are partitioned into 1-second bins:
$$\text{Throughput}_{t} = \frac{\text{Bytes in Second } t \times 8}{10^6}\text{ Mbps}$$

### 3. End-to-End One-Way Latency (ms)
Sender stamps nanoseconds $T_{tx} = \text{time.time\_ns}()$ into the 16-byte binary header (`struct.pack("!QQ", seq, tx_ns)`). Receiver captures $T_{rx} = \text{time.time\_ns}()$ upon arrival:
$$\text{One-Way Latency} = \frac{T_{rx} - T_{tx}}{10^6}\text{ ms}$$
*Note: Because the UE and Server execute on the same host kernel, clock drift is exactly zero.*

### 4. Experienced Jitter (RFC 3550)
Statistical dispersion of packet delays calculated iteratively:
$$J = J + \frac{|D_{current} - D_{previous}| - J}{16}$$

### 5. Transport Reliability & Retransmissions
Extracted directly from the Linux kernel socket via `getsockopt(SOL_TCP, TCP_INFO, 128)`:
$$\text{Retransmission Rate (\%)} = \frac{\text{tcpi\_total\_retrans}}{\max(1, \text{tcpi\_segs\_out})} \times 100\%$$
$$\text{Packet Loss Rate (\%)} = \frac{\text{Lost Packets}}{\text{Total Packets}} \times 100\%$$

### 6. RAN CPU Utilization
Sampled every $200\text{ ms}$ by parsing `utime` and `stime` ticks from `/proc/<pid>/stat`:
$$\text{Process CPU \%} = \frac{\Delta\text{utime} + \Delta\text{stime}}{\text{CLK\_TCK} \times \Delta t} \times 100\%$$
$$\text{Normalized System CPU \%} = \frac{\sum \text{RAN Process CPU}}{\text{CPU Cores (16)}}$$

---

## 8. Teardown & Cleanup

When you are finished testing and wish to terminate all simulation processes and free ports:

```bash
# 1. Kill RAN and UE simulation processes
sudo pkill -9 -f srsue || true
sudo pkill -9 -f odu || true
sudo pkill -9 -f ocuup || true
sudo pkill -9 -f ocucp || true

# 2. Stop Web Server (free port 8080)
sudo fuser -k 8080/tcp || true

# 3. Clean temporary dynamic split ratio
rm -f /tmp/pdcp_split_ratio

# 4. Restore terminal state
stty sane 2>/dev/null || true
```
*(Alternatively, execute `/root/internship-repo/project/scripts/cleanup.sh`)*.

---

## 9. Troubleshooting & FAQs

### Q1: `tun_srsue` does not show up inside `ue_mn`.
**Cause**: The UE simulation is not running, or failed Random Access.
**Fix**: Ensure CU-CP, CU-UP, DU1, and DU2 are fully started before starting `srsue`. Check `/tmp/run_ue.log` for logs:
```bash
tail -n 30 /tmp/run_ue.log
```

### Q2: Port 8080 is already in use (`Address already in use`).
**Fix**: Kill any process listening on 8080:
```bash
sudo fuser -k 8080/tcp
```

### Q3: `Connection refused` when UE connects to `10.45.0.1:8080`.
**Fix**: Ensure `server.py` is running on `0.0.0.0` (all interfaces) rather than `127.0.0.1`, so the Open5GS `ogstun` interface can route packets to it.

### Q4: DU reports `F1 Setup Request failed` or `Connection refused`.
**Fix**: Ensure CU-CP is running and listening on port `38472` before starting DU1 or DU2.
