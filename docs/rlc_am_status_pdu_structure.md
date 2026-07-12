# RLC AM STATUS PDU Structure and Log Traceability

This document details where and how to view the complete content and structure of RLC Acknowledged Mode (AM) `STATUS PDU` (Control reports) within the `ocudu` framework codebase and the generated test/simulation logs.

---

## 🔍 Log Files and Key Traces

You can see the structure and contents of the STATUS reports in three main log outputs:

### 1. Isolated Unit Test Logs
* **Log File:** [rlc_unit_tests_cases.log](file:///root/internship-repo/docs/rlc_unit_tests_cases.log)
* **Status Log Lines:**
  * When the RLC receiver entity refreshes its internal status report, it prints:
    ```text
    2026-07-07T12:11:56.745775 [RLC     ] [D] [     0.0] du=0 ue=0 SRB0 UL: Refreshed status_report. ack_sn=7 n_nack=1 nack=[5]
    ```
  * The custom test wrapper logs the final compiled STATUS PDU fields:
    ```text
    2026-07-07T12:11:56.745776 [TEST    ] [I] STATUS PDU: ack_sn=7, number of nacks=1
    2026-07-07T12:11:56.745776 [TEST    ] [I]   NACK: nack_sn=5
    ```

### 2. Live gNodeB RLC Logs
* **Log File:** [rlc_scenario1_gnb.log](file:///root/internship-repo/docs/rlc_scenario1_gnb.log) and [rlc_scenario2_gnb.log](file:///root/internship-repo/docs/rlc_scenario2_gnb.log)
* **Status Log Lines:**
  * **When transmitting a Status PDU:** The gNB receiver refreshes and stores the STATUS PDU, which logs the detailed structure:
    ```text
    2026-07-06T23:36:36.994162 [RLC     ] [I] du=0 ue=0 DRB1 DL: Refreshed status_report. ack_sn=1 n_nack=0
    ```
  * **When receiving a Status PDU:** The gNB transmitter logs the unpacked fields of the incoming status report sent by the UE:
    ```text
    2026-07-06T23:37:04.994905 [RLC     ] [I] du=0 ue=0 DRB1 UL: RX status PDU. ack_sn=1 n_nack=0
    ```

### 3. Live UE RLC Logs
* **Log File:** [rlc_scenario1_ue.log](file:///root/internship-repo/docs/rlc_scenario1_ue.log) and [rlc_scenario2_ue.log](file:///root/internship-repo/docs/rlc_scenario2_ue.log)
* **Status Log Lines:**
  * When receiving a status report, the UE logs:
    ```text
    2026-07-06T23:36:37.002291 [RLC-NR ] [I] DRB1: Rx PDU - N bytes 3
    2026-07-07T11:35:15.002296 [RLC-NR ] [D] DRB1: Processed status report ACKs. ACK_SN=1. Tx_Next_Ack=1
    ```

---

## 🛠️ Code Definition and Serialization Logic

The textual formatting and binary serialization of the STATUS PDU are defined inside [rlc_am_pdu.h](file:///root/internship-repo/project/ocudu/lib/rlc/rlc_am_pdu.h).

### 1. NACK Structure
The `rlc_am_status_nack` struct (lines 73–101) represents individual missing packets or missing byte segments:
* `nack_sn`: Sequence Number of the missing SDU.
* `has_so`: Boolean flag; true if only a segment is missing.
* `so_start` / `so_end`: 16-bit start and end byte offsets of the missing segment.
* `has_nack_range`: Boolean flag; true if multiple consecutive SDUs are missing.
* `nack_range`: Number of consecutive missing SDUs.

### 2. Status Report Formatter
The layout of the printed status log is defined by a custom `fmt::formatter` (lines 310–348):
* **No NACKs present:** Prints `ack_sn={value} n_nack=0`
* **NACKs present:** Appends ` nack={nack1}{nack2}...` to the ack_sn.
* **NACK formats:**
  * *Standard SDU NACK:* `[nack_sn]` (e.g. `[5]`)
  * *Segment offset NACK:* `[nack_sn so_start:so_end]` (e.g. `[5 100:250]`)
  * *SDU Range NACK:* `[nack_sn r{range}]` (e.g. `[5 r3]` NACKs SN 5, 6, and 7)
  * *Segment range NACK:* `[nack_sn so_start:so_end r{range}]`

---

## 📈 Comparing Unit Test Logs vs. Real-Time Logs

When checking the status PDU structure between unit tests and real-time simulations, look out for these format identifiers in the log files:

1. **Log Level Tag:** 
   * Unit tests use virtual tick timings: `[RLC     ] [D] [     0.0]`
   * Live gNB runs show real-time thread execution logs: `[RLC     ] [I]`
   * UE runs use srsRAN log formatting: `[RLC-NR ] [D]` or `[RLC-NR ] [I]`
2. **ACK_SN Resolution:**
   * In unit tests, `STATUS PDU: ack_sn=X` logs the next expected SN explicitly via test output prints.
   * In gNB logs, `Refreshed status_report. ack_sn=X n_nack=Y` displays the actual output of the receiver's status generator.
   * In UE logs, `RX status PDU: ACK_SN = X, N_nack = Y` confirms receipt of the report.
