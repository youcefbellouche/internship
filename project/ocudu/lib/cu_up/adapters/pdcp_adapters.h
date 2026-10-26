// SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
// SPDX-License-Identifier: BSD-3-Clause-Open-MPI
// Portions of this file may implement 3GPP specifications, which may be subject to additional licensing requirements.

#pragma once

#include "ocudu/cu_up/cu_up_manager.h"
#include "ocudu/e1ap/cu_up/e1ap_cu_up.h"
#include "ocudu/f1u/cu_up/f1u_tx_sdu_handler.h"
#include "ocudu/pdcp/pdcp_rx.h"
#include "ocudu/pdcp/pdcp_tx.h"
#include "ocudu/sdap/sdap.h"

#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <mutex>
#include <string>

namespace ocudu {
namespace ocuup {

class pdcp_f1u_adapter;

/// Registry bridge connecting Master Node (MN) and Secondary Node (SN) F1-U handlers in CU-UP
struct mrdc_cu_bridge {
  static inline std::mutex           mtx;
  static inline pdcp_f1u_adapter*   mn_adapter = nullptr;
  static inline f1u_tx_sdu_handler* mn_handler = nullptr;
  static inline f1u_tx_sdu_handler* sn_handler = nullptr;

  static void register_mn(pdcp_f1u_adapter* adapter, f1u_tx_sdu_handler& handler);
  static void register_sn(f1u_tx_sdu_handler& handler);
  static void unregister_mn(pdcp_f1u_adapter* adapter);
  static void unregister_sn(f1u_tx_sdu_handler* handler = nullptr);
};

/// Adapter between PDCP and SDAP
class pdcp_sdap_adapter : public pdcp_rx_upper_data_notifier
{
public:
  pdcp_sdap_adapter()           = default;
  ~pdcp_sdap_adapter() override = default;

  void connect_sdap(sdap_rx_pdu_handler& sdap_handler_) { sdap_handler = &sdap_handler_; }

  void on_new_sdu(byte_buffer sdu, bool integrity_verified) override
  {
    // The value of integrity_verified is unused for DRBs.
    ocudu_assert(sdap_handler != nullptr, "SDAP handler must not be nullptr");
    sdap_handler->handle_pdu(std::move(sdu));
  }

private:
  sdap_rx_pdu_handler* sdap_handler = nullptr;
};

/// Adapter between PDCP Rx and E1AP (to be forwarded to RRC in the DU)
class pdcp_rx_cu_up_mngr_adapter : public pdcp_rx_upper_control_notifier
{
public:
  pdcp_rx_cu_up_mngr_adapter()           = default;
  ~pdcp_rx_cu_up_mngr_adapter() override = default;

  void connect_cu_up_mngr(cu_up_ue_index_t ue_index_, cu_up_manager_pdcp_interface* cu_up_mngr_)
  {
    cu_up_mngr = cu_up_mngr_;
    ue_index   = ue_index_;
  }

  void on_protocol_failure() override
  {
    if (cu_up_mngr == nullptr) {
      ocudulog::fetch_basic_logger("PDCP").debug("Ignoring on_protocol_failure() from PDCP Rx: No E1AP handler.");
      return;
    }
    cu_up_mngr->handle_pdcp_protocol_failure(ue_index);
  }

  void on_integrity_failure() override
  {
    if (cu_up_mngr == nullptr) {
      ocudulog::fetch_basic_logger("PDCP").debug("Ignoring on_integrity_failure() from PDCP Rx: No E1AP handler.");
      return;
    }
    cu_up_mngr->handle_pdcp_integrity_failure(ue_index);
  }

  void on_max_count_reached() override
  {
    if (cu_up_mngr == nullptr) {
      ocudulog::fetch_basic_logger("PDCP").debug(
          "Max COUNT reached from PDCP Rx, but no E1AP handler present. Ignoring.");
      return;
    }
    cu_up_mngr->handle_pdcp_max_count_reached(ue_index);
  }

  void on_resume_required() override
  {
    if (cu_up_mngr == nullptr) {
      ocudulog::fetch_basic_logger("PDCP").debug(
          "Resume requested from PDCP Rx, but no E1AP handler present. Ignoring");
      return;
    }
    cu_up_mngr->handle_pdcp_resume_required(ue_index);
  }

  cu_up_manager_pdcp_interface* cu_up_mngr = nullptr;
  cu_up_ue_index_t              ue_index   = INVALID_CU_UP_UE_INDEX;
};

/// Adapter between PDCP and F1-U supporting Space-Terrestrial Multi-Connectivity (Split Bearer & Duplication)
class pdcp_f1u_adapter : public pdcp_tx_lower_notifier
{
public:
  pdcp_f1u_adapter()           = default;
  ~pdcp_f1u_adapter() override
  {
    mrdc_cu_bridge::unregister_mn(this);
  }

  void connect_f1u(f1u_tx_sdu_handler& f1u_handler_) { f1u_handler_mn = &f1u_handler_; }
  void connect_f1u_mn(f1u_tx_sdu_handler& f1u_handler_mn_) { f1u_handler_mn = &f1u_handler_mn_; }
  void connect_f1u_sn(f1u_tx_sdu_handler* f1u_handler_sn_) { f1u_handler_sn = f1u_handler_sn_; }
  void disconnect_f1u()
  {
    f1u_handler_mn = nullptr;
    f1u_handler_sn = nullptr;
  }

  void on_new_pdu(byte_buffer pdu, bool is_retx) override
  {
    if (f1u_handler_mn == nullptr && f1u_handler_sn == nullptr) {
      ocudulog::fetch_basic_logger("PDCP").info("Dropped DL PDU. F1-U handler is not connected");
      return;
    }

    // Single-DU fallback if secondary DU is not linked
    if (f1u_handler_sn == nullptr) {
      f1u_handler_mn->handle_sdu(std::move(pdu), is_retx);
      return;
    }
    if (f1u_handler_mn == nullptr) {
      f1u_handler_sn->handle_sdu(std::move(pdu), is_retx);
      return;
    }

    // Check runtime ratio periodically or upon first packet
    if (!parsed || (poll_counter++ & 0x0f) == 0) {
      check_runtime_ratio();
    }

    // Mode 1: URLLC Packet Duplication (dup)
    if (duplication_mode) {
      byte_buffer pdu_copy = pdu.copy();
      f1u_handler_sn->handle_sdu(std::move(pdu_copy), is_retx);
      f1u_handler_mn->handle_sdu(std::move(pdu), is_retx);
      return;
    }

    // Mode 2: Pure Satellite Link (0:1)
    if (ratio_mn == 0 && ratio_sn > 0) {
      f1u_handler_sn->handle_sdu(std::move(pdu), is_retx);
      return;
    }

    // Mode 3: Pure Terrestrial Link (1:0)
    if (ratio_sn == 0 && ratio_mn > 0) {
      f1u_handler_mn->handle_sdu(std::move(pdu), is_retx);
      return;
    }

    // Mode 4: Dynamic Traffic Splitting (e.g. 1:1, 3:1)
    uint32_t count = packet_counter++ % total_ratio;
    if (count < ratio_mn) {
      f1u_handler_mn->handle_sdu(std::move(pdu), is_retx);
    } else {
      f1u_handler_sn->handle_sdu(std::move(pdu), is_retx);
    }
  }

  void on_discard_pdu(uint32_t pdcp_sn) override
  {
    if (f1u_handler_mn != nullptr) {
      f1u_handler_mn->discard_sdu(pdcp_sn);
    }
    if (f1u_handler_sn != nullptr) {
      f1u_handler_sn->discard_sdu(pdcp_sn);
    }
  }

private:
  f1u_tx_sdu_handler* f1u_handler_mn = nullptr;
  f1u_tx_sdu_handler* f1u_handler_sn = nullptr;

  std::atomic<uint32_t> packet_counter{0};
  uint32_t              poll_counter     = 0;
  uint32_t              ratio_mn         = 1;
  uint32_t              ratio_sn         = 1;
  uint32_t              total_ratio      = 2;
  bool                  duplication_mode = false;
  bool                  parsed           = false;
  std::string           last_buf;

  void apply_ratio_str(const char* str)
  {
    if (str == nullptr) {
      return;
    }
    std::string s(str);
    while (!s.empty() && (s.back() == '\n' || s.back() == '\r' || s.back() == ' ')) {
      s.pop_back();
    }

    if (s == "dup" || s == "duplicate" || s == "duplication" || s.find("dup") != std::string::npos) {
      duplication_mode = true;
      ratio_mn         = 1;
      ratio_sn         = 1;
      total_ratio      = 2;
      ocudulog::fetch_basic_logger("PDCP").info(
          "[CU-UP DL Multi-Connectivity] Live mode: Packet Duplication ENABLED (DU1+DU2)");
      return;
    }

    int mn = 1, sn = 1;
    if (sscanf(s.c_str(), "%d:%d", &mn, &sn) == 2 && mn >= 0 && sn >= 0 && (mn + sn) > 0) {
      ratio_mn         = mn;
      ratio_sn         = sn;
      total_ratio      = mn + sn;
      duplication_mode = false;
      ocudulog::fetch_basic_logger("PDCP").info(
          "[CU-UP DL Multi-Connectivity] Live mode: Traffic Splitting MN(DU1)={:d}, SN(DU2)={:d} (Ratio {:d}:{:d})",
          mn,
          sn,
          mn,
          sn);
    }
  }

  void check_runtime_ratio()
  {
    if (!parsed) {
      char* env_ratio = std::getenv("PDCP_SPLIT_RATIO");
      if (env_ratio != nullptr) {
        apply_ratio_str(env_ratio);
      }
      parsed = true;
    }

    FILE* fp = fopen("/tmp/pdcp_split_ratio", "r");
    if (fp == nullptr) {
      fp = fopen("/root/internship-repo/project/pdcp_split_ratio", "r");
    }
    if (fp != nullptr) {
      char buf[64];
      if (fgets(buf, sizeof(buf), fp) != nullptr) {
        std::string cur(buf);
        if (cur != last_buf) {
          last_buf = cur;
          apply_ratio_str(buf);
        }
      }
      fclose(fp);
    }
  }
};

inline void mrdc_cu_bridge::register_mn(pdcp_f1u_adapter* adapter, f1u_tx_sdu_handler& handler)
{
  std::lock_guard<std::mutex> lock(mtx);
  mn_adapter = adapter;
  mn_handler = &handler;
  if (mn_adapter != nullptr && sn_handler != nullptr) {
    mn_adapter->connect_f1u_sn(sn_handler);
    ocudulog::fetch_basic_logger("PDCP").info(
        "[CU-UP MR-DC Bridge] Auto-connected SN (DU2) F1-U handler to MN (DU1) PDCP DL adapter.");
  }
}

inline void mrdc_cu_bridge::register_sn(f1u_tx_sdu_handler& handler)
{
  std::lock_guard<std::mutex> lock(mtx);
  sn_handler = &handler;
  if (mn_adapter != nullptr && sn_handler != nullptr) {
    mn_adapter->connect_f1u_sn(sn_handler);
    ocudulog::fetch_basic_logger("PDCP").info(
        "[CU-UP MR-DC Bridge] Auto-connected SN (DU2) F1-U handler to MN (DU1) PDCP DL adapter.");
  }
}

inline void mrdc_cu_bridge::unregister_mn(pdcp_f1u_adapter* adapter)
{
  std::lock_guard<std::mutex> lock(mtx);
  if (mn_adapter == adapter) {
    mn_adapter = nullptr;
    mn_handler = nullptr;
  }
}

inline void mrdc_cu_bridge::unregister_sn(f1u_tx_sdu_handler* handler)
{
  std::lock_guard<std::mutex> lock(mtx);
  if (handler == nullptr || sn_handler == handler) {
    if (mn_adapter != nullptr) {
      mn_adapter->connect_f1u_sn(nullptr);
    }
    sn_handler = nullptr;
  }
}


/// Adapter between PDCP Tx and E1AP (to be forwarded to RRC in the DU)
class pdcp_tx_cu_up_mngr_adapter : public pdcp_tx_upper_control_notifier
{
public:
  pdcp_tx_cu_up_mngr_adapter()           = default;
  ~pdcp_tx_cu_up_mngr_adapter() override = default;

  void connect_cu_up_mngr(cu_up_ue_index_t ue_index_, cu_up_manager_pdcp_interface* cu_up_mngr_)
  {
    cu_up_mngr = cu_up_mngr_;
    ue_index   = ue_index_;
  }

  void on_protocol_failure() override
  {
    ocudulog::fetch_basic_logger("PDCP").warning("Ignoring on_protocol_failure() from PDCP Tx: No E1AP handler");
  }

  void on_max_count_reached() override
  {
    if (cu_up_mngr == nullptr) {
      ocudulog::fetch_basic_logger("PDCP").warning(
          "No CU-UP manager handler for PDCP Tx control events. All events will be ignored");
      return;
    }
    cu_up_mngr->handle_pdcp_max_count_reached(ue_index);
  }

  void on_resume_required() override
  {
    if (cu_up_mngr == nullptr) {
      ocudulog::fetch_basic_logger("PDCP").debug(
          "Resume requested from PDCP Tx, but no E1AP handler present. Ignoring");
      return;
    }
    cu_up_mngr->handle_pdcp_resume_required(ue_index);
  }

private:
  cu_up_manager_pdcp_interface* cu_up_mngr = nullptr;
  cu_up_ue_index_t              ue_index   = INVALID_CU_UP_UE_INDEX;
};

} // namespace ocuup
} // namespace ocudu
