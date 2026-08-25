# How to Run Dual Connectivity (DC) Tests & Simulations

This guide provides step-by-step instructions for executing the Dual Connectivity validation suite in two modes:
1. **Realtime ZMQ Simulation** (End-to-End Core, gNB CU/DU, and srsRAN UE).
2. **Standalone Unit Tests & Log Simulation Scripts**.

---

## 🛠️ Prerequisites

Ensure all dependencies, MongoDB, Open5GS, and built binaries exist in the workspace:
- Core: Open5GS (`open5gs-dbctl`, `ogstun`)
- CU/DU: `project/ocudu/build/apps/` (`ocucp`, `ocuup`, `odu`)
- UE: `project/srsRAN_4G/build/srsue/src/srsue`

---

## Method 1: Realtime ZMQ End-to-End Simulation

In realtime simulation mode, packets flow from the traffic generator through Open5GS UPF, down the CU-UP split/duplication bearer, over ZMQ radio channels to the 2-RLC srsRAN UE.

### Step 1: Launch the Network Simulation Stack

Run the integrated simulation launcher script:
```bash
cd /root/internship-repo/project
chmod +x run_simulation.sh
./run_simulation.sh
```

*(Alternatively, run individual nodes in separate terminal windows):*
```bash
# Terminal 1: CU-CP
sudo /root/internship-repo/project/ocudu/build/apps/cu_cp/ocucp -c /root/internship-repo/project/ocudu/configs/endc_cu_cp.yml

# Terminal 2: CU-UP
sudo /root/internship-repo/project/ocudu/build/apps/cu_up/ocuup -c /root/internship-repo/project/ocudu/configs/endc_cu_up.yml

# Terminal 3: DU1 (ID 1) & DU2 (ID 2)
sudo /root/internship-repo/project/ocudu/build/apps/du/odu -c /root/internship-repo/project/ocudu/configs/endc_du1.yml --gnb_du_id 1
sudo /root/internship-repo/project/ocudu/build/apps/du/odu -c /root/internship-repo/project/ocudu/configs/endc_du2.yml --gnb_du_id 2

# Terminal 4: Dual-Path srsRAN UE
sudo SRSUE_SN_CONFIG=/root/internship-repo/project/ue_sn.conf \
     /root/internship-repo/project/srsRAN_4G/build/srsue/src/srsue \
     /root/internship-repo/project/ue_mn.conf > /tmp/run_ue.log 2>&1
```

---

### Step 2: Inject Test Traffic & Verify Logs

#### Test 1: Realtime Split Bearer Test (Traffic Splitting Across DU1 & DU2)
```bash
# Send 8 sequential UDP packets across UPF to UE IP (10.45.0.3)
python3 /root/internship-repo/project/dc_test_sender.py --ip 10.45.0.3 --port 5001 --test split
```

**Log Verification Command:**
```bash
grep -E "(RLC.*lcid=[45]|PDCP.*deliver)" /tmp/run_ue.log | awk '
/lcid=4/ { print "\033[33m[DU1 -> RLC1]\033[0m", $0 }
/lcid=5/ { print "\033[36m[DU2 -> RLC2]\033[0m", $0 }
/PDCP.*deliver/ { print "\033[32m[PDCP DELIVERED]\033[0m", $0 }'
```

#### Test 2: Realtime Packet Duplication Test (URLLC Duplicate Discard)
```bash
# Send 4 duplicated UDP packets across both DU legs
python3 /root/internship-repo/project/dc_test_sender.py --ip 10.45.0.3 --port 5001 --test duplication
```

**Log Verification Command:**
```bash
awk '
/PDCP/ && /sn=[0-9]+/ {
    match($0, /sn=([0-9]+)/, arr);
    sn = arr[1];
    if (seen[sn]++) {
        print "\033[31m[PDCP DISCARD DUPLICATE]\033[0m SN " sn " -> " $0;
    } else {
        print "\033[32m[PDCP ACCEPT FIRST COPY]\033[0m SN " sn " -> " $0;
    }
}' /tmp/run_ue.log
```

---

## Method 2: Standalone Unit Tests & Simulation Scripts

For fast, deterministic validation of PDCP logic without running full RF/gNB binaries.

### Option A: Python Unit Test Suite (`test_dc_pdcp_stack.py`)

Validates PDCP reordering logic and duplicate detection using unit assertions:
```bash
python3 /root/internship-repo/project/test_dc_pdcp_stack.py -v
```
- **Output Log**: Saved to [`dc_unit_tests.log`](file:///root/internship-repo/project/dc_unit_tests.log)

---

### Option B: Realtime PDCP Layer Log Generators

Runs the full PDCP layer protocol state machine and generates dedicated, separate log files for each test scenario.

#### 1. Standard Split Bearer & Duplication Test Log Generator:
```bash
python3 /root/internship-repo/project/run_realtime_pdcp_tests.py
```
- **Generated Log Files**:
  - [`ue_pdcp_split_bearer.log`](file:///root/internship-repo/project/ue_pdcp_split_bearer.log)
  - [`ue_pdcp_packet_duplication.log`](file:///root/internship-repo/project/ue_pdcp_packet_duplication.log)
  - [`ue_full_pdcp.log`](file:///root/internship-repo/project/ue_full_pdcp.log)

#### 2. Test 1 with Delayed DU2 Leg (Timer Validation):
```bash
python3 /root/internship-repo/project/run_test1_delayed_du2.py
```
- **Generated Log File**:
  - [`ue_pdcp_split_bearer_delayed_du2.log`](file:///root/internship-repo/project/ue_pdcp_split_bearer_delayed_du2.log) (Demonstrates `t-Reordering` timer start/stop and gap filling).

---

### Option C: Native srsRAN C++ PDCP Unit Test

To run native srsRAN C++ unit test binaries directly:
```bash
cd /root/internship-repo/project/srsRAN_4G/build
make pdcp_nr_test_rx -j$(nproc)
./lib/test/pdcp/pdcp_nr_test_rx
```

---

## 📊 Summary of Executable Test Files

| Script / Test File | Purpose | Output / Log File |
| :--- | :--- | :--- |
| `run_simulation.sh` | End-to-End ZMQ Realtime Stack | `/tmp/run_ue.log` |
| `dc_test_sender.py` | Sends UDP Split & Duplication Packets | Traffic Output to IP |
| `test_dc_pdcp_stack.py` | Python `unittest` Suite for PDCP | `dc_unit_tests.log` |
| `run_realtime_pdcp_tests.py` | Standard Log Simulation Generator | `ue_pdcp_split_bearer.log` & `ue_pdcp_packet_duplication.log` |
| `run_test1_delayed_du2.py` | Delayed DU2 Leg & Timer Log Generator | `ue_pdcp_split_bearer_delayed_du2.log` |
| `pdcp_nr_test_rx` | Native srsRAN C++ Unit Test Binary | Terminal Output |
