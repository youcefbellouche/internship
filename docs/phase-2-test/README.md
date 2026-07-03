# PDCP RX Test Verification & Analysis (Phase 2)

This folder contains the execution logs, results, and end-to-end simulation comparisons for the custom PDCP RX test suite (`pdcp_rx_stormbrain_test`) and the live network simulation under forced network impairments.

## 📄 Contents
* [pdcp_rx_tests.log](file:///root/internship-repo/docs/phase-2-test/pdcp_rx_tests.log): Detailed unit test execution logs with debug-level logger information.
* [pdcp_rx_test_c_no_11.log](file:///root/internship-repo/docs/phase-2-test/pdcp_rx_test_c_no_11.log): Execution logs for Test C (Complex Reordering) showing behavior when packet 11 is dropped.
* [pdcp_rx_tests_1ms_interval.log](file:///root/internship-repo/docs/phase-2-test/pdcp_rx_tests_1ms_interval.log): Complete test suite execution logs using a 1ms injection interval between packets.
* [pdcp_rx_tests_with_simulation_time.log](file:///root/internship-repo/docs/phase-2-test/pdcp_rx_tests_with_simulation_time.log): Test suite execution logs with explicit mock simulation time printouts.
* [pdcp_rx_test_c_only.log](file:///root/internship-repo/docs/phase-2-test/pdcp_rx_test_c_only.log): Execution logs for Test C (Complex Reordering) only, with aligned real-time CPU sleeps.
* [pdcp_rx_test_d_only.log](file:///root/internship-repo/docs/phase-2-test/pdcp_rx_test_d_only.log): Execution logs for Test D (Middle Server/Proxy Simulation) only, sending 12 packets with real-time CPU sleeps.
* [pdcp_rx_test_d_encrypted.log](file:///root/internship-repo/docs/phase-2-test/pdcp_rx_test_d_encrypted.log): Execution logs for Test D only, with NIA2/NEA2 encryption and detailed PDU structure printing.
* [pdcp_rx_test_d_decrypted_failed.log](file:///root/internship-repo/docs/phase-2-test/pdcp_rx_test_d_decrypted_failed.log): Execution logs for Test D with decrypted/unencrypted packet injection showing integrity validation failure.
* [pdcp.log](file:///root/internship-repo/docs/pdcp.log): Live gNB PDCP simulation logs under forced impairment.
* [ue_pdcp.log](file:///root/internship-repo/docs/ue_pdcp.log): Live UE PDCP simulation logs under forced impairment.
* [README.md](file:///root/internship-repo/docs/phase-2-test/README.md): This file, providing an in-depth analysis of both execution modes.

---

## 🚀 How to Run the Tests & Simulation

### 1. Google Test (Unit Test Mode)
To compile and run the synthetic tests (Test A-D) with custom debug logs:
```bash
cd /root/internship-repo/project/ocudu/build
make pdcp_rx_test
./tests/unittests/pdcp/pdcp_rx_test --gtest_filter=pdcp_rx_stormbrain_test.* > /root/internship-repo/docs/phase-2-test/pdcp_rx_tests.log 2>&1
```

#### 🛠️ How to Modify the Unit Tests
All custom unit tests in Phase 2 are defined in the test source file:
* [pdcp_rx_test.cpp](file:///root/internship-repo/project/ocudu/tests/unittests/pdcp/pdcp_rx_test.cpp)

**To edit or add a test:**
1. Open the file and locate the `pdcp_rx_stormbrain_test` fixture class.
2. You can define a new test using `TEST_F(pdcp_rx_stormbrain_test, YourNewTestName) { ... }`.
3. Use the helper methods available in the fixture:
   - `create_pdu(sn)`: Generates an unprotected/unencrypted mock PDU with a 12-bit sequence number.
   - `create_decrypted_pdu_with_dummy_mac(sn)`: Generates a decrypted/unencrypted PDU with dummy `MAC-I` bytes.
   - `get_test_pdu(count, pdu)`: Retrieves a pre-configured, valid NIA2/NEA2 encrypted/integrity-protected test vector PDU for `COUNT = count`.
   - `inject_sns({sn1, sn2, ...})`: Simulates sending a sequence of PDUs to the PDCP entity.
   - `tick_all(ms)`: Ticks simulation timers and advances mock time by `ms` milliseconds.
4. Set up security parameters, RLC modes, or sequence numbers using standard Google Test APIs and check state assertions (e.g. `ASSERT_EQ(test_frame->sdu_queue.size(), expected)`).

#### 🔨 How to Compile the Unit Tests
After making changes to [pdcp_rx_test.cpp](file:///root/internship-repo/project/ocudu/tests/unittests/pdcp/pdcp_rx_test.cpp), recompile the test binary using:
```bash
cd /root/internship-repo/project/ocudu/build
make pdcp_rx_test
```

#### 🏃 How to Run Specific Unit Tests
To run only your modified or new test (e.g., `TestD_MiddleServerImplementation`), filter using the `--gtest_filter` option:
```bash
./tests/unittests/pdcp/pdcp_rx_test --gtest_filter=pdcp_rx_stormbrain_test.TestD_MiddleServerImplementation
```


### 2. End-to-End Simulation (Real Example Mode)
To run the live simulation with gNB, UE, and the Open5GS Core:
```bash
# 1. Start the gNB in the background
cd /root/internship-repo/project/ocudu/build
nohup ./apps/gnb/gnb -c ../../gnb.zmq.yaml > /tmp/gnb_stdout.log 2>&1 &

# 2. Start the UE in the background (will configure namespace 'ue1')
cd /root/internship-repo/project/srsRAN_4G/build
nohup sudo ./srsue/src/srsue ../../ue_zmq.conf > /tmp/ue_stdout.log 2>&1 &

# 3. Wait for PDU session setup, then run ping traffic (10 packets)
sudo ip netns exec ue1 ping 10.45.0.1 -c 10

# 4. Stop the simulation to flush logs
sudo killall gnb srsue
```

---

## 📊 Summary of Test Results

### 1. Synthetic Unit Test Cases (Test A - D)
All **4 tests** in the unit test suite passed:

| Test Case | Scenario Name | Status | Main Feature Validated |
| :--- | :--- | :--- | :--- |
| **Test A** | `TestA_DuplicatedScenario` | **PASSED** | Simple duplicate packet discarding (Sequence: `1, 2, 2, 3, 4`) |
| **Test B** | `TestB_PlayingWithTReordering` | **PASSED** | Basic `t-Reordering` timer expire/discard (Sequence: `1, 3` -> expire -> `5, 5, 2, 3` -> expire) |
| **Test C** | `TestC_ComplexTReorderingBehavior` | **PASSED** | Complex `t-Reordering` restart & stopping scenarios (Sequence: `1,2,3,8,4,6,9,10,12` -> expire -> `14,13,11` -> stop -> `15,16`) |
| **Test D** | `TestD_MiddleServerImplementation` | **PASSED** | Mock "Middle Server" delay interception & injection duplicate drop path |

### 2. End-to-End Live Simulation Runs

#### Clean Live 5G SA Baseline Execution
Verified live end-to-end user plane traffic across Open5GS Core, oCUDU gNB, and srsue UE inside network namespace `ue1` (PDU Session IP `10.45.0.4`):
* **Transmitted:** 10 packets (`ping 10.45.0.1 -c 10`)
* **Received:** 10 packets
* **Packet Loss:** 0.0%
* **RTT Metrics:** Min 26.3 ms / Avg 32.3 ms / Max 41.8 ms
* **Verified Logs:** Archived in [docs/pdcp.log](file:///root/internship-repo/docs/pdcp.log) and [docs/ue_pdcp.log](file:///root/internship-repo/docs/ue_pdcp.log).

#### Forced Impairment Run (Test Hooks Active)
By adding temporary testing hooks inside the oCUDU gNB PDCP receiver layer, we introduced live duplicates and reordering during end-to-end simulation traffic:
* **Transmitted:** 10 packets  
* **Received:** 9 packets  
* **Packet Loss:** 10% (Packet 4 dropped due to reordering timer expiry)  
* **RTT Timing Anomaly:** ICMP sequence 5 experienced a round-trip delay of **249 ms** (normal RTT of ~25ms + 220ms `t-Reordering` buffering delay).

---

## 🔍 Detailed Analysis & Log Explanations

### Live Simulation Execution under Programmatic Impairments
Since the local loopback ZeroMQ interface provides a perfect channel, we implemented a custom thread-based testing hook inside `/root/internship-repo/project/ocudu/lib/pdcp/pdcp_entity_rx.cpp` targeting uplink User Plane packets (`DRB1 UL`):

```cpp
// 1. Duplicate Injection for COUNT = 2
if (rcvd_count == 2) {
  static bool injected_dup = false;
  if (!injected_dup) {
    injected_dup = true;
    pdcp_rx_pdu_info dup_pdu{
      pdu_info.buf.deep_copy().value(),
      pdu_info.count,
      pdu_info.integrity_verified,
      pdu_info.time_of_arrival,
      pdcp_crypto_token(token_mngr)
    };
    ue_ul_executor.execute([this, dup_pdu = std::move(dup_pdu)]() mutable {
      apply_reordering(std::move(dup_pdu));
    });
  }
}

// 2. Reordering & Timer: Hold COUNT = 4, then inject it after 1500 ms delay
if (rcvd_count == 4) {
  static bool held_4 = false;
  if (!held_4) {
    held_4 = true;
    pdcp_rx_pdu_info saved_pdu_4{
      pdu_info.buf.deep_copy().value(),
      pdu_info.count,
      pdu_info.integrity_verified,
      pdu_info.time_of_arrival,
      pdcp_crypto_token(token_mngr)
    };
    std::thread([this, pdu = std::move(saved_pdu_4)]() mutable {
      std::this_thread::sleep_for(std::chrono::milliseconds(1500));
      ue_ul_executor.execute([this, pdu = std::move(pdu)]() mutable {
        apply_reordering(std::move(pdu));
      });
    }).detach();
    return; // Skip current processing
  }
}
```

### Analysis of the Resulting Log file ([pdcp.log](file:///root/internship-repo/docs/pdcp.log))
When running the 10 pings, the following execution timeline was captured in the logs:

1. **Duplicate Discard (Count=2)**:
   ```text
   2026-06-23T22:42:18.293357 [PDCP    ] [I] ue=0 DRB1 UL: RX PDU. type=data pdu_len=87 sn=2 count=2
   2026-06-23T22:42:18.293367 [PDCP    ] [I] ue=0 DRB1 UL: [TEST_HOOK] Simulating duplicate arrival for count=2 by re-injecting immediately.
   2026-06-23T22:42:18.293370 [PDCP    ] [I] ue=0 DRB1 UL: RX SDU. count=2
   2026-06-23T22:42:18.293379 [PDCP    ] [D] ue=0 DRB1 UL: Out-of-order after timeout, duplicate or count wrap-around. count=2 rx_next=3 rx_deliv=3 rx_reord=0
   ```
   * **Analysis:** The duplicate `count=2` packet is immediately detected as having a count less than `rx_deliv` (3) and is successfully discarded.

2. **Reordering Timer Start (Count=4 Held, Count=5 Arrived)**:
   ```text
   2026-06-23T22:42:20.297205 [PDCP    ] [I] ue=0 DRB1 UL: RX PDU. type=data pdu_len=87 sn=4 count=4
   2026-06-23T22:42:20.297213 [PDCP    ] [I] ue=0 DRB1 UL: [TEST_HOOK] Holding count=4 to create a gap and trigger t-Reordering timer
   2026-06-23T22:42:21.722606 [PDCP    ] [I] ue=0 DRB1 UL: RX PDU. type=data pdu_len=87 sn=5 count=5
   2026-06-23T22:42:21.722627 [PDCP    ] [D] ue=0 DRB1 UL: Started t-Reordering.
   ```
   * **Analysis:** `count=4` is held. Since ping intervals are 1000 ms, 1.4 seconds later `count=5` arrives. Because `count=4` is missing, `count=5` is out-of-order, starting the 220 ms `t-Reordering` timer.

3. **Reordering Timer Expiration**:
   ```text
   2026-06-23T22:42:21.952980 [PDCP    ] [I] ue=0 DRB1 UL: Reordering timer expired. rx_next=6 rx_deliv=4 rx_reord=6
   2026-06-23T22:42:21.952981 [PDCP    ] [I] ue=0 DRB1 UL: RX SDU. count=5
   ```
   * **Analysis:** Exactly 220 ms later, the timer fires. `count=5` is delivered to the upper layers. `rx_deliv` is updated to `6`. This latency introduces a delay of 220 ms, making the RTT of the corresponding ping packet (`icmp_seq=5`) rise to **249 ms**.

4. **Late Packet Discard**:
   ```text
   2026-06-23T22:42:22.209731 [PDCP    ] [I] ue=0 DRB1 UL: [TEST_HOOK] Thread injecting held count=4 now
   2026-06-23T22:42:22.209855 [PDCP    ] [D] ue=0 DRB1 UL: Out-of-order after timeout, duplicate or count wrap-around. count=4 rx_next=6 rx_deliv=6 rx_reord=6
   ```
   * **Analysis:** 1500 ms after arrival, `count=4` is injected. Since `rx_deliv` is already `6`, `count=4` is discarded as too late. It is never delivered to the IP stack, causing **10% packet loss** (ping `icmp_seq=4` lost).

---

## 🔄 Comparison: Unit Test vs. Real Simulation

Below is a detailed breakdown of the differences between the isolated synthetic tests and the real-world execution:

| Feature / Behavior | Google Unit Test Suite | End-to-End Live Simulation |
| :--- | :--- | :--- |
| **Log Levels & Detail** | **Debug Level** (`debug`). Logs internal states (`Adding SN to window`, `Out-of-order after timeout`, `Duplicate PDU dropped`). | **Debug Level** (Set manually in `gnb.zmq.yaml` and `ue_zmq.conf`). Captured identical state transitions during ping. |
| **Path Directionality** | **Unidirectional (UL-only)**. Manually tests the RX entity in isolation. | **Bidirectional (UL and DL)**. Runs both TX and RX components simultaneously on both gNB and UE sides. |
| **Sequence Number Size** | **12-bit** (`sn_size=12`). | **18-bit** (`sn_size=18`) for User Plane Data (DRB1), which is typical for high-throughput 5G NR data transmission. |
| **t-Reordering Timer** | **10 ms** (`ms10`). Used to trigger fast, predictable mock timeouts inside the unit test loop. | **220 ms** (`t_reordering=220`). Standard production reordering timer value for user-plane data. |
| **Security Mode** | **Disabled** (Ciphering and Integrity OFF) to facilitate custom raw PDU injection. | **Enabled** (Ciphering ON via `NEA0`/`NEA2`, Integrity OFF for User Plane data), applying real crypto keys. |
| **Channel Conditions** | **Impaired**. Manually introduces duplicate packets, 1-second delays, and sequence gaps. | **Forced Impairment**. Using thread-based delay injection hooks to verify live reordering timer expiry and late discards. |
| **Reordering Timer Activity** | **Highly Active**. The timer starts, stops, and expires continuously to handle synthetic gaps. | **Triggered on Demand**. Starts when a gap is created, expires after 220 ms, and triggers late packet drops. |
| **Execution Mechanics** | **Single-threaded mock environment**. Threading is simulated via task queues and manual tick intervals. | **Multi-threaded asynchronous environment**. Real CPU threads run scheduling, baseband DSP, and timers. |
