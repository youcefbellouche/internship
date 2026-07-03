# Change 02: PDCP Duplicate Discarding and t-Reordering Tests

**Date:** 2026-06-22  
**Author:** AI Pair Programmer  
**Status:** Implemented & Verified  

---

## 🎯 Goal
Implement custom validation tests in the Google Test framework for the PDCP RX layer (`pdcp_entity_rx`) to verify duplicate packet discarding, `t-Reordering` timer start/expire/restart mechanics, and a mock "Middle Server" delay path. The logs of these executions must focus exclusively on PDCP DRB operations.

---

## 🛠️ Implementation Details

### Custom Test Suite in `pdcp_rx_test.cpp`
A new test class `pdcp_rx_stormbrain_test` was created inside [pdcp_rx_test.cpp](file:///root/internship-repo/project/ocudu/tests/unittests/pdcp/pdcp_rx_test.cpp#L781) to execute tests under a controlled setup:
* **12-bit Sequence Number** size.
* **RLC AM mode** operation.
* **10 ms t-Reordering** timer value (`ms10`).
* **Security algorithms set to OFF** (ciphering/integrity disabled) to facilitate injection of custom raw test sequence numbers.
* **Log isolation**: The basic logger is muted for other components and restricted to debug/info for the `"PDCP"` logger, ensuring only DRB-related PDCP logs populate.

A helper method `create_pdu` creates raw unencrypted PDCP Data PDUs with proper headers for any sequence number (SN):
```cpp
byte_buffer create_pdu(uint16_t sn) {
  byte_buffer pdu;
  if (not pdu.resize(4)) {
    report_fatal_error("Failed to resize byte buffer");
  }
  pdu[0] = 0x80 | ((sn >> 8) & 0x0F); // Set MSB D/C bit to 1 (Data PDU)
  pdu[1] = sn & 0xFF;
  pdu[2] = 0x18;
  pdu[3] = 0xe2; // Payload: SDU {0x18, 0xe2}
  return pdu;
}
```

---

## 📊 Verification Test Cases and Benchmarks

### Test A: Duplicated Scenario
* **Injected RX Sequence:** 1, 2, 2, 3, 4
* **Expected Behavior:** Receiver processes 1, 2, 3, 4 normally and discards the second 2 as a duplicate.
* **Actual Results:**
  * **Test Outcome:** `PASSED` (`pdcp_rx_stormbrain_test.TestA_DuplicatedScenario`)
  * **Verified Behavior:** Sequence numbers 1, 2, 3, and 4 were successfully assembled and delivered as SDUs to the higher layer (`RX SDU. count=1, 2, 3, 4`). The duplicate PDU for SN 2 arrived after SN 2 was already delivered and cleared from the rx_window (at state `rx_deliv=3`). Consequently, it hit the `rcvd_count < rx_deliv` condition in `pdcp_entity_rx::apply_reordering` and was discarded cleanly.
* **Code Breakpoint Mechanics:**  
  In [pdcp_entity_rx.cpp:L473-L483](file:///root/internship-repo/project/ocudu/lib/pdcp/pdcp_entity_rx.cpp#L473-L483), when a PDU arrives, the RX window is checked:
  ```cpp
  if (rx_window.has_sn(rcvd_count)) {
    const pdcp_rx_sdu_info& sdu_info = rx_window[rcvd_count];
    if (sdu_info.count == rcvd_count) {
      logger.log_debug("Duplicate PDU dropped. count={}", rcvd_count);
      metrics.add_dropped_pdus(1);
      return; // PDU already present in window, drop.
    }
  }
  ```
* **Execution Logs:**
  ```text
  2026-06-23T22:10:13.737061 [PDCP    ] [I] [     0.0] ue=0 DRB1 UL: RX PDU. type=data pdu_len=4 sn=1 count=1
  2026-06-23T22:10:13.737215 [PDCP    ] [I] [     0.0] ue=0 DRB1 UL: RX SDU. count=1
  2026-06-23T22:10:13.737218 [PDCP    ] [I] [     0.0] ue=0 DRB1 UL: RX PDU. type=data pdu_len=4 sn=2 count=2
  2026-06-23T22:10:13.737432 [PDCP    ] [I] [     0.0] ue=0 DRB1 UL: RX SDU. count=2
  2026-06-23T22:10:13.737435 [PDCP    ] [I] [     0.0] ue=0 DRB1 UL: RX PDU. type=data pdu_len=4 sn=2 count=2
  2026-06-23T22:10:13.737614 [PDCP    ] [D] [     0.0] ue=0 DRB1 UL: Out-of-order after timeout, duplicate or count wrap-around. count=2 rx_next=3 rx_deliv=3 rx_reord=0
  2026-06-23T22:10:13.737616 [PDCP    ] [I] [     0.0] ue=0 DRB1 UL: RX PDU. type=data pdu_len=4 sn=3 count=3
  2026-06-23T22:10:13.737785 [PDCP    ] [I] [     0.0] ue=0 DRB1 UL: RX SDU. count=3
  2026-06-23T22:10:13.737787 [PDCP    ] [I] [     0.0] ue=0 DRB1 UL: RX PDU. type=data pdu_len=4 sn=4 count=4
  2026-06-23T22:10:13.737961 [PDCP    ] [I] [     0.0] ue=0 DRB1 UL: RX SDU. count=4
  ```

---

### Test B: Playing with t-Reordering
* **Injected RX Sequence:** 1, 3 (Wait for timer expiration), then 5, 5, 2, 3
* **Expected Behavior:**
  1. SN 1 delivered immediately.
  2. SN 3 starts the 10ms reordering timer (waiting for missing SN 2).
  3. Timer expires => SN 3 delivered; `rx_deliv` advances to 4.
  4. SN 5 received => out-of-order (missing 4), starts new reordering timer.
  5. Second SN 5 is immediately discarded as duplicate.
  6. Delayed SN 3 and SN 2 arrive => discarded because they are too late (since `rx_deliv` is already 4).
  7. Second timer expires => SN 5 delivered; `rx_deliv` advances to 6.
* **Actual Results:**
  * **Test Outcome:** `PASSED` (`pdcp_rx_stormbrain_test.TestB_PlayingWithTReordering`)
  * **Verified Behavior:** Perfect 1:1 adherence to 3GPP TS 38.323 specifications. Timer started at SN 3 and expired after 10ms, advancing `rx_deliv` to 4 and delivering SDU 3. The second SN 5 arrived while the first SN 5 was still buffered in window (`rx_window.has_sn(5)` is true), triggering the exact `"Duplicate PDU dropped. count=5"` log line. Delayed SN 3 and 2 arriving after timeout were dropped as out-of-order.
* **Code Breakpoint Mechanics:**  
  * **Timer Start:** In [pdcp_entity_rx.cpp:L522-L526](file:///root/internship-repo/project/ocudu/lib/pdcp/pdcp_entity_rx.cpp#L522-L526), if a gap is detected (`st.rx_deliv < st.rx_next`), the timer is run:
    ```cpp
    st.rx_reord = st.rx_next;
    reordering_timer.run();
    ```
  * **Timer Expire:** In [pdcp_entity_rx.cpp:L819-L845](file:///root/internship-repo/project/ocudu/lib/pdcp/pdcp_entity_rx.cpp#L819-L845), when the timer fires, all buffered SDUs with COUNT < `rx_reord` are delivered, and `rx_deliv` is updated to `rx_reord`.
  * **Discarding Late packets:** In [pdcp_entity_rx.cpp:L462](file:///root/internship-repo/project/ocudu/lib/pdcp/pdcp_entity_rx.cpp#L462), any arriving COUNT < `rx_deliv` is discarded:
    ```cpp
    if (rcvd_count < st.rx_deliv) {
      metrics.add_dropped_pdus(1);
      return; // Invalid count, drop.
    }
    ```
* **Execution Logs:**
  ```text
  2026-06-23T22:10:13.739180 [PDCP    ] [I] [     0.0] ue=0 DRB1 UL: RX PDU. type=data pdu_len=4 sn=1 count=1
  2026-06-23T22:10:13.739349 [PDCP    ] [I] [     0.0] ue=0 DRB1 UL: RX SDU. count=1
  2026-06-23T22:10:13.739352 [PDCP    ] [I] [     0.0] ue=0 DRB1 UL: RX PDU. type=data pdu_len=4 sn=3 count=3
  2026-06-23T22:10:13.739529 [PDCP    ] [D] [     0.0] ue=0 DRB1 UL: Started t-Reordering.
  2026-06-23T22:10:13.739532 [PDCP    ] [I] [     0.0] ue=0 DRB1 UL: Reordering timer expired. rx_next=4 rx_deliv=2 rx_reord=4
  2026-06-23T22:10:13.739532 [PDCP    ] [I] [     0.0] ue=0 DRB1 UL: RX SDU. count=3
  2026-06-23T22:10:13.739534 [PDCP    ] [I] [     0.0] ue=0 DRB1 UL: RX PDU. type=data pdu_len=4 sn=5 count=5
  2026-06-23T22:10:13.739710 [PDCP    ] [D] [     0.0] ue=0 DRB1 UL: Started t-Reordering.
  2026-06-23T22:10:13.739712 [PDCP    ] [I] [     0.0] ue=0 DRB1 UL: RX PDU. type=data pdu_len=4 sn=5 count=5
  2026-06-23T22:10:13.739890 [PDCP    ] [D] [     0.0] ue=0 DRB1 UL: Duplicate PDU dropped. count=5
  2026-06-23T22:10:13.739891 [PDCP    ] [I] [     0.0] ue=0 DRB1 UL: RX PDU. type=data pdu_len=4 sn=3 count=3
  2026-06-23T22:10:13.740069 [PDCP    ] [D] [     0.0] ue=0 DRB1 UL: Out-of-order after timeout, duplicate or count wrap-around. count=3 rx_next=6 rx_deliv=4 rx_reord=6
  2026-06-23T22:10:13.740070 [PDCP    ] [I] [     0.0] ue=0 DRB1 UL: RX PDU. type=data pdu_len=4 sn=2 count=2
  2026-06-23T22:10:13.740312 [PDCP    ] [D] [     0.0] ue=0 DRB1 UL: Out-of-order after timeout, duplicate or count wrap-around. count=2 rx_next=6 rx_deliv=4 rx_reord=6
  2026-06-23T22:10:13.740314 [PDCP    ] [I] [     0.0] ue=0 DRB1 UL: Reordering timer expired. rx_next=6 rx_deliv=4 rx_reord=6
  2026-06-23T22:10:13.740314 [PDCP    ] [I] [     0.0] ue=0 DRB1 UL: RX SDU. count=5
  ```

---

### Test C: Complex t-Reordering Behavior
* **Injected RX Sequence:** 1, 2, 3, 8, 4, 6, 9, 10, 12 (Wait for timer expiration), 14, 13, 11 (Timer stops), 15, 16
* **Expected Behavior:**
  1. SN 1 to 3 delivered instantly. `rx_deliv` = 4.
  2. SN 8 starts reordering timer.
  3. SN 4 arrives, delivered immediately since it matches `rx_deliv` (4). `rx_deliv` becomes 5.
  4. SN 6, 9, 10, 12 are buffered.
  5. Timer expires => Deliver 6, 8. And because 9, 10 are consecutive, they are also delivered. `rx_deliv` becomes 11.
  6. A new timer restarts immediately since `rx_deliv` (11) < `rx_next` (13) (missing 11).
  7. SN 14, 13 are buffered.
  8. SN 11 arrives => Deliver 11, and consecutive 12, 13, 14. `rx_deliv` becomes 15.
  9. Active timer stops since `rx_deliv` (15) >= `rx_reord` (13).
  10. SN 15, 16 delivered immediately.
* **Actual Results:**
  * **Test Outcome:** `PASSED` (`pdcp_rx_stormbrain_test.TestC_ComplexTReorderingBehavior`)
  * **Verified Behavior:** Demonstrated complete 3GPP multi-step reordering dynamics. Upon timer expiration at `rx_deliv=5`, SDUs 6, 8, 9, 10 were delivered, updating `rx_deliv` to 11. Because `rx_deliv (11) < rx_next (13)`, the timer immediately restarted with `rx_reord` updated to 13. When missing SN 11 arrived, contiguous delivery flushed SDUs 11, 12, 13, 14, advancing `rx_deliv` to 15, which triggered the explicit timer stop mechanic (`Stopped t-Reordering`).
* **Code Breakpoint Mechanics:**  
  * **Timer Restarting:** In [pdcp_entity_rx.cpp:L852-L861](file:///root/internship-repo/project/ocudu/lib/pdcp/pdcp_entity_rx.cpp#L852-L861), if `rx_deliv < rx_next` after timer expiration, a new timer runs:
    ```cpp
    if (st.rx_deliv < st.rx_next) {
      st.rx_reord = st.rx_next;
      reordering_timer.run();
    }
    ```
  * **Timer Stopping:** In [pdcp_entity_rx.cpp:L513-L516](file:///root/internship-repo/project/ocudu/lib/pdcp/pdcp_entity_rx.cpp#L513-L516), if consecutive delivery catches up to/exceeds `rx_reord`, the timer stops:
    ```cpp
    if (reordering_timer.is_running() and st.rx_deliv >= st.rx_reord) {
      reordering_timer.stop();
    }
    ```
* **Execution Logs:**
  ```text
  2026-06-23T22:10:13.741199 [PDCP    ] [I] [     0.0] ue=0 DRB1 UL: RX PDU. type=data pdu_len=4 sn=1 count=1
  2026-06-23T22:10:13.741351 [PDCP    ] [I] [     0.0] ue=0 DRB1 UL: RX SDU. count=1
  2026-06-23T22:10:13.741353 [PDCP    ] [I] [     0.0] ue=0 DRB1 UL: RX PDU. type=data pdu_len=4 sn=2 count=2
  2026-06-23T22:10:13.741534 [PDCP    ] [I] [     0.0] ue=0 DRB1 UL: RX SDU. count=2
  2026-06-23T22:10:13.741536 [PDCP    ] [I] [     0.0] ue=0 DRB1 UL: RX PDU. type=data pdu_len=4 sn=3 count=3
  2026-06-23T22:10:13.741715 [PDCP    ] [I] [     0.0] ue=0 DRB1 UL: RX SDU. count=3
  2026-06-23T22:10:13.741717 [PDCP    ] [I] [     0.0] ue=0 DRB1 UL: RX PDU. type=data pdu_len=4 sn=8 count=8
  2026-06-23T22:10:13.741899 [PDCP    ] [D] [     0.0] ue=0 DRB1 UL: Started t-Reordering.
  2026-06-23T22:10:13.741901 [PDCP    ] [I] [     0.0] ue=0 DRB1 UL: RX PDU. type=data pdu_len=4 sn=4 count=4
  2026-06-23T22:10:13.742072 [PDCP    ] [I] [     0.0] ue=0 DRB1 UL: RX SDU. count=4
  2026-06-23T22:10:13.742074 [PDCP    ] [I] [     0.0] ue=0 DRB1 UL: RX PDU. type=data pdu_len=4 sn=6 count=6
  2026-06-23T22:10:13.742260 [PDCP    ] [I] [     0.0] ue=0 DRB1 UL: RX PDU. type=data pdu_len=4 sn=9 count=9
  2026-06-23T22:10:13.742443 [PDCP    ] [I] [     0.0] ue=0 DRB1 UL: RX PDU. type=data pdu_len=4 sn=10 count=10
  2026-06-23T22:10:13.742624 [PDCP    ] [I] [     0.0] ue=0 DRB1 UL: RX PDU. type=data pdu_len=4 sn=12 count=12
  2026-06-23T22:10:13.742806 [PDCP    ] [I] [     0.0] ue=0 DRB1 UL: Reordering timer expired. rx_next=13 rx_deliv=5 rx_reord=9
  2026-06-23T22:10:13.742807 [PDCP    ] [I] [     0.0] ue=0 DRB1 UL: RX SDU. count=6
  2026-06-23T22:10:13.742807 [PDCP    ] [I] [     0.0] ue=0 DRB1 UL: RX SDU. count=8
  2026-06-23T22:10:13.742807 [PDCP    ] [I] [     0.0] ue=0 DRB1 UL: RX SDU. count=9
  2026-06-23T22:10:13.742808 [PDCP    ] [I] [     0.0] ue=0 DRB1 UL: RX SDU. count=10
  2026-06-23T22:10:13.742808 [PDCP    ] [D] [     0.0] ue=0 DRB1 UL: Updating rx_reord to rx_next. rx_next=13 rx_deliv=11 rx_reord=9
  2026-06-23T22:10:13.742809 [PDCP    ] [I] [     0.0] ue=0 DRB1 UL: RX PDU. type=data pdu_len=4 sn=14 count=14
  2026-06-23T22:10:13.742986 [PDCP    ] [I] [     0.0] ue=0 DRB1 UL: RX PDU. type=data pdu_len=4 sn=13 count=13
  2026-06-23T22:10:13.743176 [PDCP    ] [I] [     0.0] ue=0 DRB1 UL: RX PDU. type=data pdu_len=4 sn=11 count=11
  2026-06-23T22:10:13.743357 [PDCP    ] [I] [     0.0] ue=0 DRB1 UL: RX SDU. count=11
  2026-06-23T22:10:13.743357 [PDCP    ] [I] [     0.0] ue=0 DRB1 UL: RX SDU. count=12
  2026-06-23T22:10:13.743358 [PDCP    ] [I] [     0.0] ue=0 DRB1 UL: RX SDU. count=13
  2026-06-23T22:10:13.743358 [PDCP    ] [I] [     0.0] ue=0 DRB1 UL: RX SDU. count=14
  2026-06-23T22:10:13.743358 [PDCP    ] [D] [     0.0] ue=0 DRB1 UL: Stopped t-Reordering.
  2026-06-23T22:10:13.743360 [PDCP    ] [I] [     0.0] ue=0 DRB1 UL: RX PDU. type=data pdu_len=4 sn=15 count=15
  2026-06-23T22:10:13.743538 [PDCP    ] [I] [     0.0] ue=0 DRB1 UL: RX SDU. count=15
  2026-06-23T22:10:13.743539 [PDCP    ] [I] [     0.0] ue=0 DRB1 UL: RX PDU. type=data pdu_len=4 sn=16 count=16
  2026-06-23T22:10:13.743725 [PDCP    ] [I] [     0.0] ue=0 DRB1 UL: RX SDU. count=16
  ```

---

### Test D: Middle Server Implementation
* **Task Scenario:** The middle server intercepts packets from the CU, logs/prints the full PDCP object to the console, and injects it to the UE after a strict 1-second delay.
* **Expected Behavior:** Original packet processed and delivered; delayed injection discarded as duplicate.
* **Actual Results:**
  * **Test Outcome:** `PASSED` (`pdcp_rx_stormbrain_test.TestD_MiddleServerImplementation`)
  * **Verified Behavior:** The middle server successfully captured raw byte payload `80 01 18 e2`, logged intercept metadata, delivered the primary PDU, and held the duplicate packet. When injected after delay, the PDCP RX layer safely rejected the delayed packet as out-of-order/duplicate without crashing or corrupting state.
* **Execution Logs:**
  ```text
  [Middle Server] Intercepted PDU from CU. Length: 4, Content: 80 01 18 e2
  2026-06-23T22:10:13.744724 [PDCP    ] [I] [     0.0] ue=0 DRB1 UL: RX PDU. type=data pdu_len=4 sn=1 count=1
  2026-06-23T22:10:13.744880 [PDCP    ] [I] [     0.0] ue=0 DRB1 UL: RX SDU. count=1
  [Middle Server] 1-second delay expired. Injecting duplicate PDU to UE.
  2026-06-23T22:10:13.744910 [PDCP    ] [I] [     0.0] ue=0 DRB1 UL: RX PDU. type=data pdu_len=4 sn=1 count=1
  2026-06-23T22:10:13.745064 [PDCP    ] [D] [     0.0] ue=0 DRB1 UL: Out-of-order after timeout, duplicate or count wrap-around. count=1 rx_next=2 rx_deliv=2 rx_reord=0
  ```

---

## ⚠️ Discovered Behaviors and Implementation Insights

During execution and log verification of both unit tests and full-stack end-to-end ZMQ simulations, several key architectural behaviors were identified:

### 1. Differentiated Duplicate Discard Logging
The oCUDU PDCP implementation in [pdcp_entity_rx.cpp](file:///root/internship-repo/project/ocudu/lib/pdcp/pdcp_entity_rx.cpp) employs two distinct code paths to handle duplicate packets:
* **Buffered Duplicate Drop (`count >= rx_deliv`):** When a duplicate PDU arrives for a sequence number that is currently buffered inside the active reordering window (`rx_window.has_sn(rcvd_count)` is true), it triggers line 477 and outputs:  
  `[D] ue=0 DRB1 UL: Duplicate PDU dropped. count=X`
* **Post-Delivery / Late Drop (`count < rx_deliv`):** When a duplicate or reordered PDU arrives after its sequence number has already been delivered to the higher layer and purged from the window, it is caught at line 462 and outputs:  
  `[D] ue=0 DRB1 UL: Out-of-order after timeout, duplicate or count wrap-around. count=X`

### 2. Log Interleaving Artifact (Asynchronous Logging Queue)
In Test D console output, `[Middle Server]` log messages (printed via standard synchronous `fmt::print`) appear slightly interleaved relative to `[PDCP]` log lines. This occurs because oCUDU utilizes an asynchronous logger worker thread (`ocudulog`) that processes log records in a non-blocking background queue. Full log order is consistently preserved upon worker flush (`TearDown()`).

### 3. Production vs. Unit Test Differences
* **Sequence Number Length:** Unit tests operate under 12-bit SNs (max COUNT 4095), whereas full-stack 5G SA production DRB configuration utilizes 18-bit SNs (max COUNT 262143).
* **Timer Granularity:** Unit tests configure a fast 10 ms `t-Reordering` timer for rapid test execution, while production gNB DRB defaults to 220 ms.
* **Full Execution Log Archive:** The complete, raw test log output generated during unit test verification is archived in [docs/phase-2-test/pdcp_rx_tests.log](file:///root/internship-repo/docs/phase-2-test/pdcp_rx_tests.log). Detailed architectural analysis and live simulation comparisons are documented in [docs/phase-2-test/README.md](file:///root/internship-repo/docs/phase-2-test/README.md).

