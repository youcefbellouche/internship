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
   - [Advanced Protocol Layer Tuning: PDCP, RLC & MAC for TN vs NTN](#26-advanced-protocol-layer-tuning-pdcp-rlc--mac-for-tn-vs-ntn)
3. [Execution Method 1: Manual Multi-Terminal CLI (Interactive)](#3-execution-method-1-manual-multi-terminal-cli-interactive)
4. [Execution Method 2: Automated Scripting](#4-execution-method-2-automated-scripting)
5. [Testing & Traffic Verification](#5-testing--traffic-verification)
   - [Testing WITHOUT Python Scripts (Pure Linux Networking)](#51-testing-without-python-scripts-pure-linux-networking)
   - [Testing WITH Python Scripts](#52-testing-with-python-scripts)
6. [Troubleshooting & Common Gotchas](#6-troubleshooting--common-gotchas)
7. [Multi-Architecture Ground & LEO Deployment Suite](#7-multi-architecture-ground--leo-deployment-suite)
   - [Architectural Topology & Physical Rationale](#71-architectural-topology--physical-rationale)
   - [Automated Setup & Simulation Scripts](#72-automated-setup--simulation-scripts)
   - [Manual Multi-Terminal CLI Instructions](#73-manual-multi-terminal-cli-instructions)
   - [Empirical Test Results & In-Depth Failure Diagnostics](#74-empirical-test-results--in-depth-failure-diagnostics)

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

#### Code Mechanics & Result-Wise Impact of Configuration Variables:

Every configuration variable directly drives specific C++ procedures, ring buffers, ASN.1 packers, or state machines within the `ocudu` and `srsRAN` codebases. Changing any of these variables has immediate and measurable consequences on timing, protocol behavior, and network throughput.

---

##### 1. Physical Propagation Delay (`ru_sdr.device_args: rx_offset`)
* **Parameter & Default**: `rx_offset=1382400` in `device_args` (GEO: 120 ms).
* **Code Implementation**: [`project/srsRAN_4G/lib/src/phy/rf/rf_zmq_imp_rx.c`](file:///root/internship-repo/project/srsRAN_4G/lib/src/phy/rf/rf_zmq_imp_rx.c#L219-L228) (`rf_zmq_rx_read()`).
* **Code Mechanics**:
  When `rx_offset > 0`, the ZMQ radio driver pre-populates its receiver ring buffer (`q->ringbuffer`) with zeros using `srsran_vec_zero()` before reading the first incoming transmission from the network socket:
  ```c
  while (q->sample_offset > 0) {
    uint32_t n_offset = SRSRAN_MIN(q->sample_offset, NBYTES2NSAMPLES(ZMQ_MAX_BUFFER_SIZE));
    srsran_vec_zero(q->temp_buffer, n_offset);
    int n = srsran_ringbuffer_write(&q->ringbuffer, q->temp_buffer, (int)(n_offset * sample_sz));
    q->sample_offset -= n_offset;
  }
  ```
  Because subsequent read calls pull data through this ring buffer, all physical I/Q samples arriving from the UE are shifted backwards in time by exactly `rx_offset` sample slots.
* **Calculation**:
  $$\text{rx\_offset} = \text{one\_way\_delay (s)} \times f_{\text{sample}} = 0.120\text{ s} \times 11.52 \times 10^6\text{ Hz} = \mathbf{1,382,400\text{ samples}}$$
* **Result-Wise Impact When Changed**:
  * **Default (1,382,400 samples / 120 ms GEO)**: One-way propagation delay is 120 ms. Round-Trip Time (RTT) through DU2 measured by ICMP ping is $2 \times 120\text{ ms} + \text{stack processing} \approx \mathbf{257\text{ ms}}$.
  * **Emulating LEO (115,200 samples / 10 ms delay)**: Ping RTT through DU2 drops proportionally to $2 \times 10\text{ ms} + \text{processing} \approx \mathbf{36\text{ ms}}$.
  * **Emulating 1 km Terrestrial (38 samples / 3.33 µs)**: Generates sub-microsecond timing shifts, testing the DU's MAC Timing Advance (TA) commands without altering perceived IP latency ($RTT \approx 21\text{ ms}$).
  * **Failure Mode (Delay increased without matching `cell_specific_koffset`)**: If `rx_offset` is increased (e.g., to 200 ms) while `cell_specific_koffset` remains small, the DU's uplink grants expire before the UE's PUSCH bursts arrive over the delayed ZMQ pipe. The DU drops the late bursts, causing 100% uplink packet loss.

---

##### 2. MAC/PHY Scheduling Offset (`cell_cfg.ntn.cell_specific_koffset`)
* **Parameter & Default**: `cell_specific_koffset: 150` (150 ms = 150 slots at 15 kHz SCS).
* **Code Implementation**:
  * Unit conversion: [`project/ocudu/lib/scheduler/config/cell_configuration.cpp`](file:///root/internship-repo/project/ocudu/lib/scheduler/config/cell_configuration.cpp#L54-L57):
    $$\text{ntn\_cs\_koffset} = \text{cell\_specific\_koffset} \times \text{nof\_slots\_per\_subframe}(\mu)$$
  * PUCCH allocation: [`project/ocudu/lib/scheduler/pucch_scheduling/pucch_allocator_impl.cpp`](file:///root/internship-repo/project/ocudu/lib/scheduler/pucch_scheduling/pucch_allocator_impl.cpp#L194):
    $$\text{pucch\_slot} = \text{slot}_{\text{tx}} + K_0 + K_1 + \text{ntn\_cs\_koffset}$$
  * PUSCH allocation: [`project/ocudu/lib/scheduler/ue_scheduling/ue_fallback_scheduler.cpp`](file:///root/internship-repo/project/ocudu/lib/scheduler/ue_scheduling/ue_fallback_scheduler.cpp#L986):
    $$\text{pusch\_slot} = \text{pdcch\_slot} + K_2 + \text{ntn\_cs\_koffset}$$
  * Contention Resolution Timer: [`project/ocudu/lib/scheduler/ue_scheduling/ue_fallback_scheduler.cpp`](file:///root/internship-repo/project/ocudu/lib/scheduler/ue_scheduling/ue_fallback_scheduler.cpp#L1397):
    $$\text{conres\_timer\_slots} = \text{conres\_timer} \times \text{slots\_per\_subframe} + \text{ntn\_cs\_koffset}$$
  * Ring buffer memory sizing: [`project/ocudu/lib/scheduler/cell/resource_grid.cpp`](file:///root/internship-repo/project/ocudu/lib/scheduler/cell/resource_grid.cpp#L358):
    Resizes internal ring buffers to `RING_MAX_HISTORY_SIZE + max_slot_ul_alloc_delay(ntn_cs_koffset)`.
* **Result-Wise Impact When Changed**:
  * **Optimal Setting (`150`)**: Provides the necessary slot margin ($\ge 120\text{ ms}$) so that when the DU sends a PDCCH grant at slot $n$, the UE receives the DCI over the 120 ms downlink, processes it, and transmits its PUSCH / PUCCH burst so that it arrives at the DU at slot $n + K + 150$. Contention resolution and HARQ feedback align with arrival times.
  * **Value Too Low (< 120, e.g., 0 or 20)**:
    1. **Expired Grants**: The UE receives DCI scheduling uplink grants for slots that have already passed in the past. The UE logs `[WARN] Uplink grant past due` and drops the grant. Uplink transmission stalls completely.
    2. **Premature PUCCH Listening**: The DU expects HARQ ACK/NACK at slot $n + K_0 + K_1 + \text{koffset}$. Because `koffset` is too small, the DU listens for the PUCCH burst before the signal has physically reached the antenna/ZMQ buffer. The DU records `PUCCH DTX` (Discontinuous Transmission), treats it as NACK, and triggers redundant retransmissions.
    3. **RACH Failure**: Contention Resolution timer expires before Msg4 can be acknowledged by the UE, causing the UE to declare RACH failure and disconnect.
  * **Value Too High (> 300 for 120 ms delay)**: Adds unnecessary idle latency to all uplink grants. PUSCH transmissions are scheduled hundreds of milliseconds later than necessary, bloating the scheduler's ring buffer memory and reducing effective uplink throughput.

---

##### 3. Common Timing Advance (`cell_cfg.ntn.ta_info.ta_common`)
* **Parameter & Default**: `ta_common: 0` (nested under `ta_info:`).
* **Code Implementation**:
  * CLI11 parsing: [`project/ocudu/apps/units/flexible_o_du/o_du_high/du_high/ntn/du_high_ntn_config_cli11_schema.cpp`](file:///root/internship-repo/project/ocudu/apps/units/flexible_o_du/o_du_high/du_high/ntn/du_high_ntn_config_cli11_schema.cpp#L330).
  * SIB19 ASN.1 serialization: [`project/ocudu/lib/du/du_high/du_manager/converters/asn1_ntn_config_helpers.cpp`](file:///root/internship-repo/project/ocudu/lib/du/du_high/du_manager/converters/asn1_ntn_config_helpers.cpp#L101):
    $$\text{ta\_common\_r17} = \left\lfloor \frac{\text{ta\_common}}{0.004072\,\mu\text{s}} \right\rfloor$$
* **Code Mechanics**:
  In 3GPP Rel-17 NTN, `ta_common` communicates the network-controlled common delay (feeder link delay from gateway to satellite) broadcast via SIB19. The UE subtracts $2 \times T_{\text{common}}$ from its transmission timing to pre-compensate uplink signals before PRACH and PUSCH.
* **Result-Wise Impact When Changed**:
  * **In ZMQ Emulation (`ta_common: 0`)**: The entire delay is placed in the virtual RF channel (`rx_offset`). The DU's PRACH receiver expects preambles to arrive matching the nominal ZMQ buffering window.
  * **Setting `ta_common` to a Non-Zero Value (e.g., 5000 µs)**: The UE advances its PRACH preamble transmission by $5\text{ ms}$. In our simulated loopback, this pre-advance shifts the received preamble ahead of the DU's FFT correlation window. The DU logs `No RACH preamble detected`, completely preventing the UE from attaching to DU2.

---

##### 4. Satellite Ephemeris & Orbit Coordinates (`epoch_timestamp` and `ephemeris_info_ecef`)
* **Parameter & Default**:
  ```yaml
  epoch_timestamp: "2026-01-01T00:00:00"
  ephemeris_info_ecef:
    pos_x: 20922195
    pos_y: 1967783
    pos_z: 19770302
    vel_x: 0
    vel_y: 0
    vel_z: 0
  ```
* **Code Implementation**:
  * ASN.1 SIB19 encoding: [`project/ocudu/lib/du/du_high/du_manager/converters/asn1_ntn_config_helpers.cpp`](file:///root/internship-repo/project/ocudu/lib/du/du_high/du_manager/converters/asn1_ntn_config_helpers.cpp#L137-L142):
    ```cpp
    rv.position_x_r17  = static_cast<int32_t>(pos_vel->position_x / 1.3);   // 1.3 m scale
    rv.velocity_vx_r17 = static_cast<int32_t>(pos_vel->velocity_vx / 0.06);  // 0.06 m/s scale
    ```
  * Doppler calculation: [`project/ocudu/lib/ntn/ntn_configuration_manager_impl.cpp`](file:///root/internship-repo/project/ocudu/lib/ntn/ntn_configuration_manager_impl.cpp#L91):
    $$f_D = \frac{\vec{v} \cdot \vec{r}}{c \|\vec{r}\|} \cdot f_c$$
* **Result-Wise Impact When Changed**:
  * **Geostationary Orbit (`vel = [0, 0, 0]`)**: In Earth-Centered Earth-Fixed (ECEF) coordinates, a GEO satellite remains fixed over the equator. Because velocity is zero, Doppler shift is $0\text{ Hz}$. The UE applies no carrier frequency pre-compensation, maintaining subcarrier orthogonality.
  * **Simulating LEO (Non-Zero Velocity, e.g., $7,500\text{ m/s}$)**: SIB19 broadcasts the satellite velocity vector. The UE calculates the relative line-of-sight vector to its GNSS position and pre-shifts its transmitter frequency by $-f_D$ (up to $\pm 40\text{ kHz}$ at Band 3).
  * **Failure Mode (Omitting or Misplacing `ephemeris_info_ecef`)**: If placed at root without the `ephemeris_info_ecef:` wrapper, the CLI11 parser fails immediately on startup: `INI was not able to parse cell_cfg.ntn.pos_x`. If SIB19 is broadcast with invalid coordinates, the UE cannot compute satellite elevation and rejects the cell during SIB19 decoding.

---

##### 5. MAC HARQ Retransmission Deactivation (`max_nof_harq_retxs: 0`)
* **Parameter & Default**: `max_nof_harq_retxs: 0` under `pdsch:` and `max_msg3_harq_retx: 0` under `prach:`.
* **Code Implementation**: [`project/ocudu/lib/scheduler/cell/cell_harq_manager.cpp`](file:///root/internship-repo/project/ocudu/lib/scheduler/cell/cell_harq_manager.cpp#L354-L388) (`handle_ack()`):
  ```cpp
  if (ack or h.nof_retxs >= h.max_nof_harq_retxs) {
    // Immediate deallocation: free HARQ ID back to allocator
    dealloc_harq(h);
  } else {
    // Retransmission queueing: process remains blocked
    set_pending_retx(h);
  }
  ```
* **Result-Wise Impact When Changed**:
  * **HARQ Disabled (`max_nof_harq_retxs: 0`)**: As soon as a Transport Block is transmitted, `h.nof_retxs >= 0` is immediately true. The scheduler instantly calls `dealloc_harq(h)` and returns the HARQ ID to `ue_harq_entity.free_harq_ids`.
    * **Why this is critical**: Packets are never held in a pending retransmission state. Reliability is offloaded to RLC Acknowledged Mode (AM) sliding windows, which can accommodate the 250 ms delay without blocking.
  * **Enabling HARQ Retransmissions (`max_nof_harq_retxs: 4`, standard terrestrial)**:
    1. **Head-of-Line (HoL) Blocking**: If a packet is lost or corrupted over the satellite link, `set_pending_retx(h)` blocks the HARQ process for the duration of the round trip (250 ms).
    2. **Process Starvation**: Standard 5G NR provides only 16 (or 32 in NTN) HARQ processes. At a 1 ms slot rate, all 32 HARQ IDs are consumed within 32 ms. With all processes blocked waiting for 250 ms round-trip feedback, `free_harq_ids` empties completely.
    3. **Throughput Collapse**: The scheduler cannot schedule any new downlink or uplink data, freezing user-plane throughput until HARQ timers expire.

---

##### 6. SIB Scheduling & Window Rules (`si_sched_info` and `si_window_position`)
* **Parameter & Default**:
  ```yaml
  sib:
    si_window_length: 5
    si_sched_info:
      - si_period: 16
        sib_mapping: [2]
      - si_period: 16
        sib_mapping: [19]
        si_window_position: 2
  ```
* **Code Implementation**: [`project/ocudu/apps/units/flexible_o_du/o_du_high/du_high/du_high_config_validator.cpp`](file:///root/internship-repo/project/ocudu/apps/units/flexible_o_du/o_du_high/du_high/du_high_config_validator.cpp#L1160-L1233).
* **Validation Rules & Exact Failure Modes**:
  1. **Rule 1 (SIB19 Requires Explicit Window Position)**:
     ```cpp
     if (sib_it >= r17_min_sib_type && !si_msg.si_window_position.has_value()) {
       fmt::print("The SIB{} must be configured with SI-window position.\n", sib_it);
       return false;
     }
     ```
     *Impact*: Omitting `si_window_position` on SIB19 causes the DU process to abort immediately during configuration validation.
  2. **Rule 2 (Base SIB < 15 Required)**:
     ```cpp
     if (n_sched_info_list_messages == 0) {
       fmt::print("The SIB{} (ID >= 15) requires at least one SIB with ID < 15 to be present; "
                  "otherwise si-WindowLength will not be included.\n", sib_it);
       return false;
     }
     ```
     *Impact*: Configuring SIB19 without scheduling SIB2 causes DU initialization to fail because 3GPP Rel-15 `SchedulingInfoList` must define the transmission structure before Rel-17 `SchedulingInfoList2` can be broadcast.
  3. **Rule 3 (Window Position Ordering)**:
     ```cpp
     if (!si_window_positions.empty() && (si_window_positions[0] <= n_sched_info_list_messages)) {
       fmt::print("Any SI element in schedulingInfoList2 must be scheduled after any SI in schedulingInfoList ({}<={})\n",
                  si_window_positions[0], n_sched_info_list_messages);
       return false;
     }
     ```
     *Impact*: Setting `si_window_position: 1` for SIB19 causes DU startup failure with `(1 <= 1)`. SIB19 must be assigned `si_window_position: 2` so it transmits in the SI window immediately following SIB2.
  4. **Rule 4 (No Co-Scheduling)**:
     ```cpp
     fmt::print("SIB19 cannot be included in the SI messages together with other SIBs.\n");
     ```
     *Impact*: Putting `sib_mapping: [2, 19]` in a single message entry fails validation. SIB19 must exist in its own dedicated SI message.

---

##### 7. PUCCH Scheduling Request Periodicity (`pucch.sr_period_ms: 320`)
* **Parameter & Default**: `sr_period_ms: 320` in `endc_du2_geo.yml` (Terrestrial DU1 uses standard `sr_period_ms: 40`).
* **Code Implementation**: [`project/ocudu/lib/scheduler/pucch_scheduling/pucch_resource_manager.cpp`](file:///root/internship-repo/project/ocudu/lib/scheduler/pucch_scheduling/pucch_resource_manager.cpp).
* **Result-Wise Impact When Changed**:
  * **Satellite Adaptation (`320 ms`)**: Sets the physical PUCCH Scheduling Request opportunity interval to 320 ms. On a GEO satellite channel with a 250 ms RTT, frequent SR opportunities (e.g., every 5 ms) are unhelpful because the UE cannot react to grant round trips within short intervals. 320 ms drastically conserves satellite uplink carrier bandwidth and reduces interference.
  * **Short Interval (e.g., `10 ms`)**: Wastes significant uplink PRB resources scheduling empty PUCCH Format 0/1 allocations for inactive UEs.

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

#### Code Mechanics & Result-Wise Impact of Control Plane Variables:

##### 1. RRC Procedure Guard Time (`cu_cp.rrc.rrc_procedure_guard_time_ms`)
* **Parameter & Default**: `rrc_procedure_guard_time_ms: 12800` (12.8 seconds). Terrestrial default in `ocudu` is `1000` ms (1 second).
* **Code Implementation**:
  * Config translation: [`project/ocudu/apps/units/o_cu_cp/cu_cp/cu_cp_config_translators.cpp`](file:///root/internship-repo/project/ocudu/apps/units/o_cu_cp/cu_cp/cu_cp_config_translators.cpp#L442).
  * Procedure timeouts:
    * RRC Setup: [`project/ocudu/lib/rrc/ue/procedures/rrc_setup_procedure.cpp`](file:///root/internship-repo/project/ocudu/lib/rrc/ue/procedures/rrc_setup_procedure.cpp#L39):
      $$\text{procedure\_timeout} = T_{300} + \text{rrc\_procedure\_guard\_time\_ms}$$
    * RRC Reconfiguration (SgNB Addition): [`project/ocudu/lib/rrc/ue/procedures/rrc_reconfiguration_procedure.cpp`](file:///root/internship-repo/project/ocudu/lib/rrc/ue/procedures/rrc_reconfiguration_procedure.cpp#L26):
      $$\text{procedure\_timeout} = T_{311} + \text{rrc\_procedure\_guard\_time\_ms}$$
    * UE Capability Transfer: [`project/ocudu/lib/rrc/ue/procedures/rrc_ue_capability_transfer_procedure.cpp`](file:///root/internship-repo/project/ocudu/lib/rrc/ue/procedures/rrc_ue_capability_transfer_procedure.cpp#L20):
      $$\text{procedure\_timeout} = \text{rrc\_procedure\_guard\_time\_ms}$$
* **Code Mechanics**:
  When CU-CP initiates a signaling transaction with the UE (such as generating an `RRCReconfiguration` message to add DU2 as the Secondary Node), it starts an asynchronous guard timer. The procedure expects an `RRCReconfigurationComplete` message from the UE before this timer ticks to zero.
* **Result-Wise Impact When Changed**:
  * **Working Value (`12800` ms / 12.8 s)**: Accommodates multi-hop F1-C transport, 120 ms downlink propagation, ASN.1 PDU decoding and radio reconfiguration at the UE, 120 ms uplink propagation, and F1AP processing overhead. Procedures conclude cleanly with state `COMPLETED`.
  * **Terrestrial Default (`1000` ms / 1.0 s)**:
    * Under loaded conditions or when large UE Capability Information containers are exchanged over the satellite link, the round trip often exceeds 1,000 ms.
    * **Failure Mode**: The guard timer fires prematurely in CU-CP. The procedure logs `[ERROR] [RRC] Procedure RRC Reconfiguration timed out`. CU-CP drops the SgNB Addition procedure and sends an F1AP `UE CONTEXT RELEASE COMMAND` to DU2. The secondary leg fails to attach, leaving the UE on Single Connectivity (MN only).

---

##### 2. Session Inactivity Teardown Timer (`cu_cp.inactivity_timer`)
* **Parameter & Default**: `inactivity_timer: 7200` (7,200 seconds = 2 hours). Default in `ocudu` is `120` seconds (2 minutes).
* **Code Implementation**:
  * E1AP negotiation: [`project/ocudu/apps/units/o_cu_cp/cu_cp/cu_cp_config_translators.cpp`](file:///root/internship-repo/project/ocudu/apps/units/o_cu_cp/cu_cp/cu_cp_config_translators.cpp#L459): passes `inactivity_timer` in E1AP `BearerContextSetupRequest`.
  * CU-UP timer expiration: [`project/ocudu/lib/cu_up/ue_context.h`](file:///root/internship-repo/project/ocudu/lib/cu_up/ue_context.h#L99-L102,L221):
    ```cpp
    ue_inactivity_timer.set(*cfg.ue_inactivity_timeout,
                            [this](timer_id_t) { on_ue_inactivity_timer_expired(); });
    ```
  * Notification dispatch: [`project/ocudu/lib/cu_up/ue_context.h`](file:///root/internship-repo/project/ocudu/lib/cu_up/ue_context.h#L224):
    When no user-plane packets traverse the SDAP/PDCP entity for `inactivity_timer` seconds, CU-UP dispatches `e1ap_bearer_context_inactivity_notification` to CU-CP.
  * Teardown routine: CU-CP responds to the inactivity notification by sending F1AP `UE CONTEXT RELEASE COMMAND` (cause: `user-inactivity`), which tears down DRB1 on both DU1 and DU2 and commands the UE to go to RRC Idle.
* **Result-Wise Impact When Changed**:
  * **Extended Value (`7200` s)**: 7,200 seconds is the absolute maximum value supported by the 3GPP E1AP ASN.1 schema. This keeps DRB1 and F1-U tunnel bindings alive for two full hours of idle time, allowing developers to run tests, inspect logs, and switch terminals without unexpected disconnects.
  * **Default Value (`120` s)**: If no ping or UDP packet flows across `tun_srsue` for 2 minutes, CU-UP fires `on_ue_inactivity_timer_expired()`. The gNB tears down the bearer. Any subsequent terminal command (e.g., a ping run 3 minutes after UE startup) immediately fails with `Destination Host Unreachable` or silent packet drop until the UE is power-cycled.

---

### 2.3 `endc_du1.yml` (Terrestrial Node)
File location: [`project/ocudu/configs/endc_du1.yml`](file:///root/internship-repo/project/ocudu/configs/endc_du1.yml)

Operates on ZMQ ports `2000/2001`, `PCI=1`, `gnb_du_id=1` with standard zero-delay parameters. Acts as the Master Node (MN) anchoring the RRC connection and primary user data leg.

---

### 2.4 `endc_cu_up.yml` (User Plane Node)
File location: [`project/ocudu/configs/endc_cu_up.yml`](file:///root/internship-repo/project/ocudu/configs/endc_cu_up.yml)

Manages the SDAP/PDCP user plane and bridges F1-U (`127.0.10.1`) with the N3 GTP-U core interface (`127.0.0.1`). Coordinates bearer splitting and security deciphering between MN and SN legs.

---

### 2.5 `ue_mn.conf`, `ue_sn.conf`, & Traffic Splitting
* **Master Leg (`project/ue_mn.conf`)**:
  Connects to DU1 (ZMQ `tx_port=tcp://127.0.0.1:2001,rx_port=tcp://127.0.0.1:2000`). Anchors the Linux network namespace and tunnel device:
  ```ini
  [gw]
  netns = ue_mn
  ip_devname = tun_srsue
  ```
* **Secondary Leg (`project/ue_sn.conf`)**:
  Connects to DU2 (ZMQ `tx_port=tcp://127.0.0.1:3001,rx_port=tcp://127.0.0.1:3000`).

#### Code Mechanics & Result-Wise Impact of Traffic Splitting (`PDCP_SPLIT_RATIO`):
* **Environment Variable**: `export PDCP_SPLIT_RATIO="N:M"` (e.g., `"2:7"`).
* **Code Implementation**: [`project/srsRAN_4G/lib/include/srsran/upper/pdcp.h`](file:///root/internship-repo/project/srsRAN_4G/lib/include/srsran/upper/pdcp.h#L36-L88) (`rlc_split_bridge`):
  ```cpp
  void write_sdu(uint32_t lcid, srsran::unique_byte_buffer_t sdu) override
  {
    // Signaling Radio Bearers (SRB0, SRB1, SRB2) ALWAYS stay on Terrestrial Master Node
    if (lcid < 3) {
      if (mn_rlc) mn_rlc->write_sdu(lcid, std::move(sdu));
      return;
    }

    if (!parsed) parse_ratio();

    static std::atomic<uint32_t> packet_counter{0};
    bool mn_full = mn_rlc ? mn_rlc->sdu_queue_is_full(lcid) : true;
    bool sn_full = sn_rlc ? sn_rlc->sdu_queue_is_full(lcid) : true;

    uint32_t count = packet_counter++ % total_ratio;
    bool route_to_mn = (count < ratio_mn);

    // Active backpressure steering
    if ((route_to_mn && !mn_full) || sn_full) {
      if (mn_rlc) mn_rlc->write_sdu(lcid, std::move(sdu));
    } else {
      if (sn_rlc) sn_rlc->write_sdu(lcid, std::move(sdu));
    }
  }
  ```
* **Result-Wise Impact When Changed**:
  * **Signaling Integrity (`lcid < 3`)**: Control signaling (RRC Reconfigurations, Measurements, NAS) is strictly locked to `mn_rlc` (DU1). It is never sent over the delayed satellite leg, shielding critical control procedures from satellite packet delay or drop.
  * **Ratio `"2:7"` (Default Test Configuration)**:
    * For every $2 + 7 = 9$ user-plane data packets (DRBs, `lcid >= 3`), 2 packets (22.2%) are dispatched via DU1 (terrestrial) and 7 packets (77.8%) are dispatched via DU2 (satellite).
    * When running ping tests, 2 out of 9 pings show terrestrial latency ($\approx 21\text{--}24\text{ ms}$), and 7 out of 9 pings show satellite latency ($\approx 255\text{--}258\text{ ms}$).
  * **Ratio `"1:1"` (Balanced Alternation)**: Packets strictly alternate: 1 packet to DU1, 1 packet to DU2. Verified in pings as alternating fast/slow response pairs.
  * **Ratio `"1:0"` (Pure Terrestrial Routing)**: 100% of user data routes through DU1. DU2 remains connected as a warm standby secondary leg, but carries zero user-plane traffic. All pings report $\approx 21\text{ ms}$.
  * **Ratio `"0:1"` (Pure Satellite Routing)**: 100% of user data routes through DU2. All pings report $\approx 257\text{ ms}$.
  * **Backpressure Overload Protection (`sn_full / mn_full`)**: If the satellite RLC SDU buffer fills up (`sn_full == true`) due to high bandwidth or delayed acknowledgements, the condition `(route_to_mn && !mn_full) || sn_full` evaluates to `true`, instantly diverting subsequent packets to the terrestrial MN leg and preventing user packet drop.

---

### 2.6 Advanced Protocol Layer Tuning: PDCP, RLC & MAC for TN vs NTN

This section provides a consolidated reference for tuning the protocol stack timers, thresholds, and multi-connectivity modes across the PDCP, RLC, and MAC layers. These parameters can be customized directly in the YAML configuration files without modifying C++ source code.

#### How to Apply These Settings:
* **Option A (Direct in Node Configs)**: Embed the `qos:` and `cell_cfg:` YAML blocks directly into [`endc_du1.yml`](file:///root/internship-repo/project/ocudu/configs/endc_du1.yml), [`endc_du2_geo.yml`](file:///root/internship-repo/project/ocudu/configs/endc_du2_geo.yml), or [`endc_cu_cp_geo.yml`](file:///root/internship-repo/project/ocudu/configs/endc_cu_cp_geo.yml).
* **Option B (Modular Config Argument)**: Pass the standalone template file [`project/ocudu/configs/qos.yml`](file:///root/internship-repo/project/ocudu/configs/qos.yml) as a secondary argument when launching nodes:
  ```bash
  sudo /root/internship-repo/project/ocudu/build/apps/du/odu -c /root/internship-repo/project/ocudu/configs/endc_du2_geo.yml -c /root/internship-repo/project/ocudu/configs/qos.yml --gnb_du_id 2
  ```

---

#### 1. PDCP Layer Tuning (CU-CP, CU-UP & UE)

##### A. `--pdcpMode` (Multi-Connectivity Traffic Steering Strategy)
* **Description**: Dictates how user-plane PDCP Data PDUs (DRBs, `lcid >= 3`) are routed across the dual legs (Terrestrial Master Node DU1 vs Satellite Secondary Node DU2).
* **Where to Change**:
  * **UE Stack**: Configured via shell environment variable before launching the monolithic UE stack:
    ```bash
    export PDCP_SPLIT_RATIO="2:7"   # Split ratio: 2 packets via DU1, 7 packets via DU2
    export PDCP_SPLIT_RATIO="1:0"   # Primary path only (100% Terrestrial DU1)
    export PDCP_SPLIT_RATIO="0:1"   # Secondary path only (100% Satellite DU2)
    export PDCP_SPLIT_RATIO="1:1"   # Balanced 50/50 round-robin alternation
    ```
  * **Code Implementation**: [`project/srsRAN_4G/lib/include/srsran/upper/pdcp.h`](file:///root/internship-repo/project/srsRAN_4G/lib/include/srsran/upper/pdcp.h#L36-L88) (`class rlc_split_bridge`). Control signaling (SRB0, SRB1, SRB2, `lcid < 3`) is strictly pinned to the terrestrial master leg (`mn_rlc`).

##### B. `t-Reordering` Timer (PDCP Reordering Window)
* **Formula**:
  $$t_{\text{reordering}} \ge \max(\text{RLC\_MAX\_RETX} \times \text{RLC\_t-reassembly}, \Delta\tau_{\text{path}})$$
* **Description**: Prevents premature out-of-order delivery to upper IP layers when packets arriving over the terrestrial path ($21\text{ ms}$) arrive significantly earlier than packets sent over the satellite path ($257\text{ ms}$).
* **Where to Change**: Configured under `qos[].pdcp.rx.t_reordering` in [`project/ocudu/configs/endc_cu_cp_geo.yml`](file:///root/internship-repo/project/ocudu/configs/endc_cu_cp_geo.yml) or [`project/ocudu/configs/qos.yml`](file:///root/internship-repo/project/ocudu/configs/qos.yml).
* **Code Implementation & Validator**:
  * Enum definition: [`project/ocudu/include/ocudu/ran/pdcp/pdcp_t_reordering.h`](file:///root/internship-repo/project/ocudu/include/ocudu/ran/pdcp/pdcp_t_reordering.h#L15-L53)
  * CU-CP validator: [`project/ocudu/apps/units/o_cu_cp/cu_cp/cu_cp_unit_config_validator.cpp`](file:///root/internship-repo/project/ocudu/apps/units/o_cu_cp/cu_cp/cu_cp_unit_config_validator.cpp#L431)
* **Valid 3GPP Discrete Steps (ms)**:
  `0, 1, 2, 4, 5, 8, 10, 15, 20, 30, 40, 50, 60, 80, 100, 120, 140, 160, 180, 200, 220, 240, 260, 280, 300, 500, 750, 1000, 1250, 1500, 1750, 2000, 2250, 2500, 2750, 3000, -1 (infinity)`.
* **Recommended Settings**:
  * **Terrestrial Leg (TN)**: $\text{Retx}=4, \text{t-reassembly}=15\text{ ms} \implies 4 \times 15 = 60\text{ ms} \implies \mathbf{60\text{ ms}}\text{ or }\mathbf{80\text{ ms}}$.
  * **GEO Satellite Leg (NTN)**: $\text{Retx}=4, \text{t-reassembly}=120\text{ ms} \implies 4 \times 120 = 480\text{ ms} \implies \mathbf{500\text{ ms}}\text{ or }\mathbf{1000\text{ ms}}$.
* **YAML Syntax**:
  ```yaml
  qos:
    - five_qi: 9
      pdcp:
        rx:
          t_reordering: 500
  ```

---

#### 2. RLC Layer Tuning (Configured per DU for TN vs NTN)

Each DU independently configures its RLC Acknowledged Mode (AM) transmit and receive entities.

* **Where to Change**: In [`project/ocudu/configs/endc_du1.yml`](file:///root/internship-repo/project/ocudu/configs/endc_du1.yml) (Terrestrial DU1) and [`project/ocudu/configs/endc_du2_geo.yml`](file:///root/internship-repo/project/ocudu/configs/endc_du2_geo.yml) (GEO Satellite DU2).
* **Code References**:
  * CLI11 Schema: [`project/ocudu/apps/units/flexible_o_du/o_du_high/du_high/du_high_config_cli11_schema.cpp`](file:///root/internship-repo/project/ocudu/apps/units/flexible_o_du/o_du_high/du_high/du_high_config_cli11_schema.cpp#L2573-L2597)
  * DU Validator: [`project/ocudu/apps/units/flexible_o_du/o_du_high/du_high/du_high_config_validator.cpp`](file:///root/internship-repo/project/ocudu/apps/units/flexible_o_du/o_du_high/du_high/du_high_config_validator.cpp#L50-L130)
  * Automatic NTN RLC Adaptation: [`project/ocudu/apps/units/flexible_o_du/o_du_high/du_high/ntn/du_high_ntn_config_translators.cpp`](file:///root/internship-repo/project/ocudu/apps/units/flexible_o_du/o_du_high/du_high/ntn/du_high_ntn_config_translators.cpp#L16-L34)

##### Parameter Breakdown:
1. **`t-poll-retransmit`** ($2.5 \times \tau_{\text{prop}}$):
   * **Role**: Timer guarding transmitter poll bit retransmissions.
   * **Valid 3GPP values (ms)**: `5, 10, 15, ..., 200, 250, 300, 350, 400, 450, 500, 800, 1000, 2000, 4000`.
   * **TN (3 ms delay)**: $2.5 \times 3 = 7.5\text{ ms} \implies \mathbf{10\text{ ms}}$ (or `15 ms`).
   * **NTN GEO (120 ms delay)**: $2.5 \times 120 = 300\text{ ms} \implies \mathbf{300\text{ ms}}$ or $\mathbf{400\text{ ms}}$. *(Note: `ocudu` automatically clamps this to $\ge 400\text{ ms}$ for GEO).*
2. **`rlcAmStatusProhibitMs` (`t-status-prohibit`)** ($2.5 \times \tau_{\text{prop}}$):
   * **Role**: Prohibits receiver from generating excessive RLC STATUS reports.
   * **Valid 3GPP values (ms)**: `0, 5, 10, 15, ..., 200, 250, 300, 350, 400, ..., 2400`.
   * **TN (3 ms delay)**: $2.5 \times 3 = 7.5\text{ ms} \implies \mathbf{10\text{ ms}}$.
   * **NTN GEO (120 ms delay)**: $2.5 \times 120 = 300\text{ ms} \implies \mathbf{300\text{ ms}}$.
3. **`rlcAmPollPdu` (`poll-pdu`)** (Maximum):
   * **Role**: Triggers poll bit insertion every $N$ PDUs.
   * **Setting**: Set to **`-1`** for infinity (maximum / no PDU limit; polls only when transmit buffer is empty). Maximum finite value is **`65536`**.
4. **`rlcAmPollByte` (`poll-byte`)** (Maximum):
   * **Role**: Triggers poll bit insertion every $N$ kilobytes.
   * **Setting**: Set to **`-1`** for infinity (maximum / no byte limit). Maximum finite value is **`40000`** ($40\text{ MB}$).
5. **`rlcAmMaxRetxThreshold` (`max-retx-threshold`)** (Set to `4`):
   * **Role**: Maximum consecutive retransmissions of an RLC PDU before declaring Radio Link Failure (RLF).
   * **Valid 3GPP values**: `1, 2, 3, 4, 6, 8, 16, 32`.
   * **Setting**: **`4`**.
6. **`t-Reassembly` (`t-reassembly`)**:
   * **Role**: Timer used by receiver to detect lost RLC PDUs before advancing receive window.
   * **Valid 3GPP values (ms)**: `0, 5, 10, 15, 20, 25, 30, ..., 200`.
   * **Settings**:
     * **NTN GEO with HARQ = 0**: Set to **`15`** (or `20 ms`).
     * **TN with HARQ enabled ($3\text{ ms}$ delay)**: $4 \times 3 = 12\text{ ms} \implies \mathbf{15\text{ ms}}$ (or `20 ms`).
     * **NTN if HARQ were enabled ($120\text{ ms}$ delay)**: $4 \times 120 = 480\text{ ms} \implies$ clamped to max 3GPP enum **`200 ms`**.

---

#### 3. MAC Layer Tuning: HARQ Retransmissions per DU

* **Where to Change**: Under `cell_cfg:` in [`project/ocudu/configs/endc_du1.yml`](file:///root/internship-repo/project/ocudu/configs/endc_du1.yml) and [`project/ocudu/configs/endc_du2_geo.yml`](file:///root/internship-repo/project/ocudu/configs/endc_du2_geo.yml).
* **Code Implementation**: [`project/ocudu/apps/units/flexible_o_du/o_du_high/du_high/du_high_config_cli11_schema.cpp`](file:///root/internship-repo/project/ocudu/apps/units/flexible_o_du/o_du_high/du_high/du_high_config_cli11_schema.cpp#L302,L869) and [`project/ocudu/lib/scheduler/cell/cell_harq_manager.cpp`](file:///root/internship-repo/project/ocudu/lib/scheduler/cell/cell_harq_manager.cpp#L354-L388).

##### Configuration Profiles:
* **Terrestrial DU1 ([`endc_du1.yml`](file:///root/internship-repo/project/ocudu/configs/endc_du1.yml))**:
  ```yaml
  cell_cfg:
    pdsch:
      max_nof_harq_retxs: 4      # 4 DL HARQ retransmissions
    pusch:
      max_nof_harq_retxs: 4      # 4 UL HARQ retransmissions
    prach:
      max_msg3_harq_retx: 4      # 4 Msg3 HARQ retransmissions
  ```
* **Satellite NTN DU2 ([`endc_du2_geo.yml`](file:///root/internship-repo/project/ocudu/configs/endc_du2_geo.yml))**:
  ```yaml
  cell_cfg:
    pdsch:
      max_nof_harq_retxs: 0      # Disabled to prevent 250 ms HoL blocking
    pusch:
      max_nof_harq_retxs: 0      # Disabled
    prach:
      max_msg3_harq_retx: 0      # Disabled
  ```

---

#### 4. Ready-to-Paste Configuration Templates

##### For Terrestrial Master DU1 ([`endc_du1.yml`](file:///root/internship-repo/project/ocudu/configs/endc_du1.yml)):
```yaml
qos:
  - five_qi: 9
    rlc:
      mode: am
      am:
        tx:
          sn: 18
          t-poll-retransmit: 10     # 2.5 * 3 ms prop delay
          max-retx-threshold: 4     # Max 4 RLC retransmissions
          poll-pdu: -1              # Infinity (maximum)
          poll-byte: -1             # Infinity (maximum)
        rx:
          sn: 18
          t-reassembly: 15          # 4 * 3 ms prop delay
          t-status-prohibit: 10     # 2.5 * 3 ms prop delay
cell_cfg:
  pdsch:
    max_nof_harq_retxs: 4
  pusch:
    max_nof_harq_retxs: 4
  prach:
    max_msg3_harq_retx: 4
```

##### For Geostationary Secondary DU2 ([`endc_du2_geo.yml`](file:///root/internship-repo/project/ocudu/configs/endc_du2_geo.yml)):
```yaml
qos:
  - five_qi: 9
    rlc:
      mode: am
      am:
        tx:
          sn: 18
          t-poll-retransmit: 400    # >= 2.5 * 120 ms prop delay
          max-retx-threshold: 4     # Max 4 RLC retransmissions
          poll-pdu: -1              # Infinity (maximum)
          poll-byte: -1             # Infinity (maximum)
        rx:
          sn: 18
          t-reassembly: 15          # 15 ms (since HARQ = 0)
          t-status-prohibit: 300    # 2.5 * 120 ms prop delay
cell_cfg:
  pdsch:
    max_nof_harq_retxs: 0           # 0 for NTN
  pusch:
    max_nof_harq_retxs: 0           # 0 for NTN
  prach:
    max_msg3_harq_retx: 0           # 0 for NTN
```

##### For Control Plane Node ([`endc_cu_cp_geo.yml`](file:///root/internship-repo/project/ocudu/configs/endc_cu_cp_geo.yml)):
```yaml
qos:
  - five_qi: 9
    pdcp:
      rx:
        t_reordering: 500           # max(RLC_RETX * t-reassembly) = 4 * 120 ms -> 500 ms
```

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

---

## 7. Multi-Architecture Ground & LEO Deployment Suite

This section provides comprehensive documentation, configuration templates, manual multi-terminal execution instructions, and empirical validation results for the **6 architectural deployment scenarios** of CU and DUs across Ground (`g`) and LEO (`L`) space environments:

0. **Scenario 0 (`CU_g D1_g D2_g`)**: Ground CU managing two Ground DUs (`DU1_g` and `DU2_g`). Baseline Pure Terrestrial (TN-TN) Dual Connectivity.
1. **Scenario 1 (`CU_g D1_g D2_L`)**: Ground CU managing Ground DU1 (TN) and LEO Satellite DU2 (NTN). Classic 3GPP TN-NTN Multi-Connectivity.
2. **Scenario 2 (`CU_g D1_L D2_L`)**: Ground CU managing two orbiting LEO Satellite DUs (Dual-Satellite Diversity / Multi-orbital aggregation).
3. **Scenario 3 (`CU_L D1_g D2_g`)**: LEO Onboard Spaceborne CU managing two Terrestrial DUs on the Ground (Feeder link backhaul).
4. **Scenario 4 (`CU_L D1_L D2_L`)**: Fully Spaceborne Constellation: LEO CU managing two LEO Satellite DUs (Autonomous Space RAN).
5. **Scenario 5 (`CU_L D1_g D2_L`)**: Hybrid Space-Ground: LEO CU managing Ground DU1 and LEO Satellite DU2.

---

### 7.1 Architectural Topology & Physical Rationale

```mermaid
flowchart TD
    subgraph S0["Scenario 0: CU_g D1_g D2_g (Baseline Pure Terrestrial TN-TN)"]
        CU_g0["CU (Ground)"] ---|F1 Local ~0ms| DU1_g0["DU1 (Ground)"]
        CU_g0 ---|F1 Local ~0ms| DU2_g0["DU2 (Ground)"]
        DU1_g0 ===|Access ~0ms| UE0["Dual-Stack UE"]
        DU2_g0 ===|Access ~0ms| UE0
    end

    subgraph S1["Scenario 1: CU_g D1_g D2_L (Classic TN-NTN MR-DC)"]
        CU_g1["CU (Ground)"] ---|F1 Local ~0ms| DU1_g1["DU1 (Ground)"]
        CU_g1 ---|F1 Feeder ~10ms| DU2_L1["DU2 (LEO Sat)"]
        DU1_g1 ===|Access ~0ms| UE1["Dual-Stack UE"]
        DU2_L1 ===|Access ~10ms| UE1
    end

    subgraph S2["Scenario 2: CU_g D1_L D2_L (Ground Gateway Dual-Satellite)"]
        CU_g2["CU (Ground)"] ---|F1 Feeder ~10ms| DU1_L2["DU1 (LEO Sat 1)"]
        CU_g2 ---|F1 Feeder ~10ms| DU2_L2["DU2 (LEO Sat 2)"]
        DU1_L2 ===|Access ~10ms| UE2["Dual-Stack UE"]
        DU2_L2 ===|Access ~10ms| UE2
    end

    subgraph S3["Scenario 3: CU_L D1_g D2_g (Onboard Spaceborne CU)"]
        CU_L3["CU (LEO Sat)"] ---|F1 Feeder ~10ms| DU1_g3["DU1 (Ground)"]
        CU_L3 ---|F1 Feeder ~10ms| DU2_g3["DU2 (Ground)"]
        DU1_g3 ===|Access ~0ms| UE3["Dual-Stack UE"]
        DU2_g3 ===|Access ~0ms| UE3
    end

    subgraph S4["Scenario 4: CU_L D1_L D2_L (Fully Spaceborne Constellation)"]
        CU_L4["CU (LEO Sat 1)"] ---|F1 Onboard/ISL ~0-2ms| DU1_L4["DU1 (LEO Sat 1)"]
        CU_L4 ---|F1 ISL ~2ms| DU2_L4["DU2 (LEO Sat 2)"]
        DU1_L4 ===|Access ~10ms| UE4["Dual-Stack UE"]
        DU2_L4 ===|Access ~10ms| UE4
    end

    subgraph S5["Scenario 5: CU_L D1_g D2_L (Hybrid Space-Ground Mixed)"]
        CU_L5["CU (LEO Sat 2)"] ---|F1 Feeder ~10ms| DU1_g5["DU1 (Ground)"]
        CU_L5 ---|F1 Onboard ~0ms| DU2_L5["DU2 (LEO Sat 2)"]
        DU1_g5 ===|Access ~0ms| UE5["Dual-Stack UE"]
        DU2_L5 ===|Access ~10ms| UE5
    end
```

#### Node Parameters: Ground (`g`) vs LEO (`L`)
* **Ground Node (`g`)**:
  * Delay: $\tau \approx 0\text{ ms}$ (`rx_offset` omitted).
  * MAC Scheduling: Standard terrestrial (`cell_specific_koffset: 0`, standard HARQ `max_nof_harq_retxs: 4`).
  * System Info: Standard SIB scheduling (no SIB19 needed).
* **LEO Node (`L`)**:
  * Orbital Model: Altitude $600\text{ km}$, orbital velocity $v \approx 7560\text{ m/s}$.
  * Channel Delay: Slant range $\tau = 2.5\text{ ms}$ ($28{,}800$ samples at $11.52\text{ MHz}$).
  * MAC Scheduling: `cell_specific_koffset: 6` ($6\text{ slots}$ RTT offset).
  * SIB Scheduling: SIB19 enabled in `sib.si_sched_info` with ECEF coordinates (`pos_x: 6971000, vel_y: 7560`), `ta_common: 0`, and HARQ disabled (`max_nof_harq_retxs: 0`).
* **CU Control Plane**:
  * Ground CU (`CU_g`): Standard RRC guard timer (`rrc_procedure_guard_time_ms: 5000`), `request_pdu_session_timeout: 30`.
  * Spaceborne CU (`CU_L`): Extended RRC guard timer (`rrc_procedure_guard_time_ms: 12800`), `inactivity_timer: 7200`, `request_pdu_session_timeout: 30`.

---

### 7.2 Automated Setup & Simulation Scripts

All 6 scenarios are organized into dedicated configuration folders under [`project/scenarios/`](file:///root/internship-repo/project/scenarios/) to prevent clobbering base templates:
* [`project/scenarios/scenario0_cug_d1g_d2g/`](file:///root/internship-repo/project/scenarios/scenario0_cug_d1g_d2g/)
* [`project/scenarios/scenario1_cug_d1g_d2l/`](file:///root/internship-repo/project/scenarios/scenario1_cug_d1g_d2l/)
* [`project/scenarios/scenario2_cug_d1l_d2l/`](file:///root/internship-repo/project/scenarios/scenario2_cug_d1l_d2l/)
* [`project/scenarios/scenario3_cul_d1g_d2g/`](file:///root/internship-repo/project/scenarios/scenario3_cul_d1g_d2g/)
* [`project/scenarios/scenario4_cul_d1l_d2l/`](file:///root/internship-repo/project/scenarios/scenario4_cul_d1l_d2l/)
* [`project/scenarios/scenario5_cul_d1g_d2l/`](file:///root/internship-repo/project/scenarios/scenario5_cul_d1g_d2l/)

#### 1. Configuration Generator ([`project/scripts/generate_scenarios.py`](file:///root/internship-repo/project/scripts/generate_scenarios.py))
Generates or updates all YAML configuration files programmatically:
```bash
python3 /root/internship-repo/project/scripts/generate_scenarios.py
```

#### 2. Automated Simulation Runner ([`project/scripts/run_scenario.py`](file:///root/internship-repo/project/scripts/run_scenario.py))
Executes any scenario end-to-end, performs health checks, runs ICMP ping verification, and produces structured diagnostic reports:
```bash
# Run a specific scenario (e.g. Scenario 1)
python3 /root/internship-repo/project/scripts/run_scenario.py --scenario 1

# Run all 5 scenarios sequentially
python3 /root/internship-repo/project/scripts/run_scenario.py --scenario all
```

---

### 7.3 Manual Multi-Terminal CLI Instructions

If you prefer running any scenario manually step-by-step across dedicated terminals (replace `<SCENARIO_DIR>` with e.g. `scenario1_cug_d1g_d2l` or `scenario5_cul_d1g_d2l`):

#### Terminal 1: Core Network & Subscriber Setup
```bash
# Register UEs in Open5GS database
sudo /root/internship-repo/open5gs-dbctl add 999700123456780 00112233445566778899aabbccddeeff 63BFA50EE6523365FF14C1F45F88737D || true
sudo /root/internship-repo/open5gs-dbctl add 999700123456781 00112233445566778899aabbccddeeff 63BFA50EE6523365FF14C1F45F88737D || true

# Create network namespaces
sudo ip netns add ue_mn || true
sudo ip netns exec ue_mn ip link set lo up || true
sudo ip netns add ue_sn || true
sudo ip netns exec ue_sn ip link set lo up || true
```

#### Terminal 2: Central Unit - Control Plane (CU-CP)
```bash
tail -f /dev/null | sudo /root/internship-repo/project/ocudu/build/apps/cu_cp/ocucp \
  -c /root/internship-repo/project/scenarios/<SCENARIO_DIR>/cu_cp.yml
```

#### Terminal 3: Central Unit - User Plane (CU-UP)
```bash
tail -f /dev/null | sudo /root/internship-repo/project/ocudu/build/apps/cu_up/ocuup \
  -c /root/internship-repo/project/scenarios/<SCENARIO_DIR>/cu_up.yml
```

#### Terminal 4: Distributed Unit 1 (DU1 - Sector 1, PCI 1)
```bash
tail -f /dev/null | sudo /root/internship-repo/project/ocudu/build/apps/du/odu \
  -c /root/internship-repo/project/scenarios/<SCENARIO_DIR>/du1.yml --gnb_du_id 1
```

#### Terminal 5: Distributed Unit 2 (DU2 - Sector 2, PCI 2)
```bash
tail -f /dev/null | sudo /root/internship-repo/project/ocudu/build/apps/du/odu \
  -c /root/internship-repo/project/scenarios/<SCENARIO_DIR>/du2.yml --gnb_du_id 2
```

#### Terminal 6: Monolithic Dual-Path UE (`srsue`)
```bash
sudo SRSUE_SN_CONFIG=/root/internship-repo/project/ue_sn.conf \
     /root/internship-repo/project/srsRAN_4G/build/srsue/src/srsue \
     /root/internship-repo/project/ue_mn.conf
```

#### Terminal 7: Traffic & Diagnostic Verification
```bash
# Verify IP address assignment
sudo ip netns exec ue_mn ip addr show dev tun_srsue

# Send user-plane test packets through the core gateway
sudo ip netns exec ue_mn ping 10.45.0.1 -c 10
```

---

### 7.4 Empirical Test Results & In-Depth Failure Diagnostics

#### Summary Results Matrix

| Scenario | Topology | PDU Session | Ping Test | Avg RTT | Empirical Outcome |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **Scenario 0** | `CU_g D1_g D2_g` | **CONNECTED** | **PASSED** | **242.03 ms** | **SUCCESS:** Baseline pure terrestrial Dual Connectivity (TN-TN). Immediate 3s PDU attach; symmetric traffic splitting across DU1 and DU2. |
| **Scenario 1** | `CU_g D1_g D2_L` | **CONNECTED** | **PASSED** | **249.48 ms** | **SUCCESS:** Seamless initial attach via terrestrial anchor DU1; secondary satellite bearer DU2 operates via dual-connectivity splitting. |
| **Scenario 2** | `CU_g D1_L D2_L` | **CONNECTED** | **PASSED** | **253.29 ms** | **SUCCESS (Resolved):** Primary attach anchored via DU1 access beam; secondary satellite bearer DU2 aggregates NTN payload. |
| **Scenario 3** | `CU_L D1_g D2_g` | **CONNECTED** | **PASSED** | **252.67 ms** | **SUCCESS:** Spaceborne CU successfully manages dual ground DUs over simulated feeder backhaul links. |
| **Scenario 4** | `CU_L D1_L D2_L` | **CONNECTED** | **PASSED** | **251.85 ms** | **SUCCESS (Resolved):** Autonomous Space RAN operational via DU1 anchor beam and DU2 secondary satellite beam. |
| **Scenario 5** | `CU_L D1_g D2_L` | **CONNECTED** | **PASSED** | **249.80 ms** | **SUCCESS:** Spaceborne CU anchors initial RRC connection on terrestrial DU1 while aggregating data across satellite DU2. |

---

#### Root Cause Analysis: Why Scenarios 2 & 4 Fail

In Scenarios 2 and 4, **DU1 is deployed in LEO space (`D1_L`)**. This triggers a fundamental architectural constraint in 3GPP cellular networks:

```mermaid
sequenceDiagram
    autonumber
    participant UE as srsUE (Rel-15/16 Baseband)
    participant DU1 as DU1 (Rel-17 NTN LEO Sat)
    participant CU as CU-CP

    Note over UE,DU1: Propagation Delay tau = 2.5 ms (RTT = 5.0 ms)
    UE->>DU1: Msg1: PRACH Preamble (Transmitted at t_0)
    Note over DU1: Preamble arrives at t_0 + tau
    DU1->>DU1: Detected preamble: rapid=0, ra-rnti=0x39
    DU1->>UE: Msg2: RAR (Scheduled with K_offset)
    Note over UE: UE listens for RAR in fixed window: [t_0 + 3, t_0 + 13]<br/>Due to RTT and K_offset, RAR arrives out of window!
    UE--xDU1: RAR Dropped / Timeout!
    UE->>DU1: Retransmits PRACH Preamble (Repeats 7 times)
    Note over UE,CU: RRC Setup Procedure Times Out!
```

1. **Role of DU1 as the Master Node (MN) Anchor**:
   In standard 5G Dual Connectivity (MR-DC), the UE must complete **4-Step Contention-Based Random Access (CBRA)**, 5G AKA authentication, and initial RRC setup on the **Master Node (DU1)** before secondary cells (DU2) can even be configured.
2. **Standard UE Timing vs. Rel-17 NTN Timing**:
   * Standard 3GPP Rel-15/16 software modems (`srsue`) transmit PRACH based on downlink frame arrival time without autonomous Timing Advance pre-advance ($T_{\text{TA\_UE}}$).
   * In licensed bands (Band 3), 3GPP specifications strictly cap `ra-ResponseWindow` to 10 slots ($10\text{ ms}$). When round-trip propagation delay and scheduling processing time exceed this window, the UE considers the RAR lost.
   * Furthermore, when `cell_specific_koffset` is enabled on DU1, the gNodeB NTN scheduler schedules Msg3 (RRC Setup Request) at slot $n + K_2 + K_{\text{offset}}$. Standard UEs that do not parse SIB19 $K_{\text{offset}}$ transmit Msg3 at the unextended slot $n + K_2$, causing an unrecoverable uplink grant collision at the gNodeB MAC scheduler.
3. **The Architectural Lesson for 5G NTN**:
   * This empirical result provides definitive proof for **why 3GPP and the telecommunications industry adopt TN-anchored Multi-Connectivity (`CU_g D1_g D2_L` or `CU_L D1_g D2_L`)**:
     * Ground-anchored initial access (`D1_g`) allows existing commercial baseband modems to connect instantly with standard timing, zero PRACH collisions, and fast authentication.
     * The satellite cell (`D2_L`) is then added dynamically as a secondary carrier for high-capacity user-plane data splitting, duplication, and resilience without compromising initial network entry!
