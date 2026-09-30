#!/usr/bin/env python3
"""
Scenario Configuration Generator for 6 Ground & LEO 5G NR Multi-Connectivity Architectures.

Generates self-contained, reproducible YAML configuration files for:
  Scenario 0: CU_g D1_g D2_g (Ground CU, Ground DU1, Ground DU2) - Baseline Pure Terrestrial
  Scenario 1: CU_g D1_g D2_L (Ground CU, Ground DU1, LEO Satellite DU2)
  Scenario 2: CU_g D1_L D2_L (Ground CU, LEO Satellite DU1, LEO Satellite DU2)
  Scenario 3: CU_L D1_g D2_g (LEO Onboard CU, Ground DU1, Ground DU2)
  Scenario 4: CU_L D1_L D2_L (LEO Onboard CU, LEO Satellite DU1, LEO Satellite DU2)
  Scenario 5: CU_L D1_g D2_L (LEO Onboard CU, Ground DU1, LEO Satellite DU2)
"""

import os
import yaml

BASE_DIR = "/root/internship-repo/project"
SCENARIOS_DIR = os.path.join(BASE_DIR, "scenarios")

# LEO Orbital & Channel Constants (600-800 km altitude, 750 km slant range)
LEO_ALTITUDE_KM = 600.0
LEO_ONE_WAY_DELAY_MS = 2.5  # 2.5 ms one-way delay (5 ms RTT, fits within 10-slot RAR window)
BASE_SRATE_HZ = 11.52e6
LEO_RX_OFFSET_SAMPLES = int((LEO_ONE_WAY_DELAY_MS / 1000.0) * BASE_SRATE_HZ)  # 28,800 samples
LEO_K_OFFSET = 6  # 6 slots for RTT scheduling offset

SCENARIO_SPECS = {
    "scenario0_cug_d1g_d2g": {
        "title": "Scenario 0: CU_g D1_g D2_g",
        "desc": "Baseline Terrestrial: Ground CU managing two Terrestrial DUs (Pure TN-TN Dual Connectivity)",
        "cu": "g",
        "d1": "g",
        "d2": "g",
    },
    "scenario1_cug_d1g_d2l": {
        "title": "Scenario 1: CU_g D1_g D2_L",
        "desc": "Ground CU managing Ground DU1 (TN) and LEO Satellite DU2 (NTN)",
        "cu": "g",
        "d1": "g",
        "d2": "L",
    },
    "scenario2_cug_d1l_d2l": {
        "title": "Scenario 2: CU_g D1_L D2_L",
        "desc": "Ground CU managing two orbiting LEO Satellite DUs (Dual-Satellite Diversity)",
        "cu": "g",
        "d1": "L",
        "d2": "L",
    },
    "scenario3_cul_d1g_d2g": {
        "title": "Scenario 3: CU_L D1_g D2_g",
        "desc": "LEO Onboard CU managing two Terrestrial DUs on Ground (Feeder link backhaul)",
        "cu": "L",
        "d1": "g",
        "d2": "g",
    },
    "scenario4_cul_d1l_d2l": {
        "title": "Scenario 4: CU_L D1_L D2_L",
        "desc": "Fully Spaceborne Constellation: LEO CU managing two LEO Satellite DUs (Autonomous Space RAN)",
        "cu": "L",
        "d1": "L",
        "d2": "L",
    },
    "scenario5_cul_d1g_d2l": {
        "title": "Scenario 5: CU_L D1_g D2_L",
        "desc": "Hybrid Space-Ground: LEO CU managing Ground DU1 and LEO Satellite DU2",
        "cu": "L",
        "d1": "g",
        "d2": "L",
    },
}


def build_cu_cp_config(cu_mode: str, scenario_name: str) -> dict:
    cfg = {
        "cu_cp": {
            "request_pdu_session_timeout": 30,
            "inactivity_timer": 7200,
            "amf": {
                "addrs": "127.0.0.5",
                "bind_addrs": "127.0.0.1",
                "supported_tracking_areas": [
                    {
                        "tac": 1,
                        "plmn_list": [
                            {"plmn": "99970", "tai_slice_support_list": [{"sst": 1}]}
                        ],
                    }
                ],
            },
            "e1ap": {"bind_addrs": "127.0.20.1"},
            "f1ap": {"bind_addrs": "127.0.10.1"},
        },
        "log": {
            "filename": f"/tmp/{scenario_name}_cu_cp.log",
            "all_level": "debug",
        },
    }

    if cu_mode == "L":
        # Spaceborne LEO CU: Extended RRC procedure guard timer to tolerate Feeder Link RTT
        cfg["cu_cp"]["rrc"] = {"rrc_procedure_guard_time_ms": 12800}
    else:
        # Ground CU: Standard guard timer
        cfg["cu_cp"]["rrc"] = {"rrc_procedure_guard_time_ms": 5000}

    return cfg


def build_cu_up_config(scenario_name: str) -> dict:
    return {
        "cu_up": {
            "plmn_list": ["99970"],
            "e1ap": {
                "gateways": [{"bind_addrs": "127.0.20.2", "addrs": "127.0.20.1"}]
            },
            "ngu": {"socket": [{"bind_addr": "127.0.0.1"}]},
            "f1u": {"socket": [{"bind_addr": "127.0.10.1"}]},
        },
        "log": {
            "filename": f"/tmp/{scenario_name}_cu_up.log",
            "all_level": "debug",
        },
    }


def build_du_config(
    du_id: int, mode: str, scenario_name: str, tx_port: int, rx_port: int, bind_ip: str
) -> dict:
    device_args = f"tx_port=tcp://127.0.0.1:{tx_port},rx_port=tcp://127.0.0.1:{rx_port},base_srate=11.52e6"
    if mode == "L" and du_id == 2:
        # Inject LEO propagation delay on secondary payload beam (DU2)
        device_args += f",rx_offset={LEO_RX_OFFSET_SAMPLES}"

    cfg = {
        "gnb_du_id": du_id,
        "f1ap": {"addrs": "127.0.10.1", "bind_addrs": bind_ip},
        "f1u": {"socket": [{"bind_addr": bind_ip}]},
        "ru_sdr": {
            "device_driver": "zmq",
            "device_args": device_args,
            "srate": 11.52,
        },
        "cell_cfg": {
            "sector_id": du_id,
            "dl_arfcn": 368500,
            "band": 3,
            "channel_bandwidth_MHz": 10,
            "common_scs": 15,
            "plmn": "99970",
            "tac": 1,
            "pci": du_id,
            "pdcch": {
                "common": {"ss0_index": 0, "coreset0_index": 6},
                "dedicated": {
                    "ss2_type": "common",
                    "dci_format_0_1_and_1_1": False,
                },
            },
            "prach": {
                "prach_config_index": 1,
                "total_nof_ra_preambles": 64,
                "nof_ssb_per_ro": 1,
                "nof_cb_preambles_per_ssb": 64,
            },
            "pdsch": {"mcs_table": "qam64"},
            "pusch": {"mcs_table": "qam64"},
        },
        "log": {
            "filename": f"/tmp/{scenario_name}_du{du_id}.log",
            "all_level": "debug",
        },
    }

    if mode == "L" and du_id == 2:
        # LEO Satellite Secondary Payload Beam (DU2):
        # Full NTN parameters, scheduling koffset, SIB19, and extended CSI/PUCCH
        cfg["cell_cfg"]["ntn"] = {
            "cell_specific_koffset": LEO_K_OFFSET,
            "epoch_timestamp": "2026-01-01T00:00:00",
            "ta_info": {"ta_common": 0},
            "ephemeris_info_ecef": {
                "pos_x": 6971000,
                "pos_y": 0,
                "pos_z": 0,
                "vel_x": 0,
                "vel_y": 7560,
                "vel_z": 0,
            },
        }
        cfg["cell_cfg"]["sib"] = {
            "si_window_length": 5,
            "si_sched_info": [
                {"si_period": 16, "sib_mapping": [2]},
                {"si_period": 16, "sib_mapping": [19], "si_window_position": 2},
            ],
            "sib2": {
                "q_hyst": 3,
                "thresh_serving_low_p": 0,
                "cell_reselection_priority": 6,
                "q_rx_lev_min": -70,
                "s_intra_search_p": 62,
                "t_reselection_nr": 1,
            },
        }
        cfg["cell_cfg"]["pucch"] = {"sr_period_ms": 320}
        cfg["cell_cfg"]["csi"] = {"csi_rs_period": 80}
        cfg["cell_cfg"]["pdsch"]["max_nof_harq_retxs"] = 0
        cfg["cell_cfg"]["prach"]["max_msg3_harq_retx"] = 0

    return cfg


def generate_all():
    os.makedirs(SCENARIOS_DIR, exist_ok=True)
    print(f"[*] Generating configuration files in: {SCENARIOS_DIR}\n")

    for scen_key, spec in SCENARIO_SPECS.items():
        scen_path = os.path.join(SCENARIOS_DIR, scen_key)
        os.makedirs(scen_path, exist_ok=True)

        print(f"=== Generating {spec['title']} ({scen_key}) ===")
        print(f"    Description: {spec['desc']}")
        print(f"    Nodes: CU={spec['cu']}, DU1={spec['d1']}, DU2={spec['d2']}")

        # 1. CU-CP
        cu_cp_cfg = build_cu_cp_config(spec["cu"], scen_key)
        cu_cp_file = os.path.join(scen_path, "cu_cp.yml")
        with open(cu_cp_file, "w") as f:
            f.write(f"# {spec['title']} - CU-CP Configuration\n")
            f.write(f"# CU Location: {'LEO Satellite' if spec['cu'] == 'L' else 'Ground'}\n\n")
            yaml.dump(cu_cp_cfg, f, default_flow_style=False, sort_keys=False)

        # 2. CU-UP
        cu_up_cfg = build_cu_up_config(scen_key)
        cu_up_file = os.path.join(scen_path, "cu_up.yml")
        with open(cu_up_file, "w") as f:
            f.write(f"# {spec['title']} - CU-UP Configuration\n\n")
            yaml.dump(cu_up_cfg, f, default_flow_style=False, sort_keys=False)

        # 3. DU1
        du1_cfg = build_du_config(
            du_id=1,
            mode=spec["d1"],
            scenario_name=scen_key,
            tx_port=2000,
            rx_port=2001,
            bind_ip="127.0.10.2",
        )
        du1_file = os.path.join(scen_path, "du1.yml")
        with open(du1_file, "w") as f:
            f.write(f"# {spec['title']} - DU1 Configuration\n")
            f.write(f"# DU1 Location: {'LEO Satellite Anchor Beam' if spec['d1'] == 'L' else 'Ground (Terrestrial, 0 ms delay)'}\n\n")
            yaml.dump(du1_cfg, f, default_flow_style=False, sort_keys=False)

        # 4. DU2
        du2_cfg = build_du_config(
            du_id=2,
            mode=spec["d2"],
            scenario_name=scen_key,
            tx_port=3000,
            rx_port=3001,
            bind_ip="127.0.10.3",
        )
        du2_file = os.path.join(scen_path, "du2.yml")
        with open(du2_file, "w") as f:
            f.write(f"# {spec['title']} - DU2 Configuration\n")
            f.write(f"# DU2 Location: {'LEO Satellite Secondary Payload (10 ms delay, SIB19)' if spec['d2'] == 'L' else 'Ground (Terrestrial, 0 ms delay)'}\n\n")
            yaml.dump(du2_cfg, f, default_flow_style=False, sort_keys=False)

        print(f"    [+] Created: {cu_cp_file}")
        print(f"    [+] Created: {cu_up_file}")
        print(f"    [+] Created: {du1_file}")
        print(f"    [+] Created: {du2_file}\n")

    print("[SUCCESS] All 6 scenario configurations generated successfully!")


if __name__ == "__main__":
    generate_all()
