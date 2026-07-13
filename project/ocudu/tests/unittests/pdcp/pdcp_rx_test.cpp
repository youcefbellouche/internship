// SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
// SPDX-License-Identifier: BSD-3-Clause-Open-MPI
// Portions of this file may implement 3GPP specifications, which may be subject to additional licensing requirements.

#include "pdcp_rx_test.h"
#include "pdcp_test_vectors.h"
#include "ocudu/pdcp/pdcp_config.h"
#include "ocudu/support/test_utils.h"
#include <gtest/gtest.h>
#include <queue>
#include <thread>
#include <chrono>

using namespace ocudu;

/// Test creation of PDCP RX entities
TEST_P(pdcp_rx_test_drb, create_new_entity)
{
  init(std::get<pdcp_sn_size>(GetParam()), std::get<unsigned>(GetParam()), std::get<rohc_test_params>(GetParam()));
  ocudu::test_delimit_logger delimiter("Entity creation test. SN_SIZE={} ", sn_size);
  unsigned                   exp_nof_deompressors = header_compression.has_value() ? 1 : 0;
  EXPECT_EQ(pdcp_rohc_factory->get_nof_compressors(), 0);
  EXPECT_EQ(pdcp_rohc_factory->get_nof_decompressors(), exp_nof_deompressors);
  EXPECT_EQ(pdcp_rohc_factory->get_last_decompressor_config(), header_compression);

  ASSERT_NE(pdcp_rx, nullptr);
  ASSERT_NE(test_frame, nullptr);

  // No warnings or errors during construction
  EXPECT_EQ(test_spy.get_warning_counter(), 0);
  EXPECT_EQ(test_spy.get_error_counter(), 0);
}

/// Test extraction of PDCP sequence numbers
TEST_P(pdcp_rx_test_drb, sn_unpack)
{
  init(std::get<pdcp_sn_size>(GetParam()), std::get<unsigned>(GetParam()), std::get<rohc_test_params>(GetParam()));
  unsigned exp_nof_decompressors = header_compression.has_value() ? 1 : 0;
  EXPECT_EQ(pdcp_rohc_factory->get_nof_compressors(), 0);
  EXPECT_EQ(pdcp_rohc_factory->get_nof_decompressors(), exp_nof_decompressors);

  auto test_hdr_reader = [this](uint32_t count) {
    ocudu::test_delimit_logger delimiter("Header reader test. SN_SIZE={} COUNT={}", sn_size, count);
    // Get PDU to test
    byte_buffer test_pdu;
    get_test_pdu(count, test_pdu);
    pdcp_data_pdu_header hdr;
    ASSERT_TRUE(pdcp_rx->read_data_pdu_header(hdr, test_pdu));
    ASSERT_EQ(hdr.sn, SN(count));
  };

  if (sn_size == pdcp_sn_size::size12bits) {
    test_hdr_reader(0);
    test_hdr_reader(2048);
    test_hdr_reader(4096);
    test_hdr_reader(4294967295);
  } else if (sn_size == pdcp_sn_size::size18bits) {
    test_hdr_reader(0);
    test_hdr_reader(131072);
    test_hdr_reader(262144);
    test_hdr_reader(4294967295);
  } else {
    FAIL();
  }

  // No warnings or errors
  EXPECT_EQ(test_spy.get_warning_counter(), 0);
  EXPECT_EQ(test_spy.get_error_counter(), 0);

  EXPECT_EQ(pdcp_rohc_factory->get_nof_compressors(), 0);
  EXPECT_EQ(pdcp_rohc_factory->get_nof_decompressors(), exp_nof_decompressors);
}

/// Test in-order reception of PDCP PDUs
TEST_P(pdcp_rx_test_drb, rx_in_order)
{
  init(std::get<pdcp_sn_size>(GetParam()), std::get<unsigned>(GetParam()), std::get<rohc_test_params>(GetParam()));
  unsigned exp_nof_decompressors = header_compression.has_value() ? 1 : 0;
  EXPECT_EQ(pdcp_rohc_factory->get_nof_compressors(), 0);
  EXPECT_EQ(pdcp_rohc_factory->get_nof_decompressors(), exp_nof_decompressors);

  auto test_rx_in_order = [this](uint32_t count) {
    ocudu::test_delimit_logger delimiter("RX in order test. SN_SIZE={} COUNT={}", sn_size, count);

    pdcp_rx->configure_security(sec_cfg, security::integrity_enabled::on, security::ciphering_enabled::on);

    byte_buffer test_pdu1;
    get_test_pdu(count, test_pdu1);
    byte_buffer test_pdu2;
    get_test_pdu(count + 1, test_pdu2);
    pdcp_rx_state init_state = {.rx_next = count, .rx_deliv = count, .rx_reord = 0};
    pdcp_rx->set_state(init_state);
    pdcp_rx->handle_pdu(byte_buffer_chain::create(std::move(test_pdu1)).value());
    pdcp_rx->handle_pdu(byte_buffer_chain::create(std::move(test_pdu2)).value());

    // Wait for crypto and reordering
    wait_pending_crypto();
    worker.run_pending_tasks();
    ASSERT_EQ(2, test_frame->sdu_queue.size());
    while (not test_frame->sdu_queue.empty()) {
      ASSERT_EQ(test_frame->sdu_queue.front(), sdu1);
      test_frame->sdu_queue.pop();
    }
  };

  if (sn_size == pdcp_sn_size::size12bits) {
    test_rx_in_order(0);
    test_rx_in_order(2047);
    test_rx_in_order(4095);
  } else if (sn_size == pdcp_sn_size::size18bits) {
    test_rx_in_order(0);
    test_rx_in_order(131071);
    test_rx_in_order(262143);
  } else {
    FAIL();
  }

  // No warnings or errors
  EXPECT_EQ(test_spy.get_warning_counter(), 0);
  EXPECT_EQ(test_spy.get_error_counter(), 0);

  EXPECT_EQ(pdcp_rohc_factory->get_nof_compressors(), 0);
  EXPECT_EQ(pdcp_rohc_factory->get_nof_decompressors(), exp_nof_decompressors);
}

/// Test out of order reception of PDUs.
/// All PDUs are received before the t-Reordering expires.
TEST_P(pdcp_rx_test_drb, rx_out_of_order)
{
  init(std::get<pdcp_sn_size>(GetParam()), std::get<unsigned>(GetParam()), std::get<rohc_test_params>(GetParam()));
  unsigned exp_nof_decompressors = header_compression.has_value() ? 1 : 0;
  EXPECT_EQ(pdcp_rohc_factory->get_nof_compressors(), 0);
  EXPECT_EQ(pdcp_rohc_factory->get_nof_decompressors(), exp_nof_decompressors);

  auto test_rx_out_of_order = [this](uint32_t count) {
    ocudu::test_delimit_logger delimiter(
        "RX out-of-order test, no t-Reordering. SN_SIZE={} COUNT=[{}, {}]", sn_size, count + 1, count);

    pdcp_rx->configure_security(sec_cfg, security::integrity_enabled::on, security::ciphering_enabled::on);

    byte_buffer test_pdu1;
    get_test_pdu(count, test_pdu1);
    byte_buffer test_pdu2;
    get_test_pdu(count + 1, test_pdu2);
    byte_buffer test_pdu3;
    get_test_pdu(count + 2, test_pdu3);
    pdcp_rx_state init_state = {.rx_next = count, .rx_deliv = count, .rx_reord = 0};
    pdcp_rx->set_state(init_state);

    pdcp_rx->handle_pdu(byte_buffer_chain::create(std::move(test_pdu2)).value());

    // Wait for crypto and reordering
    wait_pending_crypto();
    worker.run_pending_tasks();
    ASSERT_EQ(0, test_frame->sdu_queue.size());
    // check rx_reord matches rx_next matches count + 2
    EXPECT_EQ(pdcp_rx->get_state().rx_reord, count + 2);
    EXPECT_EQ(pdcp_rx->get_state().rx_reord, pdcp_rx->get_state().rx_next);

    pdcp_rx->handle_pdu(byte_buffer_chain::create(std::move(test_pdu3)).value());

    // Wait for crypto and reordering
    wait_pending_crypto();
    worker.run_pending_tasks();
    ASSERT_EQ(0, test_frame->sdu_queue.size());
    // check rx_reord still maches count + 2, i.e did not change because t_reord is already running; rx_next moved on
    EXPECT_EQ(pdcp_rx->get_state().rx_reord, count + 2);
    EXPECT_EQ(pdcp_rx->get_state().rx_next, count + 3);

    pdcp_rx->handle_pdu(byte_buffer_chain::create(std::move(test_pdu1)).value());

    // Wait for crypto and reordering
    wait_pending_crypto();
    worker.run_pending_tasks();
    ASSERT_EQ(3, test_frame->sdu_queue.size());
    while (not test_frame->sdu_queue.empty()) {
      ASSERT_EQ(test_frame->sdu_queue.front(), sdu1);
      test_frame->sdu_queue.pop();
    }
  };

  if (sn_size == pdcp_sn_size::size12bits) {
    test_rx_out_of_order(0);
    test_rx_out_of_order(2047);
    test_rx_out_of_order(4095);
  } else if (sn_size == pdcp_sn_size::size18bits) {
    test_rx_out_of_order(0);
    test_rx_out_of_order(131071);
    test_rx_out_of_order(262143);
  } else {
    FAIL();
  }

  // No warnings or errors
  EXPECT_EQ(test_spy.get_warning_counter(), 0);
  EXPECT_EQ(test_spy.get_error_counter(), 0);

  EXPECT_EQ(pdcp_rohc_factory->get_nof_compressors(), 0);
  EXPECT_EQ(pdcp_rohc_factory->get_nof_decompressors(), exp_nof_decompressors);
}

/// Test reception of duplicate PDCP PDUs
TEST_P(pdcp_rx_test_drb, rx_duplicate)
{
  init(std::get<pdcp_sn_size>(GetParam()), std::get<unsigned>(GetParam()), std::get<rohc_test_params>(GetParam()));
  unsigned exp_nof_decompressors = header_compression.has_value() ? 1 : 0;
  EXPECT_EQ(pdcp_rohc_factory->get_nof_compressors(), 0);
  EXPECT_EQ(pdcp_rohc_factory->get_nof_decompressors(), exp_nof_decompressors);

  auto test_rx_out_of_order = [this](uint32_t count) {
    ocudu::test_delimit_logger delimiter("RX duplicate test. SN_SIZE={} COUNT=[{}, {}]", sn_size, count + 1, count);

    pdcp_rx->configure_security(sec_cfg, security::integrity_enabled::on, security::ciphering_enabled::on);

    byte_buffer test_pdu1;
    get_test_pdu(count, test_pdu1);
    byte_buffer test_pdu2;
    get_test_pdu(count + 1, test_pdu2);
    byte_buffer test_pdu2_dup;
    get_test_pdu(count + 1, test_pdu2_dup);
    byte_buffer test_pdu3;
    get_test_pdu(count + 2, test_pdu3);
    pdcp_rx_state init_state = {.rx_next = count, .rx_deliv = count, .rx_reord = 0};
    pdcp_rx->set_state(init_state);

    pdcp_rx->handle_pdu(byte_buffer_chain::create(std::move(test_pdu2)).value());

    // Wait for crypto and reordering
    wait_pending_crypto();
    worker.run_pending_tasks();
    ASSERT_EQ(0, test_frame->sdu_queue.size());
    // check rx_reord matches rx_next matches count + 2
    EXPECT_EQ(pdcp_rx->get_state().rx_reord, count + 2);
    EXPECT_EQ(pdcp_rx->get_state().rx_reord, pdcp_rx->get_state().rx_next);

    pdcp_rx->handle_pdu(byte_buffer_chain::create(std::move(test_pdu3)).value());

    // Wait for crypto and reordering
    wait_pending_crypto();
    worker.run_pending_tasks();
    ASSERT_EQ(0, test_frame->sdu_queue.size());
    // check rx_reord still maches count + 2, i.e did not change because t_reord is already running; rx_next moved on
    EXPECT_EQ(pdcp_rx->get_state().rx_reord, count + 2);
    EXPECT_EQ(pdcp_rx->get_state().rx_next, count + 3);

    // Send the duplicate
    pdcp_rx->handle_pdu(byte_buffer_chain::create(std::move(test_pdu2_dup)).value());

    // Wait for crypto and reordering
    wait_pending_crypto();
    worker.run_pending_tasks();
    ASSERT_EQ(0, test_frame->sdu_queue.size());
    // check rx_reord still maches count + 2
    EXPECT_EQ(pdcp_rx->get_state().rx_reord, count + 2);
    EXPECT_EQ(pdcp_rx->get_state().rx_next, count + 3);

    pdcp_rx->handle_pdu(byte_buffer_chain::create(std::move(test_pdu1)).value());

    // Wait for crypto and reordering
    wait_pending_crypto();
    worker.run_pending_tasks();
    ASSERT_EQ(3, test_frame->sdu_queue.size());
    while (not test_frame->sdu_queue.empty()) {
      ASSERT_EQ(test_frame->sdu_queue.front(), sdu1);
      test_frame->sdu_queue.pop();
    }
  };

  if (sn_size == pdcp_sn_size::size12bits) {
    test_rx_out_of_order(0);
    test_rx_out_of_order(2047);
    test_rx_out_of_order(4095);
  } else if (sn_size == pdcp_sn_size::size18bits) {
    test_rx_out_of_order(0);
    test_rx_out_of_order(131071);
    test_rx_out_of_order(262143);
  } else {
    FAIL();
  }

  // No warnings or errors
  EXPECT_EQ(test_spy.get_warning_counter(), 0);
  EXPECT_EQ(test_spy.get_error_counter(), 0);

  EXPECT_EQ(pdcp_rohc_factory->get_nof_compressors(), 0);
  EXPECT_EQ(pdcp_rohc_factory->get_nof_decompressors(), exp_nof_decompressors);
}

/// Test out of order reception of PDUs.
/// The out-of-order PDU is received after the t-Reordering expires.
TEST_P(pdcp_rx_test_drb, rx_reordering_timer)
{
  init(std::get<pdcp_sn_size>(GetParam()), std::get<unsigned>(GetParam()), std::get<rohc_test_params>(GetParam()));
  unsigned exp_nof_decompressors = header_compression.has_value() ? 1 : 0;
  EXPECT_EQ(pdcp_rohc_factory->get_nof_compressors(), 0);
  EXPECT_EQ(pdcp_rohc_factory->get_nof_decompressors(), exp_nof_decompressors);

  auto test_rx_t_reorder = [this](uint32_t count) {
    ocudu::test_delimit_logger delimiter(
        "RX out-of-order test, t-Reordering expires. SN_SIZE={} COUNT=[{}, {}]", sn_size, count + 1, count);

    pdcp_rx->configure_security(sec_cfg, security::integrity_enabled::on, security::ciphering_enabled::on);

    byte_buffer test_pdu1;
    get_test_pdu(count, test_pdu1);
    byte_buffer test_pdu2;
    get_test_pdu(count + 1, test_pdu2);
    pdcp_rx_state init_state = {.rx_next = count, .rx_deliv = count, .rx_reord = 0};
    pdcp_rx->set_state(init_state);
    pdcp_rx->handle_pdu(byte_buffer_chain::create(std::move(test_pdu2)).value());

    // Wait for crypto and reordering
    wait_pending_crypto();
    worker.run_pending_tasks();
    ASSERT_EQ(0, test_frame->sdu_queue.size());
    tick_all(10);
    ASSERT_EQ(1, test_frame->sdu_queue.size());
    pdcp_rx->handle_pdu(byte_buffer_chain::create(std::move(test_pdu1)).value());

    // Wait for crypto and reordering
    wait_pending_crypto();
    worker.run_pending_tasks();
    ASSERT_EQ(1, test_frame->sdu_queue.size());
    while (not test_frame->sdu_queue.empty()) {
      ASSERT_EQ(test_frame->sdu_queue.front(), sdu1);
      test_frame->sdu_queue.pop();
    }
  };
  if (sn_size == pdcp_sn_size::size12bits) {
    test_rx_t_reorder(0);
    test_rx_t_reorder(2047);
    test_rx_t_reorder(4095);
  } else if (sn_size == pdcp_sn_size::size18bits) {
    test_rx_t_reorder(0);
    test_rx_t_reorder(131071);
    test_rx_t_reorder(262143);
  } else {
    FAIL();
  }

  // No warnings or errors
  EXPECT_EQ(test_spy.get_warning_counter(), 0);
  EXPECT_EQ(test_spy.get_error_counter(), 0);

  EXPECT_EQ(pdcp_rohc_factory->get_nof_compressors(), 0);
  EXPECT_EQ(pdcp_rohc_factory->get_nof_decompressors(), exp_nof_decompressors);
}

/// Test out of order reception of PDUs.
/// t-Reordering is set to 0, so PDUs are immediately delivered.
TEST_P(pdcp_rx_test_drb, rx_reordering_timer_0ms)
{
  init(std::get<pdcp_sn_size>(GetParam()),
       std::get<unsigned>(GetParam()),
       std::get<rohc_test_params>(GetParam()),
       pdcp_rb_type::drb,
       pdcp_rlc_mode::am,
       pdcp_t_reordering::ms0);
  unsigned exp_nof_decompressors = header_compression.has_value() ? 1 : 0;
  EXPECT_EQ(pdcp_rohc_factory->get_nof_compressors(), 0);
  EXPECT_EQ(pdcp_rohc_factory->get_nof_decompressors(), exp_nof_decompressors);

  auto test_rx_t_reorder = [this](uint32_t count) {
    ocudu::test_delimit_logger delimiter(
        "RX out-of-order test, t-Reordering is set to 0. SN_SIZE={} COUNT=[{}, {}]", sn_size, count + 1, count);

    pdcp_rx->configure_security(sec_cfg, security::integrity_enabled::on, security::ciphering_enabled::on);

    byte_buffer test_pdu1;
    get_test_pdu(count, test_pdu1);
    byte_buffer test_pdu2;
    get_test_pdu(count + 1, test_pdu2);
    pdcp_rx_state init_state = {.rx_next = count, .rx_deliv = count, .rx_reord = 0};
    pdcp_rx->set_state(init_state);
    pdcp_rx->handle_pdu(byte_buffer_chain::create(std::move(test_pdu2)).value());

    // Wait for crypto and reordering
    wait_pending_crypto();
    worker.run_pending_tasks();
    ASSERT_EQ(1, test_frame->sdu_queue.size());
    pdcp_rx->handle_pdu(byte_buffer_chain::create(std::move(test_pdu1)).value());

    // Wait for crypto and reordering
    wait_pending_crypto();
    worker.run_pending_tasks();
    ASSERT_EQ(1, test_frame->sdu_queue.size());
    while (not test_frame->sdu_queue.empty()) {
      ASSERT_EQ(test_frame->sdu_queue.front(), sdu1);
      test_frame->sdu_queue.pop();
    }
  };
  if (sn_size == pdcp_sn_size::size12bits) {
    test_rx_t_reorder(0);
    test_rx_t_reorder(2047);
    test_rx_t_reorder(4095);
  } else if (sn_size == pdcp_sn_size::size18bits) {
    test_rx_t_reorder(0);
    test_rx_t_reorder(131071);
    test_rx_t_reorder(262143);
  } else {
    FAIL();
  }

  // No warnings or errors
  EXPECT_EQ(test_spy.get_warning_counter(), 0);
  EXPECT_EQ(test_spy.get_error_counter(), 0);

  EXPECT_EQ(pdcp_rohc_factory->get_nof_compressors(), 0);
  EXPECT_EQ(pdcp_rohc_factory->get_nof_decompressors(), exp_nof_decompressors);
}

/// Test out of order reception of PDUs.
/// t-Reordering is set to infinite, so  no PDUs are delivered
/// until they are received in order.
TEST_P(pdcp_rx_test_drb, rx_reordering_timer_infinite)
{
  init(std::get<pdcp_sn_size>(GetParam()),
       std::get<unsigned>(GetParam()),
       std::get<rohc_test_params>(GetParam()),
       pdcp_rb_type::drb,
       pdcp_rlc_mode::am,
       pdcp_t_reordering::infinity);
  unsigned exp_nof_decompressors = header_compression.has_value() ? 1 : 0;
  EXPECT_EQ(pdcp_rohc_factory->get_nof_compressors(), 0);
  EXPECT_EQ(pdcp_rohc_factory->get_nof_decompressors(), exp_nof_decompressors);

  auto test_rx_t_reorder = [this](uint32_t count) {
    ocudu::test_delimit_logger delimiter(
        "RX out-of-order test, t-Reordering is set to infinity. SN_SIZE={} COUNT=[{}, {}]", sn_size, count + 1, count);

    pdcp_rx->configure_security(sec_cfg, security::integrity_enabled::on, security::ciphering_enabled::on);

    byte_buffer test_pdu1;
    get_test_pdu(count, test_pdu1);
    byte_buffer test_pdu2;
    get_test_pdu(count + 1, test_pdu2);
    pdcp_rx_state init_state = {.rx_next = count, .rx_deliv = count, .rx_reord = 0};
    pdcp_rx->set_state(init_state);
    pdcp_rx->handle_pdu(byte_buffer_chain::create(std::move(test_pdu2)).value());
    tick_all(6000); // max t-Reordering is 3000ms

    // Wait for crypto and reordering
    wait_pending_crypto();
    worker.run_pending_tasks();
    ASSERT_EQ(0, test_frame->sdu_queue.size());

    pdcp_rx->handle_pdu(byte_buffer_chain::create(std::move(test_pdu1)).value());

    // Wait for crypto and reordering
    wait_pending_crypto();
    worker.run_pending_tasks();
    ASSERT_EQ(2, test_frame->sdu_queue.size());
    while (not test_frame->sdu_queue.empty()) {
      ASSERT_EQ(test_frame->sdu_queue.front(), sdu1);
      test_frame->sdu_queue.pop();
    }
  };
  if (sn_size == pdcp_sn_size::size12bits) {
    test_rx_t_reorder(0);
    test_rx_t_reorder(2047);
    test_rx_t_reorder(4095);
  } else if (sn_size == pdcp_sn_size::size18bits) {
    test_rx_t_reorder(0);
    test_rx_t_reorder(131071);
    test_rx_t_reorder(262143);
  } else {
    FAIL();
  }

  // One warning but no errors
  EXPECT_EQ(test_spy.get_warning_counter(), 1);
  EXPECT_EQ(test_spy.get_error_counter(), 0);

  EXPECT_EQ(pdcp_rohc_factory->get_nof_compressors(), 0);
  EXPECT_EQ(pdcp_rohc_factory->get_nof_decompressors(), exp_nof_decompressors);
}

/// Test reception of PDUs with bad integrity checks.
/// The PDCP should notify the RRC of the integrity error.
TEST_P(pdcp_rx_test_drb, rx_integrity_fail)
{
  init(std::get<pdcp_sn_size>(GetParam()), std::get<unsigned>(GetParam()), std::get<rohc_test_params>(GetParam()));
  unsigned exp_nof_decompressors = header_compression.has_value() ? 1 : 0;
  EXPECT_EQ(pdcp_rohc_factory->get_nof_compressors(), 0);
  EXPECT_EQ(pdcp_rohc_factory->get_nof_decompressors(), exp_nof_decompressors);

  auto test_rx_integrity_fail = [this](uint32_t count) {
    ocudu::test_delimit_logger delimiter("RX PDU with bad integrity. SN_SIZE={} COUNT={}", sn_size, count);

    pdcp_rx->configure_security(sec_cfg, security::integrity_enabled::on, security::ciphering_enabled::on);

    byte_buffer test_pdu1;
    get_test_pdu(count, test_pdu1);
    ASSERT_TRUE(test_pdu1.append(0)); // mess up MAC-I
    pdcp_rx_state init_state = {.rx_next = count, .rx_deliv = count, .rx_reord = 0};
    pdcp_rx->set_state(init_state);
    uint32_t prev_integrity_fail_counter = test_frame->integrity_fail_counter;
    pdcp_rx->handle_pdu(byte_buffer_chain::create(std::move(test_pdu1)).value());

    // Wait for crypto and reordering
    wait_pending_crypto();
    worker.run_pending_tasks();
    ASSERT_EQ(0, test_frame->sdu_queue.size());
    ASSERT_EQ(prev_integrity_fail_counter + 1, test_frame->integrity_fail_counter);
  };

  if (sn_size == pdcp_sn_size::size12bits) {
    test_rx_integrity_fail(0);
    test_rx_integrity_fail(2047);
    test_rx_integrity_fail(4095);
  } else if (sn_size == pdcp_sn_size::size18bits) {
    test_rx_integrity_fail(0);
    test_rx_integrity_fail(131071);
    test_rx_integrity_fail(262143);
  } else {
    FAIL();
  }

  // Three warnings but no errors
  EXPECT_EQ(test_spy.get_warning_counter(), 3);
  EXPECT_EQ(test_spy.get_error_counter(), 0);

  EXPECT_EQ(pdcp_rohc_factory->get_nof_compressors(), 0);
  EXPECT_EQ(pdcp_rohc_factory->get_nof_decompressors(), exp_nof_decompressors);
}

/// Test reception of SRB PDUs with zero-padded MAC-I across all integrity modes (off, on, SMC transition mode).
/// The PDCP should reject the PDUs only in when integrity is fully enabled.
TEST_P(pdcp_rx_test_srb, rx_zero_padded_mac)
{
  init(pdcp_sn_size::size12bits, 2, cfg_rohc_disabled, pdcp_rb_type::srb);
  unsigned exp_nof_decompressors = header_compression.has_value() ? 1 : 0;
  EXPECT_EQ(pdcp_rohc_factory->get_nof_compressors(), 0);
  EXPECT_EQ(pdcp_rohc_factory->get_nof_decompressors(), exp_nof_decompressors);

  auto test_rx_integrity_mode = [this](uint32_t count) {
    ocudu::test_delimit_logger delimiter("RX PDU with unverified integrity. SN_SIZE={} COUNT={}", sn_size, count);

    if (std::get<security::integrity_enabled>(GetParam()) != security::integrity_enabled::off) {
      pdcp_rx->configure_security(
          sec_cfg, std::get<security::integrity_enabled>(GetParam()), security::ciphering_enabled::off);
    }

    byte_buffer test_pdu1;
    get_test_pdu(count, test_pdu1);
    // overwrite MAC-I with zero padding
    byte_buffer_view mac{test_pdu1, test_pdu1.length() - security::sec_mac_len, security::sec_mac_len};
    std::fill(mac.begin(), mac.end(), 0x0);
    pdcp_rx_state init_state = {.rx_next = count, .rx_deliv = count, .rx_reord = 0};
    pdcp_rx->set_state(init_state);
    uint32_t prev_integrity_fail_counter = test_frame->integrity_fail_counter;
    pdcp_rx->handle_pdu(byte_buffer_chain::create(std::move(test_pdu1)).value());

    // Wait for crypto and reordering
    wait_pending_crypto();
    worker.run_pending_tasks();
    if (std::get<security::integrity_enabled>(GetParam()) == security::integrity_enabled::on) {
      // Integrity on: Expect PDU to be dropped.
      ASSERT_EQ(0, test_frame->sdu_queue.size());
      ASSERT_EQ(prev_integrity_fail_counter + 1, test_frame->integrity_fail_counter);
    } else {
      // Integrity off or in SMC transition: Expect PDU to pass.
      ASSERT_EQ(1, test_frame->sdu_queue.size());
      ASSERT_EQ(prev_integrity_fail_counter, test_frame->integrity_fail_counter);
      while (not test_frame->sdu_queue.empty()) {
        test_frame->sdu_queue.pop();
      }
    }
  };

  test_rx_integrity_mode(0);
  test_rx_integrity_mode(2047);
  test_rx_integrity_mode(4095);

  if (std::get<security::integrity_enabled>(GetParam()) == security::integrity_enabled::on) {
    // Three warnings but no errors
    EXPECT_EQ(test_spy.get_warning_counter(), 3);
    EXPECT_EQ(test_spy.get_error_counter(), 0);
  } else {
    // No warnings and no errors
    EXPECT_EQ(test_spy.get_warning_counter(), 0);
    EXPECT_EQ(test_spy.get_error_counter(), 0);
  }

  EXPECT_EQ(pdcp_rohc_factory->get_nof_compressors(), 0);
  EXPECT_EQ(pdcp_rohc_factory->get_nof_decompressors(), exp_nof_decompressors);
}

/// Test reception of SRB PDUs with non zero-padded MAC-I across all integrity modes (off, on, SMC transition mode).
/// The PDCP should reject all PDUs.
TEST_P(pdcp_rx_test_srb, rx_non_zero_padded_mac)
{
  init(pdcp_sn_size::size12bits, 2, cfg_rohc_disabled, pdcp_rb_type::srb);
  unsigned exp_nof_decompressors = header_compression.has_value() ? 1 : 0;
  EXPECT_EQ(pdcp_rohc_factory->get_nof_compressors(), 0);
  EXPECT_EQ(pdcp_rohc_factory->get_nof_decompressors(), exp_nof_decompressors);

  auto test_rx_integrity_mode = [this](uint32_t count) {
    ocudu::test_delimit_logger delimiter("RX PDU with unverified integrity. SN_SIZE={} COUNT={}", sn_size, count);

    if (std::get<security::integrity_enabled>(GetParam()) != security::integrity_enabled::off) {
      pdcp_rx->configure_security(
          sec_cfg, std::get<security::integrity_enabled>(GetParam()), security::ciphering_enabled::off);
    }

    byte_buffer test_pdu1;
    get_test_pdu(count, test_pdu1);
    // overwrite MAC-I with non-zero padding
    byte_buffer_view mac{test_pdu1, test_pdu1.length() - security::sec_mac_len, security::sec_mac_len};
    std::fill(mac.begin(), mac.end(), 0x1);
    pdcp_rx_state init_state = {.rx_next = count, .rx_deliv = count, .rx_reord = 0};
    pdcp_rx->set_state(init_state);
    uint32_t prev_integrity_fail_counter = test_frame->integrity_fail_counter;
    pdcp_rx->handle_pdu(byte_buffer_chain::create(std::move(test_pdu1)).value());

    // Wait for crypto and reordering
    wait_pending_crypto();
    worker.run_pending_tasks();

    // Expect PDU to be dropped.
    ASSERT_EQ(0, test_frame->sdu_queue.size());
    ASSERT_EQ(prev_integrity_fail_counter + 1, test_frame->integrity_fail_counter);
  };

  test_rx_integrity_mode(0);
  test_rx_integrity_mode(2047);
  test_rx_integrity_mode(4095);

  // Three warnings but no errors
  EXPECT_EQ(test_spy.get_warning_counter(), 3);
  EXPECT_EQ(test_spy.get_error_counter(), 0);

  EXPECT_EQ(pdcp_rohc_factory->get_nof_compressors(), 0);
  EXPECT_EQ(pdcp_rohc_factory->get_nof_decompressors(), exp_nof_decompressors);
}

/// Test count wrap-around protection for PDCP RX
/// Receive one PDU before notify limit, four after notify
/// limit and one after the hard limit.
TEST_P(pdcp_rx_test_drb, count_wraparound)
{
  uint32_t       rx_next_notify = 262144;
  uint32_t       rx_next_max    = 262148;
  uint32_t       rx_next_start  = 262143;
  uint32_t       n_sdus         = 6;
  pdcp_max_count max_count{rx_next_notify, rx_next_max};
  init(std::get<pdcp_sn_size>(GetParam()),
       std::get<unsigned>(GetParam()),
       std::get<rohc_test_params>(GetParam()),
       pdcp_rb_type::drb,
       pdcp_rlc_mode::am,
       pdcp_t_reordering::ms10,
       max_count);
  unsigned exp_nof_decompressors = header_compression.has_value() ? 1 : 0;
  EXPECT_EQ(pdcp_rohc_factory->get_nof_compressors(), 0);
  EXPECT_EQ(pdcp_rohc_factory->get_nof_decompressors(), exp_nof_decompressors);

  auto test_max_count = [this, n_sdus](uint32_t count) {
    // Set state of PDCP entiy
    // Do not enable integrity or ciphering, to make it easier to generate test vectors.
    pdcp_rx_state init_state = {.rx_next = count, .rx_deliv = count, .rx_reord = 0};
    pdcp_rx->set_state(init_state);

    pdcp_rx->configure_security(sec_cfg, security::integrity_enabled::off, security::ciphering_enabled::off);

    // Write SDUs
    for (uint32_t i = 0; i < n_sdus; i++) {
      byte_buffer pdu;
      get_test_pdu(count + i, pdu);
      pdcp_rx->handle_pdu(byte_buffer_chain::create(std::move(pdu)).value());
    }
    // Wait for crypto and reordering
    wait_pending_crypto();
    worker.run_pending_tasks();

    // check nof max_count reached and max protocol failures.
    ASSERT_EQ(5, test_frame->sdu_queue.size());
    ASSERT_EQ(1, test_frame->nof_max_count_reached);
    ASSERT_EQ(1, test_frame->nof_protocol_failure);
  };

  test_max_count(rx_next_start);

  // One warning and one error
  EXPECT_EQ(test_spy.get_warning_counter(), 1);
  EXPECT_EQ(test_spy.get_error_counter(), 1);

  EXPECT_EQ(pdcp_rohc_factory->get_nof_compressors(), 0);
  EXPECT_EQ(pdcp_rohc_factory->get_nof_decompressors(), exp_nof_decompressors);
}

/// Test TX SDU buffering.
TEST_P(pdcp_rx_test_drb, rx_buffer)
{
  uint32_t n_no_buffer_pdus = 1;
  uint32_t n_buffer_pdus    = 2;
  init(std::get<pdcp_sn_size>(GetParam()), std::get<unsigned>(GetParam()), std::get<rohc_test_params>(GetParam()));
  unsigned exp_nof_decompressors = header_compression.has_value() ? 1 : 0;
  EXPECT_EQ(pdcp_rohc_factory->get_nof_compressors(), 0);
  EXPECT_EQ(pdcp_rohc_factory->get_nof_decompressors(), exp_nof_decompressors);

  pdcp_rx->configure_security(sec_cfg, security::integrity_enabled::on, security::ciphering_enabled::on);

  for (uint32_t count = 0; count < n_no_buffer_pdus; count++) {
    byte_buffer test_pdu;
    get_test_pdu(count, test_pdu);
    pdcp_rx->handle_pdu(byte_buffer_chain::create(std::move(test_pdu)).value());
  }

  // Wait for crypto and reordering.
  wait_pending_crypto();
  worker.run_pending_tasks();

  // Check SDUs were received correctly.
  FLUSH_AND_ASSERT_EQ(1, test_frame->sdu_queue.size());
  test_frame->sdu_queue = {}; // clear queue.

  pdcp_rx->begin_buffering();
  for (uint32_t n = 0; n < n_buffer_pdus; n++) {
    uint32_t    count = n_no_buffer_pdus + n;
    byte_buffer test_pdu;
    get_test_pdu(count, test_pdu);
    pdcp_rx->handle_pdu(byte_buffer_chain::create(std::move(test_pdu)).value());
  }
  FLUSH_AND_ASSERT_EQ(0, test_frame->sdu_queue.size());
  pdcp_rx->end_buffering();
  wait_pending_crypto();
  worker.run_pending_tasks();
  FLUSH_AND_ASSERT_EQ(2, test_frame->sdu_queue.size());

  // No warnings or errors
  EXPECT_EQ(test_spy.get_warning_counter(), 0);
  EXPECT_EQ(test_spy.get_error_counter(), 0);

  EXPECT_EQ(pdcp_rohc_factory->get_nof_compressors(), 0);
  EXPECT_EQ(pdcp_rohc_factory->get_nof_decompressors(), exp_nof_decompressors);
}

///////////////////////////////////////////////////////////////////
// Finally, instantiate all testcases for each supported SN size //
///////////////////////////////////////////////////////////////////
static std::string pdcp_rx_test_drb_param_info_to_string(
    const ::testing::TestParamInfo<std::tuple<pdcp_sn_size, unsigned, rohc_test_params>>& info)
{
  fmt::memory_buffer buffer;
  fmt::format_to(std::back_inserter(buffer),
                 "{}bit_nia{}_nea{}_{}",
                 pdcp_sn_size_to_uint(std::get<pdcp_sn_size>(info.param)),
                 std::get<unsigned>(info.param),
                 std::get<unsigned>(info.param),
                 std::get<rohc_test_params>(info.param).name);
  return fmt::to_string(buffer);
}

INSTANTIATE_TEST_SUITE_P(
    pdcp_rx_test_all_variants,
    pdcp_rx_test_drb,
    ::testing::Combine(::testing::Values(pdcp_sn_size::size12bits, pdcp_sn_size::size18bits),
                       ::testing::Values(1, 2, 3),
                       ::testing::Values(cfg_rohc_disabled, cfg_rohc_uncompressed, cfg_rohc_compressed)),
    pdcp_rx_test_drb_param_info_to_string);

static std::string pdcp_rx_test_srb_param_info_to_string(
    const ::testing::TestParamInfo<std::tuple<unsigned, security::integrity_enabled>>& info)
{
  fmt::memory_buffer buffer;
  fmt::format_to(std::back_inserter(buffer),
                 "nia{}_{}_nea{}",
                 std::get<unsigned>(info.param),
                 std::get<security::integrity_enabled>(info.param),
                 std::get<unsigned>(info.param));
  return fmt::to_string(buffer);
}

INSTANTIATE_TEST_SUITE_P(pdcp_rx_test_all_variants,
                         pdcp_rx_test_srb,
                         ::testing::Combine(::testing::Values(1, 2, 3),
                                            ::testing::Values(security::integrity_enabled::off,
                                                              security::integrity_enabled::on,
                                                              security::integrity_enabled::smc_transition)),
                         pdcp_rx_test_srb_param_info_to_string);

class pdcp_rx_stormbrain_test : public pdcp_rx_test_helper_default_crypto, public ::testing::Test {
protected:

  void SetUp() override {
    ocudulog::init();
    // Disable all logs except those related to PDCP.
    // Reactivate others only if debugging errors in the implementation.
    // Focus exclusively on DRB-related logs.
    ocudulog::fetch_basic_logger("PDCP", false).set_level(ocudulog::basic_levels::debug);
    ocudulog::fetch_basic_logger("PDCP", false).set_hex_dump_max_size(100);

    // Initialize with 12-bit SN, AM RLC mode, and 10ms reordering timer
    init(pdcp_sn_size::size12bits, 2, cfg_rohc_disabled, pdcp_rb_type::drb, pdcp_rlc_mode::am, pdcp_t_reordering::ms10);

    // Disable integrity and ciphering to allow raw injection without cipher/MAC checks
    pdcp_rx->configure_security(sec_cfg, security::integrity_enabled::off, security::ciphering_enabled::off);
  }

  void TearDown() override {
    ocudulog::flush();
  }

  // Helper to create unprotected PDU with 12-bit SN
  byte_buffer create_pdu(uint16_t sn) {
    byte_buffer pdu;
    if (not pdu.resize(4)) {
      report_fatal_error("Failed to resize byte buffer");
    }
    pdu[0] = 0x80 | ((sn >> 8) & 0x0F);
    pdu[1] = sn & 0xFF;
    pdu[2] = 0x18;
    pdu[3] = 0xe2;
    return pdu;
  }

  // Helper to inject sequence numbers continuously with 1ms interval
  void inject_sns(const std::vector<uint16_t>& sns) {
    for (uint16_t sn : sns) {
      fmt::print("[Sim Time: {} ms] Injecting SN={}\n", timers.now(), sn);
      pdcp_rx->handle_pdu(byte_buffer_chain::create(create_pdu(sn)).value());
      wait_pending_crypto();
      worker.run_pending_tasks();
      tick_all(1);
    }
  }

  // Helper to print PDU fields and format in detail
  void print_pdu_structure(uint32_t sim_time, const std::string& prefix, const byte_buffer& pdu) {
    if (pdu.length() < 2) {
      fmt::print("[Sim Time: {} ms] {} Invalid PDU length: {}\n", sim_time, prefix, pdu.length());
      return;
    }
    bool dc_bit = (pdu[0] & 0x80) != 0;
    uint16_t sn = ((pdu[0] & 0x0F) << 8) | pdu[1];
    
    fmt::print("[Sim Time: {} ms] {} Detailed PDU Structure:\n", sim_time, prefix);
    fmt::print("  - Type: {}\n", dc_bit ? "Data PDU" : "Control PDU");
    fmt::print("  - Sequence Number (SN): {}\n", sn);
    fmt::print("  - Header Bytes: {:02x} {:02x}\n", pdu[0], pdu[1]);
    
    size_t payload_len = pdu.length() - 2;
    // NIA2/NEA2 adds 4 bytes of MAC-I at the end if integrity is enabled
    bool has_mac = payload_len >= 4;
    size_t data_len = has_mac ? (payload_len - 4) : payload_len;
    
    if (data_len > 0) {
      std::vector<uint8_t> data_bytes(data_len);
      for (size_t idx = 0; idx < data_len; ++idx) {
        data_bytes[idx] = pdu[2 + idx];
      }
      fmt::print("  - Encrypted Payload Bytes (Length {}): {:02x}\n", data_len, fmt::join(data_bytes, " "));
    }
    
    if (has_mac) {
      std::vector<uint8_t> mac_bytes(4);
      for (size_t idx = 0; idx < 4; ++idx) {
        mac_bytes[idx] = pdu[pdu.length() - 4 + idx];
      }
      fmt::print("  - Message Authentication Code (MAC-I): {:02x}\n", fmt::join(mac_bytes, " "));
    }
    fmt::print("  - Full PDU hex dump: {:02x}\n", fmt::join(pdu, " "));
  }

  // Helper to create decrypted (unencrypted) PDU with dummy MAC-I
  byte_buffer create_decrypted_pdu_with_dummy_mac(uint16_t sn) {
    byte_buffer pdu;
    if (not pdu.resize(8)) {
      report_fatal_error("Failed to resize byte buffer");
    }
    pdu[0] = 0x80 | ((sn >> 8) & 0x0F);
    pdu[1] = sn & 0xFF;
    pdu[2] = 0x18; // Unencrypted SDU payload (sdu1)
    pdu[3] = 0xe2;
    pdu[4] = 0x00; // Dummy MAC-I
    pdu[5] = 0x00;
    pdu[6] = 0x00;
    pdu[7] = 0x00;
    return pdu;
  }
};

TEST_F(pdcp_rx_stormbrain_test, TestA_DuplicatedScenario)
{
  ocudu::test_delimit_logger delimiter("Stormbrain Test A: Duplicated Scenario");

  // Injected RX Sequence: 1, 2, 2, 3, 4
  pdcp_rx_state init_state = {.rx_next = 1, .rx_deliv = 1, .rx_reord = 0};
  pdcp_rx->set_state(init_state);

  inject_sns({1, 2, 2, 3, 4});

  // Verify: The receiver must discard the second 2 because it is a duplicate.
  // Delivered SDUs should be 1, 2, 3, 4 (exactly 4 SDUs)
  ASSERT_EQ(test_frame->sdu_queue.size(), 4);

  while (!test_frame->sdu_queue.empty()) {
    test_frame->sdu_queue.pop();
  }
}

TEST_F(pdcp_rx_stormbrain_test, TestB_PlayingWithTReordering)
{
  ocudu::test_delimit_logger delimiter("Stormbrain Test B: Playing with t-Reordering");

  pdcp_rx_state init_state = {.rx_next = 1, .rx_deliv = 1, .rx_reord = 0};
  pdcp_rx->set_state(init_state);

  // 1. Inject 1
  inject_sns({1});
  ASSERT_EQ(test_frame->sdu_queue.size(), 1);
  EXPECT_FALSE(pdcp_rx->is_reordering_timer_running());

  // 2. Inject 3
  inject_sns({3});
  // 3 is out-of-order, buffered. Timer starts.
  ASSERT_EQ(test_frame->sdu_queue.size(), 1);
  EXPECT_TRUE(pdcp_rx->is_reordering_timer_running());
  EXPECT_EQ(pdcp_rx->get_state().rx_reord, 4);

  // 3. Wait for timer expiration
  tick_all(10);
  // Timer expires. 3 is delivered. rx_deliv becomes 4.
  ASSERT_EQ(test_frame->sdu_queue.size(), 2);
  EXPECT_FALSE(pdcp_rx->is_reordering_timer_running());
  EXPECT_EQ(pdcp_rx->get_state().rx_deliv, 4);

  // 4. Inject 5
  inject_sns({5});
  // 5 is out-of-order, buffered, timer starts.
  ASSERT_EQ(test_frame->sdu_queue.size(), 2);
  EXPECT_TRUE(pdcp_rx->is_reordering_timer_running());
  EXPECT_EQ(pdcp_rx->get_state().rx_reord, 6);

  // 5. Inject 5 again (duplicate)
  inject_sns({5});
  ASSERT_EQ(test_frame->sdu_queue.size(), 2);

  // 6. Inject 3 and 2
  inject_sns({3, 2});
  // Both are discarded (3 is duplicate/too late, 2 is too late since rx_deliv = 4)
  ASSERT_EQ(test_frame->sdu_queue.size(), 2);

  // 7. Tick to let the second timer expire
  tick_all(10);
  // Timer expires. 5 is delivered. rx_deliv becomes 6.
  ASSERT_EQ(test_frame->sdu_queue.size(), 3);
  EXPECT_FALSE(pdcp_rx->is_reordering_timer_running());
  EXPECT_EQ(pdcp_rx->get_state().rx_deliv, 6);

  while (!test_frame->sdu_queue.empty()) {
    test_frame->sdu_queue.pop();
  }
}

TEST_F(pdcp_rx_stormbrain_test, TestC_ComplexTReorderingBehavior)
{
  ocudu::test_delimit_logger delimiter("Stormbrain Test C: Complex t-Reordering Behavior");

  pdcp_rx_state init_state = {.rx_next = 1, .rx_deliv = 1, .rx_reord = 0};
  pdcp_rx->set_state(init_state);

  // 1. Inject 1, 2, 3
  inject_sns({1, 2, 3});
  ASSERT_EQ(test_frame->sdu_queue.size(), 3);
  EXPECT_FALSE(pdcp_rx->is_reordering_timer_running());
  EXPECT_EQ(pdcp_rx->get_state().rx_deliv, 4);

  // 2. Inject 8
  inject_sns({8});
  // 8 is out-of-order, triggers timer. rx_next = 9, rx_reord = 9.
  ASSERT_EQ(test_frame->sdu_queue.size(), 3);
  EXPECT_TRUE(pdcp_rx->is_reordering_timer_running());
  EXPECT_EQ(pdcp_rx->get_state().rx_reord, 9);
  EXPECT_EQ(pdcp_rx->get_state().rx_next, 9);

  // 3. Inject 4
  inject_sns({4});
  // 4 is consecutive, delivered immediately. rx_deliv becomes 5.
  ASSERT_EQ(test_frame->sdu_queue.size(), 4);
  EXPECT_TRUE(pdcp_rx->is_reordering_timer_running());
  EXPECT_EQ(pdcp_rx->get_state().rx_deliv, 5);

  // 4. Inject 6, 9, 10, 12
  inject_sns({6, 9, 10, 12});
  // All are out of order, buffered. rx_next = 13.
  ASSERT_EQ(test_frame->sdu_queue.size(), 4);
  EXPECT_TRUE(pdcp_rx->is_reordering_timer_running());
  EXPECT_EQ(pdcp_rx->get_state().rx_reord, 9);
  EXPECT_EQ(pdcp_rx->get_state().rx_next, 13);

  // 5. Timer expires
  tick_all(10);
  // Deliver < rx_reord (9) => 6, 8. And consecutive => 9, 10.
  // Delivered: 6, 8, 9, 10. (Total delivered: 4 + 4 = 8).
  // rx_deliv becomes 11.
  // Since rx_deliv (11) < rx_next (13), a new timer starts with rx_reord = 13.
  ASSERT_EQ(test_frame->sdu_queue.size(), 8);
  EXPECT_TRUE(pdcp_rx->is_reordering_timer_running());
  EXPECT_EQ(pdcp_rx->get_state().rx_reord, 13);
  EXPECT_EQ(pdcp_rx->get_state().rx_deliv, 11);

  // 6. Inject 14, 13
  inject_sns({14, 13});
  // Buffered. rx_next = 15.
  ASSERT_EQ(test_frame->sdu_queue.size(), 8);
  EXPECT_TRUE(pdcp_rx->is_reordering_timer_running());

  // 7. Do not inject 11, instead wait for timer expiration
  // inject_sns({11});
  fmt::print("[Sim Time: {} ms] Waiting 10ms for timer expiration...\n", timers.now());
  tick_all(10);
  fmt::print("[Sim Time: {} ms] Timer expired. Deliver < 13 => 12. And consecutive starting from 13 => 13, 14.\n", timers.now());
  // Delivered: 12, 13, 14. (Total delivered: 8 + 3 = 11).
  // rx_deliv becomes 15.
  // Active timer stops because rx_deliv (15) >= rx_reord (13).
  ASSERT_EQ(test_frame->sdu_queue.size(), 11);
  EXPECT_FALSE(pdcp_rx->is_reordering_timer_running());
  EXPECT_EQ(pdcp_rx->get_state().rx_deliv, 15);

  // 8. Inject 15, 16
  inject_sns({15, 16});
  // Instantly delivered. (Total delivered: 11 + 2 = 13).
  ASSERT_EQ(test_frame->sdu_queue.size(), 13);
  EXPECT_FALSE(pdcp_rx->is_reordering_timer_running());

  while (!test_frame->sdu_queue.empty()) {
    test_frame->sdu_queue.pop();
  }
}

TEST_F(pdcp_rx_stormbrain_test, TestD_MiddleServerImplementation)
{
  ocudu::test_delimit_logger delimiter("Stormbrain Test D: Middle Server Simulation");

  // Configure security with integrity and ciphering enabled (NIA2/NEA2)
  pdcp_rx->configure_security(sec_cfg, security::integrity_enabled::on, security::ciphering_enabled::on);

  pdcp_rx_state init_state = {.rx_next = 0, .rx_deliv = 0, .rx_reord = 0};
  pdcp_rx->set_state(init_state);

  std::vector<unique_timer> delay_timers;
  int total_packets = 3;

  // 1. Send decrypted packets (COUNT 0 to 2)
  for (int i = 0; i < total_packets; ++i) {
    uint32_t count = i;
    byte_buffer cu_packet = create_decrypted_pdu_with_dummy_mac(count);

    print_pdu_structure(timers.now(), "[Middle Server] Intercepted Decrypted PDU from CU:", cu_packet);

    // Pathway A: Direct injection to UE
    pdcp_rx->handle_pdu(byte_buffer_chain::create(cu_packet.deep_copy().value()).value());
    wait_pending_crypto();
    worker.run_pending_tasks();
    fmt::print("[Sim Time: {} ms] [Middle Server] Direct injected SN={} to UE\n", timers.now(), count);

    // Pathway B: Schedule duplicate injection after 1000ms
    auto delay_timer = timers.create_unique_timer(ul_worker);
    byte_buffer dup_pdu = cu_packet.deep_copy().value();
    delay_timer.set(timer_duration{1000}, [this, count, dup_pdu = std::move(dup_pdu)](timer_id_t) mutable {
      fmt::print("[Sim Time: {} ms] [Middle Server] 1-second delay expired. Injecting duplicate PDU to UE for SN={}\n", timers.now(), count);
      pdcp_rx->handle_pdu(byte_buffer_chain::create(std::move(dup_pdu)).value());
      wait_pending_crypto();
      worker.run_pending_tasks();
    });
    delay_timer.run();
    delay_timers.push_back(std::move(delay_timer));

    // Increment simulation time by 1 ms per packet injection
    tick_all(1);
  }

  // Verify all 3 packets failed integrity checks and were NOT delivered (queue size is 0)
  ASSERT_EQ(test_frame->sdu_queue.size(), 0);
  ASSERT_EQ(test_frame->integrity_fail_counter, 3);

  // 2. Wait for 1000 ms to expire the duplicate timers
  fmt::print("[Sim Time: {} ms] Waiting 1000ms for duplicate injections...\n", timers.now());
  
  // Tick to advance simulation time and trigger duplicate expirations
  tick_all(1000);

  // Verify duplicates also failed integrity checks (queue size remains 0, fail counter is 6)
  ASSERT_EQ(test_frame->sdu_queue.size(), 0);
  ASSERT_EQ(test_frame->integrity_fail_counter, 6);

  while (!test_frame->sdu_queue.empty()) {
    test_frame->sdu_queue.pop();
  }
}

TEST_F(pdcp_rx_stormbrain_test, TestE_MockXnBridgeDualPath)
{
  ocudu::test_delimit_logger delimiter("Stormbrain Test E: Mock Xn Bridge Dual Path Simulation");

  pdcp_rx_state init_state = {.rx_next = 1, .rx_deliv = 1, .rx_reord = 0};
  pdcp_rx->set_state(init_state);

  // 1. MN RLC path: Inject SN = 1
  fmt::print("[Sim Time: {} ms] [MN Stack] RLC delivers SN=1\n", timers.now());
  pdcp_rx->handle_pdu(byte_buffer_chain::create(create_pdu(1)).value());
  wait_pending_crypto();
  worker.run_pending_tasks();
  ASSERT_EQ(test_frame->sdu_queue.size(), 1);
  EXPECT_FALSE(pdcp_rx->is_reordering_timer_running());

  // 2. SN RLC path: Inject SN = 3 (arrives out of order, starting reordering timer)
  fmt::print("[Sim Time: {} ms] [SN Stack] RLC delivers SN=3\n", timers.now());
  pdcp_rx->handle_pdu(byte_buffer_chain::create(create_pdu(3)).value());
  wait_pending_crypto();
  worker.run_pending_tasks();
  ASSERT_EQ(test_frame->sdu_queue.size(), 1); // 3 is buffered
  EXPECT_TRUE(pdcp_rx->is_reordering_timer_running());
  EXPECT_EQ(pdcp_rx->get_state().rx_reord, 4);

  // 3. Mock Xn-Bridge: SN stack forwards SN = 2 over loopback/bridge to MN PDCP
  fmt::print("[Sim Time: {} ms] [Mock Xn-Bridge] Forwarding SN=2 from SN to MN PDCP\n", timers.now());
  pdcp_rx->handle_pdu(byte_buffer_chain::create(create_pdu(2)).value());
  wait_pending_crypto();
  worker.run_pending_tasks();

  // All packets (1, 2, 3) delivered. Reordering timer stops.
  ASSERT_EQ(test_frame->sdu_queue.size(), 3);
  EXPECT_FALSE(pdcp_rx->is_reordering_timer_running());

  while (!test_frame->sdu_queue.empty()) {
    test_frame->sdu_queue.pop();
  }
}

int main(int argc, char** argv)
{
  ::testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
