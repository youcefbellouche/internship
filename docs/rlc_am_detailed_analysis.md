# RLC AM Detailed Log Analysis and Cases Walkthrough

This document presents the detailed architectural analysis of RLC Acknowledged Mode (AM) state variables, receiver/transmitter buffering mechanisms, and walkthroughs of six specific sequence injection test cases.

---

## 📋 Task 1: RLC RX/TX Buffering, Reception, and Transmission Mechanisms

In RLC Acknowledged Mode (AM), data reception, buffering, and transmission are divided across the RX and TX entities:

### 1. Receiver (RX) Side:
* **Reception:** When a PDU arrives from lower layers (via `handle_pdu`), the RLC layer parses the header (SN size, polling bit, segmentation info).
  * If the PDU is a **Control PDU** (STATUS report), it is redirected immediately to the TX entity's status handler (`on_status_pdu`) to clear ACKs/NACKs.
  * If the PDU is a **Data PDU**, it checks if its sequence number (SN) is within the receive window: `rx_next <= SN < rx_next + am_window_size`. If outside, the PDU is discarded. Duplicate packet arrivals are also discarded.
* **Buffering:** If valid, the Data PDU is stored in the receive window buffer (`rx_window` using `rlc_rx_am_sdu_info`).
  * If the packet is a segment, it is buffered alongside other segments of the same SN.
* **Assembly and Delivery:**
  * Once all segments for an SN are received, the RLC layer reassembles them into a complete SDU (removing RLC headers).
  * If the reassembled SN equals `rx_next` (meaning it is the lowest missing SN in the window), it is immediately delivered to the upper layer (PDCP) via the notifier (`on_new_sdu`).
  * `rx_next` is then incremented to the next missing SN.
  * Any subsequent buffered contiguous SDUs that are now in-order are also delivered, sliding the receive window.
  * If the SN is out-of-order, it remains buffered in the window until missing sequence numbers arrive or the `t-Reassembly` timer expires.

### 2. Transmitter (TX) Side:
* **Reception:** When an SDU arrives from the upper layer (PDCP) via `handle_sdu`, it is placed in the transmit SDU queue (`tx_sdu_queue`).
* **Transmission & Buffering:**
  * When a MAC transmission opportunity (MAC grant) occurs, the RLC segmenter constructs AMD PDUs by taking SDUs from `tx_sdu_queue`, segmenting them if necessary to fit the grant size, and appending the RLC header.
  * Once transmitted to lower layers, the RLC layer keeps a copy of the AMD PDU in its transmit window buffer (`tx_window`).
* **Retransmission and Slide:**
  * The PDU remains buffered in `tx_window` until the receiver sends a `STATUS PDU`.
  * **ACK:** If the STATUS PDU acknowledges the SN (below `ack_sn` and not NACKed), it is discarded from `tx_window`, allowing the transmit window boundary `tx_next_ack` to slide forward.
  * **NACK:** If the STATUS PDU NACKs the SN, it is moved to the retransmission queue (`retx_queue`) to be sent during the next MAC opportunity. The retransmission counter for that SN (`retx_count`) is incremented.

---

## 📋 Task 2: Receiver (RX) State Transitions Upon Status Delivery

When the MAC layer requests the generated STATUS PDU for transmission via `rlc_rx_am_entity::get_status_pdu()`:

1. **Clear Status Request Trigger:** The internal trigger flag `do_status` is reset to `false`.
2. **Status Prohibit Timer:** If `t-StatusProhibit` is configured (`cfg.t_status_prohibit > 0`), the receiver starts the `status_prohibit_timer` and sets `status_prohibit_timer_is_running` to `true`. This prevents the receiver from generating another STATUS PDU until the timer expires, allowing time for the retransmitted packets to arrive.
3. **Timer Expiry Callback:** When the prohibit timer expires, `status_prohibit_timer_is_running` is cleared, permitting new status reports if a gap remains.

---

## 📋 Task 3: Transmitter (TX) State Transitions Upon Status Receipt

When the transmitter receives the STATUS report via `rlc_tx_am_entity::handle_status_pdu()`:

1. **Sanity Check:** Discards out-of-order reports if `ack_sn` is outside the current transmit window.
2. **Timer Reset:** Stops the `t-PollRetransmit` timer if the report acknowledges the packet that carried the poll bit (`poll_sn < ack_sn`).
3. **Sliding the Transmit Window:** Iterates from the oldest unacknowledged SN (`tx_next_ack`) up to the first NACKed SN. For each acknowledged SN, it:
   * Removes it from the transmit window (`tx_window.remove_sn(sn)`).
   * Advances the window boundary `tx_next_ack = sn + 1`.
   * Notifies the PDCP upper layer that the SDU has been successfully delivered (`on_delivered_sdu`).
4. **Retransmission Queue Assembly:** For each NACKed SN in the report, the transmitter:
   * Inserts the missing PDU or PDU segment into the retransmission queue (`retx_queue`).
   * Increments the retransmission counter for that sequence number (`increment_retx_count(sn)`).
5. **Max Retransmission Threshold Check:** If an SN's retransmission counter reaches the configured threshold (`cfg.max_retx_thresh`, default `32`):
   * Logs: `Reached maximum number of RETX. sn=X retx_count=Y`.
   * Calls `upper_cn.on_max_retx()`, which triggers a Radio Link Failure (RLF) at the RRC layer.
6. **Logging Clarity:** The ODU transmitter logs are highly clear during retransmission, printing:
   * `Re-transmission required. retx_queue_size=Z`
   * `Processing RETX. [Data PDU, SN=X, SO=Y]`
   * `Creating RETX PDU. SN=X si=Y retx_payload_len=Z expected_hdr_len=W grant_len=V`

---

## 📋 Task 4: Detailed Analysis of Sequence Test Cases (18-bit Config)

The following walkthroughs explain the receiver behavior under the six custom 18-bit sequence injection test cases documented in [rlc_unit_tests_cases.log](file:///root/internship-repo/docs/rlc_unit_tests_cases.log).

---

### Case 1: `0 to 4` then `6 to 8` (Double Timer Cycle & Retransmit Recovery)
* **Sequence:** `0..4`, `6..8` (Missing: `5`).
* **Test Log Snippet:**
  ```text
  [TEST    ] [I] [TX-RX Comm] [RX] Sending STATUS report. ack_sn=9, NACKs=[5]
  [TEST    ] [I] [TX-RX Comm] [TX] Sent PDU with SN=9
  [TEST    ] [I] [TX-RX Comm] [TX] Retransmitting SN 5...
  [TEST    ] [I] [TX-RX Comm] [RX] Retransmitted SN 5 dropped on channel!
  [TEST    ] [I] [TX-RX Comm] [RX] Running reassembly timer (second cycle)...
  [TEST    ] [I] [TX-RX Comm] [RX] Sending STATUS report. ack_sn=10, NACKs=[5]
  [TEST    ] [I] [TX-RX Comm] [TX] Retransmitting SN 5...
  [TEST    ] [I] [TX-RX Comm] [RX] Received PDU with SN=5
  [TEST    ] [I] [TX-RX Comm] [RX] Delivered SDUs up to SN 9. rx_next=10
  ```
* **Walkthrough:**
  1. SN `0..4` and `6..8` are transmitted, leaving a gap at `5`.
  2. Timer expires. A STATUS report NACKing `5` (`ack_sn=9`) is sent.
  3. The first retransmission of `5` is dropped on the channel. SN `9` is sent, which is out-of-order and restarts `t-Reassembly` at the receiver.
  4. Timer expires a second time. A second STATUS report NACKing `5` (`ack_sn=10`) is sent.
  5. The second retransmission of `5` is successful, filling the gap. `rx_next` slides forward to `10`.

---

### Case 2: `0 to 4` then `8, 6` (Multiple Gaps)
* **Sequence:** `0..4`, then `8`, then `6`. (Missing: `5`, `7`).
* **Test Log Snippet:**
  ```text
  [TEST    ] [I] [TX-RX Comm] [RX] Sending STATUS report. ack_sn=9, NACKs=[5, 7]
  [TEST    ] [I] [TX-RX Comm] [TX] Retransmitting SN 5...
  [TEST    ] [I] [TX-RX Comm] [TX] Retransmitting SN 7...
  [TEST    ] [I] [TX-RX Comm] [RX] Delivered SDUs up to SN 8. rx_next=9
  ```
* **Walkthrough:**
  1. SN `0..4` arrive in-order, updating `rx_next` to `5`.
  2. SN `8` arrives out of order, starting `t-Reassembly` and setting `rx_highest_status = 9`.
  3. SN `6` arrives, leaving gaps at `5` and `7`.
  4. Timer expires. Since both `5` and `7` are inside the evaluation window `[5, 9)`, the STATUS report NACKs both SNs.
  5. Retransmissions of `5` and `7` successfully arrive. `rx_next` advances to `9` (as `6` and `8` were already buffered).

---

### Case 3: `0 to 4` then `6, 8, 9, 10` (Deferred Gaps)
* **Sequence:** `0..4`, then `6, 8, 9, 10`. (Missing: `5`, `7`).
* **Test Log Snippet:**
  ```text
  [TEST    ] [I] [TX-RX Comm] [RX] Sending STATUS report. ack_sn=7, NACKs=[5] (7 deferred)
  [TEST    ] [I] [TX-RX Comm] [TX] Retransmitting SN 5...
  [TEST    ] [I] [TX-RX Comm] [RX] Running reassembly timer for SN 7...
  [TEST    ] [I] [TX-RX Comm] [RX] Sending STATUS report. ack_sn=11, NACKs=[7]
  [TEST    ] [I] [TX-RX Comm] [TX] Retransmitting SN 7...
  [TEST    ] [I] [TX-RX Comm] [RX] Delivered SDUs up to SN 10. rx_next=11
  ```
* **Walkthrough:**
  1. SN `6` arrives, starting `t-Reassembly` (`rx_highest_status = 7`).
  2. SN `8, 9, 10` arrive out of order, creating another gap at `7`. Since the timer is running, `rx_highest_status` remains `7`.
  3. Timer expires. It evaluates gaps up to `7`. Only `5` is NACKed; `7` is deferred to prevent premature NACKing of packets currently in transit.
  4. Retransmission of `5` is received, sliding `rx_next` to `7`.
  5. Since `7` is missing and `rx_next_highest` is `11` (> `rx_next + 1`), the receiver starts `t-Reassembly` for `7` (`rx_highest_status = 11`).
  6. Timer expires, NACKing `7` (`ack_sn=11`).
  7. Retransmission of `7` is received, sliding `rx_next` to `11`.

---

### Case 4: `0 to 4` then `6, 5, 8, 9, 10` (Gap Filled Before Expiry)
* **Sequence:** `0..4` followed by `6`, then `5`, then `8, 9, 10`. (Missing: `7`).
* **Test Log Snippet:**
  ```text
  [TEST    ] [I] [TX-RX Comm] [RX] Sending STATUS report. ack_sn=11, NACKs=[7]
  [TEST    ] [I] [TX-RX Comm] [TX] Retransmitting SN 7...
  [TEST    ] [I] [TX-RX Comm] [RX] Delivered SDUs up to SN 10. rx_next=11
  ```
* **Walkthrough:**
  1. SN `6` arrives, starting the timer for gap at `5` (`rx_highest_status = 7`).
  2. SN `5` arrives before the timer expires, filling the gap. `rx_next` advances to `7` and the timer is stopped.
  3. SN `8` arrives, starting the timer for gap at `7` (`rx_highest_status = 9`).
  4. SN `9` and `10` arrive, updating `rx_next_highest` to `11`.
  5. Timer expires. Only SN `7` is missing. A STATUS report NACKing `7` (`ack_sn=11`) is sent.
  6. Retransmission of `7` is received, sliding `rx_next` to `11`.

---

### Case 5: `0 to 4` then `6, 8, 5, 9, 10` (Gap Filled Out of Order Before Expiry)
* **Sequence:** `0..4` followed by `6`, then `8`, then `5`, then `9, 10`. (Missing: `7`).
* **Test Log Snippet:**
  ```text
  [TEST    ] [I] [TX-RX Comm] [RX] Sending STATUS report. ack_sn=11, NACKs=[7]
  [TEST    ] [I] [TX-RX Comm] [TX] Retransmitting SN 7...
  [TEST    ] [I] [TX-RX Comm] [RX] Delivered SDUs up to SN 10. rx_next=11
  ```
* **Walkthrough:**
  1. SN `6` starts the timer. SN `8` arrives, creating another gap at `7`.
  2. SN `5` arrives before the timer expires, resolving the gap at `5`. `rx_next` advances to the next missing packet, which is `7`.
  3. Timer expires. Gaps are evaluated up to `11` (updated by subsequent arrivals of `9, 10`).
  4. Only SN `7` is missing. A STATUS report NACKing `7` is sent.
  5. Retransmission of `7` is received, sliding `rx_next` to `11`.

---

### Case 6: `0 to 4` then `8, 5, 6, 9, 10, 12` -> Expire -> `11, 12, 13` (Gap Resolution Timing)
* **Sequence:** `0..4`, followed by `8, 5, 6, 9, 10, 12`. Expire. Then `11, 12, 13`.
* **Test Log Snippet:**
  ```text
  [TEST    ] [I] [TX-RX Comm] [RX] Sending STATUS report. ack_sn=11, NACKs=[7] (11 deferred)
  [TEST    ] [I] [TX-RX Comm] [TX] Retransmitting SN 7...
  [TEST    ] [I] [TX-RX Comm] [TX] Injecting post-expiry SNs 11, 12, 13...
  [TEST    ] [I] [TX-RX Comm] [RX] Delivered SDUs up to SN 13. rx_next=14
  ```
* **Walkthrough:**
  1. SN `8` starts the timer (`rx_highest_status = 9`).
  2. SN `5` and `6` arrive, resolving their gaps. SN `7` remains missing.
  3. SN `9, 10, 12` arrive, creating a gap at `11`. `rx_next_highest` becomes `13`.
  4. Timer expires. Gaps are evaluated up to `rx_highest_status` (which was updated to `11` due to arrivals of `9, 10`).
  5. The only gap inside `[5, 11)` is `7`. A STATUS report NACKing `7` (`ack_sn=11`) is sent. Gap `11` is deferred.
  8. Retransmission of `7` is received, sliding `rx_next` to `11` and restarting the timer for `11`.
  9. Post-expiry packets `11, 12, 13` arrive, resolving the remaining gap at `11`. `rx_next` advances to `14`.

---

## 📈 Instant Reception in Unit Tests vs. Latency in Live Runs

If RLC RX and TX entities use buffers, why do the unit test logs show that a packet is received instantly after being sent?

### 1. In Unit Tests (Synchronous Call Stack)
Unit tests run in a single-threaded, synchronous sandbox:
* The test fixture calls a helper function `inject_sn(sn)` which acts as both the "transmitter" and "channel".
* The function prints `[TX] Sent PDU with SN=X`.
* In the very next line of code, it calls `rlc->handle_pdu()` directly:
  ```cpp
  logger.info("[TX-RX Comm] [RX] Received PDU with SN={}", sn);
  rlc->handle_pdu(std::move(pdu));
  ```
* Because this is a direct, synchronous C++ function call on the same CPU thread, execution enters the receiver entity instantly. 
* Although the receiver buffers the packet in `rx_window` (out-of-order) or reassembles it immediately (in-order), the log outputs appear back-to-back because there is no virtual network delay, thread context-switching, or physical interface propagation time.

### 2. In Live Runtime Simulation (Asynchronous Communication)
In the end-to-end local ZeroMQ simulation:
* The UE and gNB processes run asynchronously on separate OS threads.
* When the UE transmitter puts a packet on the air, it serializes it and sends it over a ZeroMQ socket.
* The gNB receiver reads the packet from its ZeroMQ socket, deserializes it, and passes it to the RLC RX entity.
* This introduces real physical delays (1-3 ms propagation/scheduling delay) and queuing delays. You will see a clear timestamp gap in the live logs ([rlc_scenario1_gnb.log](file:///root/internship-repo/docs/rlc_scenario1_gnb.log)) between the transmitter queue and the receiver handler.
