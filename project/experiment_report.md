# Dual Connectivity (DC) Realtime Simulation & Log Report

## 📋 Executive Summary

This report presents the UE PDCP layer execution logs captured during realtime simulation of Dual Connectivity (DC) split bearer and packet duplication modes across two Distributed Units (`DU1` and `DU2`).

All logs have been recorded into separate log files:
1. **Split Bearer Realtime Log**: [`ue_pdcp_split_bearer.log`](file:///root/internship-repo/project/ue_pdcp_split_bearer.log)
2. **Packet Duplication Realtime Log**: [`ue_pdcp_packet_duplication.log`](file:///root/internship-repo/project/ue_pdcp_packet_duplication.log)
3. **Full UE PDCP Layer Log**: [`ue_full_pdcp.log`](file:///root/internship-repo/project/ue_full_pdcp.log)

---

## 🔍 Log File Breakdown & Verification

### 1. Test 1: Split Bearer UE PDCP Log (`ue_pdcp_split_bearer.log`)

In this test, DU1 transmits odd packets (`1, 3, 5, 7`) on `LCID 4` and DU2 transmits even packets (`2, 4, 6, 8`) on `LCID 5`.

#### Key Log Traces:
```text
2026-07-20 17:26:57.409 [RLC    ] [D] [LCID 4] Received PDU from DU1 | sn=1 bytes=64
2026-07-20 17:26:57.409 [PDCP   ] [D] [DRB 1] rx_pdu: Received PDU from LCID 4 | PDCP SN=1 (Size 64B)
2026-07-20 17:26:57.409 [PDCP   ] [I] [DRB 1] deliver: Reordering buffer pop SN=1 -> Delivered in-sequence to SDAP/IP layer
2026-07-20 17:26:57.409 [RLC    ] [D] [LCID 5] Received PDU from DU2 | sn=2 bytes=64
2026-07-20 17:26:57.409 [PDCP   ] [D] [DRB 1] rx_pdu: Received PDU from LCID 5 | PDCP SN=2 (Size 64B)
2026-07-20 17:26:57.409 [PDCP   ] [I] [DRB 1] deliver: Reordering buffer pop SN=2 -> Delivered in-sequence to SDAP/IP layer
...
--- END TEST 1: SPLIT BEARER SUCCESSFUL (All 8 Packets Delivered In Sequence) ---
```

---

### 2. Test 2: Packet Duplication UE PDCP Log (`ue_pdcp_packet_duplication.log`)

In this test, both DU1 (`LCID 4`) and DU2 (`LCID 5`) transmit identical copies of packets `1, 2, 3, 4`.

#### Key Log Traces:
```text
2026-07-20 17:26:57.409 [RLC    ] [D] [LCID 4] Received PDU from DU1 | sn=1 bytes=64
2026-07-20 17:26:57.409 [PDCP   ] [I] [DRB 1] deliver: First copy of SN=1 accepted -> Forwarded to IP layer
...
2026-07-20 17:26:57.409 [RLC    ] [D] [LCID 5] Received PDU from DU2 | sn=1 bytes=64
2026-07-20 17:26:57.409 [PDCP   ] [W] [DRB 1] DISCARD DUPLICATE: PDCP SN=1 already received on primary leg. Dropping redundant PDU.
...
--- END TEST 2: PACKET DUPLICATION SUCCESSFUL (4 Duplicates Detected & Dropped) ---
```

---

## 🛠️ Log File Locations

- [`ue_pdcp_split_bearer.log`](file:///root/internship-repo/project/ue_pdcp_split_bearer.log)
- [`ue_pdcp_packet_duplication.log`](file:///root/internship-repo/project/ue_pdcp_packet_duplication.log)
- [`ue_full_pdcp.log`](file:///root/internship-repo/project/ue_full_pdcp.log)
- [`experiment_report.md`](file:///root/internship-repo/project/experiment_report.md)
