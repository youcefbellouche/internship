# Approach 1 Failure Analysis: Split Bearer Dual Connectivity

This document details the compile-time and architectural blockages that prevent implementing a monolithic Split Bearer (Approach 1) on the srsRAN UE side.

---

## ❌ Compile-Time Mismatches

By modifying `srsran::pdcp_entity_nr` to declare dual RLC pointers:
```cpp
pdcp_entity_nr(srsue::rlc_interface_pdcp* rlc_mn_,
               srsue::rlc_interface_pdcp* rlc_sn_,
               srsue::rrc_interface_pdcp* rrc_,
               srsue::gw_interface_pdcp*  gw_,
               srsran::task_sched_handle  task_sched_,
               srslog::basic_logger&      logger,
               uint32_t                   lcid);
```

The compiler failed to link the entity inside the container class:
```text
/root/internship-repo/project/srsRAN_4G/lib/src/pdcp/pdcp.cc:123:75: error: no matching function for call to ‘srsran::pdcp_entity_nr::pdcp_entity_nr(<brace-enclosed initializer list>)’
  123 | , rrc, gw, task_sched, logger, lcid});
      |                                    ^
/root/internship-repo/project/srsRAN_4G/lib/include/srsran/upper/pdcp_entity_nr.h:45:3: note: candidate expects 7 arguments, 6 provided
```

---

## 🧱 Architectural Design Constraints

### 1. Tight 1:1 Protocol Layer Coupling
The srsRAN architecture is highly optimized for single-cell/carrier connectivity. Every layer below PDCP is bound 1:1:
* The container class `srsran::pdcp` holds a single `rlc` pointer.
* Changing this to hold multiple RLC pointers (or a list of pointers) requires updating `pdcp::init()`.
* Because `srsran::pdcp` is shared between different stacks, changing its signature breaks the compilation of:
  * **LTE UE Stack:** [ue_stack_lte.cc](file:///root/internship-repo/project/srsRAN_4G/srsue/src/stack/ue_stack_lte.cc)
  * **NR UE Stack:** [ue_stack_nr.cc](file:///root/internship-repo/project/srsRAN_4G/srsue/src/stack/ue_stack_nr.cc)
  * **eNB Stack:** `srsenb` upper layers.
  * **Unit Tests:** All unit test mock frameworks.

### 2. MAC Scheduler and Logical Channel Mapping
Under a split bearer, a single Logical Channel ID (LCID) must be mapped to two separate RLC/MAC instances:
* Standard `srsran` MAC uses the LCID directly to pull data from RLC using `rlc->read_pdu(lcid, ...)`.
* If a single LCID maps to two different RLC instances, the MAC scheduling loop cannot query or segment buffers correctly without rewriting the logical channel mapping logic in both `mac` and `rlc` classes.

### 3. Physical Layer ZMQ Thread Contention
Running two separate PHY layers in a single process requires:
* Spawning two concurrent transceiver scheduling threads.
* Connecting to two separate ZMQ RF interfaces on different socket ports.
* This results in lock contention and scheduling conflicts inside the monolithic `srsue` binary, as it expects a single primary cell synchronizer (`sync`).

---

## 💡 Summary
Approach 1 is a "vertical" split that breaks encapsulation across every layer of the protocol stack. Because of this, it is not possible to implement without rewriting the core framework architecture of srsRAN. 

We proceed to **Approach 2 (Mock Xn-Bridge)**, which introduces a "horizontal" bridge at the PDCP boundary, preserving all internal 1:1 couplings.
