# RLC AM Logs Analysis and Comparison Report

This document presents a comparative analysis of the logs generated during isolated synthetic unit tests and the live real-time network simulation under RLC Acknowledged Mode (AM) packet drop scenarios.

---

## 🔍 Log Overview

### 1. Google Test (Isolated Unit Tests)
* **Log File:** [rlc_unit_tests.log](file:///root/internship-repo/docs/rlc_unit_tests.log)
* **Goal:** Verify RLC AM receiver functionality in isolation by manually feeding a pre-constructed sequence of PDUs starting from SN 0 and mocking time ticks to trigger reassembly.

### 2. Live Runtime Simulation (Scenario 1 & Scenario 2)
* **Scenario 1 Logs:** [rlc_scenario1_gnb.log](file:///root/internship-repo/docs/rlc_scenario1_gnb.log) and [rlc_scenario1_ue.log](file:///root/internship-repo/docs/rlc_scenario1_ue.log)
* **Scenario 2 Logs:** [rlc_scenario2_gnb.log](file:///root/internship-repo/docs/rlc_scenario2_gnb.log) and [rlc_scenario2_ue.log](file:///root/internship-repo/docs/rlc_scenario2_ue.log)
* **Goal:** Verify end-to-end RLC AM retransmission behavior with real network traffic (ICMP ping) on local loopback ZMQ interfaces under programmatic single and multiple packet drops.

---

## 🛠️ Step-by-Step Log Explanation

### Phase A: Packet Drop and Gap Detection

#### In Unit Tests:
The test programmatically injects a sequence of PDUs into the RLC receiver. When SN 5 is omitted, the receiver detects a gap as soon as SN 6 arrives:
```text
2026-07-07T10:50:11.086586 [TEST    ] [D] AMD PDU header: dc=data p=0 si=full sn=6
2026-07-07T10:50:11.086586 [RLC     ] [I] [     0.0] du=0 ue=0 SRB0 UL: RX PDU. pdu_len=22 dc=data p=0 si=full sn=6
2026-07-07T10:50:11.086587 [RLC     ] [D] [     0.0] du=0 ue=0 SRB0 UL: Adding sn=6 to window.
2026-07-07T10:50:11.086588 [RLC     ] [D] [     0.0] du=0 ue=0 SRB0 UL: Started reassembly timer, updated rx_next_status_trigger=7.
```
* **Analysis:** The out-of-order arrival of SN 6 triggers the start of `t-Reassembly`. `rx_next_status_trigger` is set to `7` (one past the highest received continuous sequence).

#### In Real-Time Simulation:
The UE transmits uplink user packets. When SN 5 arrives at the gNB, the custom test hook drops it on its first arrival. When SN 6 arrives, the gap is detected, starting the reassembly timer:
```text
2026-07-07T10:51:21.237930 [RLC     ] [I] du=0 ue=0 DRB1 UL: [TEST_HOOK] Dropping PDU with SN=5 for Scenario 1 (first arrival)
2026-07-07T10:51:21.246405 [RLC     ] [D] du=0 ue=0 DRB1 UL: Adding sn=6 to window.
2026-07-07T10:51:21.246410 [RLC     ] [D] du=0 ue=0 DRB1 UL: Started reassembly timer, updated rx_next_status_trigger=7.
```
* **Analysis:** The live gNB RLC receiver shows the exact same gap-detection logic as the unit test, updating `rx_next_status_trigger` to `7` and initiating the `t-Reassembly` timer.

---

### Phase B: Reassembly Timer Expiry & STATUS PDU Construction

#### In Unit Tests:
Since time is virtual in unit tests, we simulate the passage of time by calling a loop of `tick()` commands. Once the timer expires, the receiver builds the status report:
```text
2026-07-07T10:50:11.086639 [RLC     ] [D] [     0.0] du=0 ue=0 SRB0 UL: Reassembly timer expired after 35ms.
2026-07-07T10:50:11.086639 [RLC     ] [D] [     0.0] du=0 ue=0 SRB0 UL: Restarted t-Reassmebly. rx_next=5 rx_next_status_trigger=21 rx_highest_status=19 rx_next_highest=21
2026-07-07T10:50:11.086639 [RLC     ] [D] [     0.0] du=0 ue=0 SRB0 UL: Generating status PDU. rx_next=5 rx_highest_status=19 stop_sn=19
2026-07-07T10:50:11.086640 [RLC     ] [D] [     0.0] du=0 ue=0 SRB0 UL: Adding nack=[5].
2026-07-07T10:50:11.086642 [RLC     ] [D] [     0.0] du=0 ue=0 SRB0 UL: Refreshed status_report. ack_sn=19 n_nack=1 nack=[5]
```
* **Analysis:** 
  1. The receiver restarts `t-Reassembly` because there are still gaps (SN 19 is missing as well).
  2. `rx_highest_status` is updated to `19` (the highest status boundary up to which gaps are reported). Gaps above this (such as SN 19 itself) are deferred to prevent premature NACKs.
  3. The resulting `STATUS PDU` contains:
     * **ACK_SN:** `19` (acknowledging all received SNs up to 19, except NACKed ones).
     * **NACKs:** `5` (identifying SN 5 as missing).

#### In Real-Time Simulation:
In the live run, the OS thread timer manager triggers timer expiration asynchronously:
```text
2026-07-07T10:51:21.266857 [RLC     ] [D] du=0 ue=0 DRB1 UL: Reassembly timer expired after 20ms.
2026-07-07T10:51:21.266890 [RLC     ] [D] du=0 ue=0 DRB1 UL: Restarted t-Reassmebly. rx_next=5 rx_next_status_trigger=21 rx_highest_status=19 rx_next_highest=21
2026-07-07T10:51:21.266905 [RLC     ] [D] du=0 ue=0 DRB1 UL: Generating status PDU. rx_next=5 rx_highest_status=19 stop_sn=19
2026-07-07T10:51:21.266912 [RLC     ] [D] du=0 ue=0 DRB1 UL: Adding nack=[5].
2026-07-07T10:51:21.266940 [RLC     ] [D] du=0 ue=0 DRB1 UL: Refreshed status_report. ack_sn=19 n_nack=1 nack=[5]
```
* **Analysis:** The live simulation matches the unit test logic 1:1, verifying that the RLC AM receiver behaves correctly under real multi-threaded timer execution.

---

### Phase C: Transmitter Polling Fallback and Retransmission

#### In Real-Time Simulation (UE logs - `docs/rlc_scenario1_ue.log`):
Because proactive polling is disabled, the transmitter relies on its queue status. When it has no more data to send, it sets the poll bit (`P=1`) to prevent deadlocks:
```text
2026-07-07T10:51:21.142408 [RLC-NR ] [D] DRB1: Checking poll bit requirements for PDU. SN=5, retx=false, sdu_bytes=87, POLL_SN=0
2026-07-07T10:51:21.142409 [RLC-NR ] [D] DRB1: Setting poll bit due to empty buffers/inability to TX. SN=5, POLL_SN=0
2026-07-07T10:51:21.142410 [RLC-NR ] [I] DRB1: Started t-PollRetransmit. POLL_SN=5
```
Once the transmitter receives the `STATUS PDU` from the gNB indicating that SN 5 was NACKed, it immediately resends the packet:
```text
2026-07-07T10:51:21.268291 [RLC-NR ] [I] DRB1: Rx PDU - N bytes 3 (Control PDU)
2026-07-07T10:51:21.268295 [RLC-NR ] [D] DRB1: DRB1 Rx control PDU
2026-07-07T10:51:21.268310 [RLC-NR ] [D] DRB1: Re-transmission required for SN=5
2026-07-07T10:51:21.268315 [RLC-NR ] [I] DRB1: RETX PDU SN=5 (90 B)
```

---

## ⚖️ Key Differences Between Unit Tests and Live Runs

Below is the comparative breakdown of key system characteristics:

| Feature / Behavior | Isolated Unit Tests | Live Runtime Simulation |
| :--- | :--- | :--- |
| **Path Directionality** | **Unidirectional (UL only).** Injects PDUs directly into the RLC Rx entity in isolation. | **Bidirectional (UL and DL).** Both transmitter and receiver are active on both gNB and UE. |
| **Time Execution** | **Virtual Ticks.** Time steps are simulated by calling `tick()` manually inside the test loop. | **Real Asynchronous Timers.** Runs on standard multi-threaded CPU scheduling loops. |
| **Sequence Number sizes** | **12-bit & 18-bit.** Runs the entire suite sequentially for both RLC SN configurations. | **18-bit (DRB) & 12-bit (SRB).** Employs standard 3GPP size allocation for signaling and user planes. |
| **Transmitter Details** | **None.** Transmitter is mocked; raw PDUs are fed directly to the receiver. | **Fully Logged.** UE logs show transmitter states, poll bit fallbacks, and retransmission actions. |
| **Log Format & Tags** | Unified logs using prefix `[TEST]` for test controls and `[RLC]` for the RLC entity. | Distributed logs with gNB prefix `[RLC ]` and UE prefix `[RLC-NR]`. |
| **Latency manifestation** | **Instantaneous.** Virtual time jumps do not reflect user plane round-trip delays. | **Real Latency.** Retransmissions trigger RTT spikes from ~25ms to ~160ms on ICMP ping. |
