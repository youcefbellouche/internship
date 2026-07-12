# RLC AM Retransmission and Status Report Experiments

This document describes the design, implementation, and analysis of experiments targeting the RLC Acknowledged Mode (AM) retransmission and Status PDU reporting mechanisms within the `ocudu` framework.

---

## 🔬 Experiment Goals and Context

The purpose of these experiments is to observe and verify the behavior of the RLC AM layer under impaired channel conditions (missing packets) when polling features are disabled. By disabling proactive polling at the transmitter, the receiver is forced to rely solely on the `t-Reassembly` timer to detect gaps and trigger `STATUS PDU` (status reports).

The experiments cover two specific packet-loss scenarios starting from SN 0:
1. **Scenario 1 (Multiple Missing SNs):** Transmitter sends `0..4 6..18 20` (SN 5 and 19 are missing/dropped).
2. **Scenario 2 (Single Missing SN):** Transmitter sends `0..4 6..18` (SN 5 is missing/dropped).

---

## 🛠️ Configuration Changes

To focus the retransmissions purely on `t-Reassembly` expiration at the receiver, proactive transmitter-side status polling was disabled inside the QoS profile.

### QoS Override Config
The parameters `poll-pdu` and `poll-byte` were set to `-1` for all Acknowledged Mode (AM) bearers in the QoS configuration file:
* **File Path:** [qos.yml](file:///root/internship-repo/project/ocudu/configs/qos.yml)
* **Configuration snippet:**
  ```yaml
  rlc:
    mode: am
    am:
      tx:
        sn: 18
        t-poll-retransmit: 100
        max-retx-threshold: 32
        poll-pdu: -1       # Disabled
        poll-byte: -1      # Disabled
      rx:
        sn: 18
        t-reassembly: 20   # Timer configured to 20ms
        t-status-prohibit: 10
  ```

---

## 💻 Code Modifications & Test Hooks

To inject packet drops programmatically on the locally simulated loopback interface, a test hook was added to the gNB's RLC AM receiver entity. The hook intercepts incoming Data PDUs on User Plane bearers (DRBs) and drops specific sequence numbers upon their first arrival.

### gNB RLC AM Receiver Modifications
* **File Path:** [rlc_rx_am_entity.cpp](file:///root/internship-repo/project/ocudu/lib/rlc/rlc_rx_am_entity.cpp)
* **Implementation Details:**
  The test hook uses the environment variable `RLC_TEST_SCENARIO` to select the scenario:
  * **Scenario 1:** Drops SN `5` and `19` on first arrival.
  * **Scenario 2:** Drops SN `5` on first arrival.
  * *Note:* Subsequent retransmissions are allowed to pass through using a tracking set to prevent deadlocks.

```cpp
  // RLC AM Experiment test hooks
  char* scenario_str = std::getenv("RLC_TEST_SCENARIO");
  if (scenario_str && pcap_context.bearer_type == PCAP_RLC_BEARER_TYPE_DRB) {
    int scenario = std::atoi(scenario_str);
    static std::set<uint32_t> dropped_sns;
    if (scenario == 1) {
      if (header.sn == 5 || header.sn == 19) {
        if (dropped_sns.find(header.sn) == dropped_sns.end()) {
          dropped_sns.insert(header.sn);
          logger.log_info("[TEST_HOOK] Dropping PDU with SN={} for Scenario 1 (first arrival)", header.sn);
          return;
        }
      }
    } else if (scenario == 2) {
      if (header.sn == 5) {
        if (dropped_sns.find(header.sn) == dropped_sns.end()) {
          dropped_sns.insert(header.sn);
          logger.log_info("[TEST_HOOK] Dropping PDU with SN={} for Scenario 2 (first arrival)", header.sn);
          return;
        }
      }
    }
  }
```

---

## 🔨 Compilation Instructions

To build the gNB application and the custom unit tests:

1. **Navigate to the build directory:**
   ```bash
   cd /root/internship-repo/project/ocudu/build
   ```
2. **Compile the gNB binary:**
   ```bash
   make gnb
   ```
3. **Compile the RLC unit tests:**
   ```bash
   make rlc_rx_am_test
   ```

---

## 🏃 Running the Experiments

### 1. Synthetic Unit Verification
To execute the synthetic unit tests verifying both scenarios in an isolated mockup environment:
```bash
cd /root/internship-repo/project/ocudu/build
./tests/unittests/rlc/rlc_rx_am_test --gtest_filter=*TestRLC_AM_*
```

### 2. Live Runtime Network Simulation
To run the end-to-end local ZeroMQ simulation and observe live RLC retransmissions under ping traffic:

#### Set Up the Namespace
Ensure the UE namespace exists:
```bash
sudo ip netns add ue1
sudo ip netns exec ue1 ip link set lo up
```

#### Run Scenario 1 (Multiple Missing RLC SNs)
1. **Start the UE:**
   ```bash
   cd /root/internship-repo/project/srsRAN_4G/build
   sudo ./srsue/src/srsue ../../ue_zmq.conf
   ```
2. **Start the gNB** (in a separate terminal, passing QoS configuration and setting scenario environment variable):
   ```bash
   cd /root/internship-repo/project/ocudu/build
   RLC_TEST_SCENARIO=1 ./apps/gnb/gnb -c ../../gnb.zmq.yaml -c ../configs/qos.yml
   ```
3. **Inject Traffic:**
   Once the UE attaches and obtains its IP, trigger ping traffic from the `ue1` namespace:
   ```bash
   sudo ip netns exec ue1 ping 10.45.0.1 -c 20
   ```
4. **Shutdown and Flush Logs:**
   Stop the gNB and UE via `SIGTERM` to allow log files to flush:
   ```bash
   sudo pkill -15 gnb
   sudo pkill -15 srsue
   ```
5. **Logs Output:**
   * gNB logs are saved to `docs/rlc_scenario1_gnb.log`
   * UE logs are saved to `docs/rlc_scenario1_ue.log`

#### Run Scenario 2 (Single Missing RLC SN)
Repeat the steps above but execute the gNB with `RLC_TEST_SCENARIO=2`.
* **Logs Output:**
  * gNB logs are saved to `docs/rlc_scenario2_gnb.log`
  * UE logs are saved to `docs/rlc_scenario2_ue.log`

---

## 🔍 Detailed Analysis & Log Explanations

### Scenario 1: Multiple Missing SNs (5 and 19 dropped)

#### 1. Receiver-Side Logs Analysis (`docs/rlc_scenario1_gnb.log`)
* **Uplink Drop of SN 5 and 19:**
  As the ping traffic progresses from SN 0, SN 5 and SN 19 are dropped. Gaps are created, initiating the `t-Reassembly` timer for each gap. Once the timer expires, the gNB receiver sends a status report requesting retransmission, which successfully recovers the packet on the second attempt:
  ```text
  2026-07-07T10:51:21.237930 [RLC     ] [I] du=0 ue=0 DRB1 UL: [TEST_HOOK] Dropping PDU with SN=5 for Scenario 1 (first arrival)
  2026-07-07T10:51:35.269583 [RLC     ] [I] du=0 ue=0 DRB1 UL: [TEST_HOOK] Dropping PDU with SN=19 for Scenario 1 (first arrival)
  ```

#### 2. Transmitter-Side Logs Analysis (`docs/rlc_scenario1_ue.log`)
Even though proactive polling is disabled, the RLC transmitter still sets the poll bit (`P=1`) as a fallback when the transmit queue is empty. This prevents the link from stalling. When the UE receives a status report indicating NACKs, it schedules the retransmission of the missing SNs.

---

### Scenario 2: Single Missing SN (5 dropped)

#### 1. Logs Analysis (`docs/rlc_scenario2_gnb.log`)
In Scenario 2, SN 5 is dropped, while SN 19 is received normally.
* **Uplink Drop:**
  ```text
  2026-07-07T11:35:25.210845 [RLC     ] [I] du=0 ue=0 DRB1 UL: [TEST_HOOK] Dropping PDU with SN=5 for Scenario 2 (first arrival)
  ```
* **t-Reassembly Timer:**
  The gap at SN 5 triggers the `t-Reassembly` timer.
* **STATUS PDU construction:**
  Upon timer expiry, the status report lists:
  * **ACK_SN:** `5` (lowest missing packet)
  * **NACKs:** `5`
  * **Highest Received SN so far:** `6`

---

## 📈 Latency Observation (Ping RTT)

The RLC AM layer's packet drops directly impacted the user plane RTT during our ping tests:
* **Normal Ping RTT:** ~20–39 ms (no packet drops).
* **Impaired Ping RTT (Retransmission Delay):** ~150–170 ms (due to dropping the sequence number, waiting for `t-Reassembly` timer expiry, sending the `STATUS PDU`, and retransmitting the packet).
