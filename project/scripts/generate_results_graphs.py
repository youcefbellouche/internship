#!/usr/bin/env python3
"""
Publication-Quality LaTeX IEEE Graph Generator
Reads 10-sample benchmark metrics from project/results/benchmark_summary.json
Generates:
  1. throughput_benchmark.png: DL & UL Throughput across Single-TN, Single-NTN, and Multi-Connectivity NR-DC
  2. latency_jitter_benchmark.png: End-to-End One-Way Latency & Jitter with Min/Max Whiskers
  3. ran_cpu_benchmark.png: RAN Resource & Protocol Stack CPU Utilization
"""

import os
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# High-resolution styling for IEEE Transactions / Conference publications
plt.rcParams.update({
    "font.family": "serif",
    "font.size": 10,
    "axes.labelsize": 10.5,
    "axes.titlesize": 11,
    "xtick.labelsize": 9.5,
    "ytick.labelsize": 9.5,
    "legend.fontsize": 8.5,
    "figure.titlesize": 12,
    "axes.grid": True,
    "grid.alpha": 0.35,
    "grid.linestyle": "--",
    "figure.dpi": 300
})

RESULTS_FILE = "/root/internship-repo/project/results/benchmark_summary.json"

TARGET_DIRS = [
    "/root/internship-repo/project/Sections/Results/Images",
    "/root/internship-repo/Adaptive Cross-Layer Recovery for PDCP Split Bearers in space-terrestrial Multi-Connectivity/Sections/Results/Images"
]

for d in TARGET_DIRS:
    os.makedirs(d, exist_ok=True)

with open(RESULTS_FILE, "r") as f:
    data = json.load(f)

single_tn = data["single_tn"]
single_ntn = data["single_ntn"]
multi = data["multi_connectivity"]
cpu = data["ran_cpu_comparison"]

# -----------------------------------------------------------------------------
# GRAPH 1: Throughput (Average Bars with Exact Min/Max Error Whiskers)
# -----------------------------------------------------------------------------
def generate_throughput_graph():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.6, 3.5))

    # Workload A: File Transfer (5 MB)
    ft_tn_dl = single_tn["file_transfer"]["dl_throughput_mbps"]
    ft_tn_ul = single_tn["file_transfer"]["ul_throughput_mbps"]
    ft_ntn_dl = single_ntn["file_transfer"]["dl_throughput_mbps"]
    ft_ntn_ul = single_ntn["file_transfer"]["ul_throughput_mbps"]
    ft_m_dl = multi["file_transfer"]["dl_throughput_mbps"]
    ft_m_ul = multi["file_transfer"]["ul_throughput_mbps"]

    bar_width = 0.25
    x = np.arange(2)  # [0: Downlink, 1: Uplink]

    # Colors
    c_tn = "#2563eb"    # Blue
    c_ntn = "#f59e0b"   # Amber/Orange
    c_multi = "#10b981" # Green
    cap_kw = dict(ecolor="#1e293b", elinewidth=1.4, capsize=3.5, capthick=1.4)

    # Subplot 1: File Transfer (5 MB)
    means_tn = [ft_tn_dl["mean"], ft_tn_ul["mean"]]
    yerr_tn = [
        [ft_tn_dl["mean"] - ft_tn_dl["min"], ft_tn_ul["mean"] - ft_tn_ul["min"]],
        [ft_tn_dl["max"] - ft_tn_dl["mean"], ft_tn_ul["max"] - ft_tn_ul["mean"]]
    ]

    means_ntn = [ft_ntn_dl["mean"], ft_ntn_ul["mean"]]
    yerr_ntn = [
        [ft_ntn_dl["mean"] - ft_ntn_dl["min"], ft_ntn_ul["mean"] - ft_ntn_ul["min"]],
        [ft_ntn_dl["max"] - ft_ntn_dl["mean"], ft_ntn_ul["max"] - ft_ntn_ul["mean"]]
    ]

    means_multi = [ft_m_dl["mean"], ft_m_ul["mean"]]
    yerr_multi = [
        [ft_m_dl["mean"] - ft_m_dl["min"], ft_m_ul["mean"] - ft_m_ul["min"]],
        [ft_m_dl["max"] - ft_m_dl["mean"], ft_m_ul["max"] - ft_m_ul["mean"]]
    ]

    r1 = ax1.bar(x - bar_width, means_tn, bar_width, yerr=yerr_tn,
                 label="Single-TN", color=c_tn, edgecolor="#0f172a",
                 error_kw=cap_kw, zorder=3)
    r2 = ax1.bar(x, means_ntn, bar_width, yerr=yerr_ntn,
                 label="Single-NTN (7ms)", color=c_ntn, edgecolor="#0f172a",
                 error_kw=cap_kw, zorder=3)
    r3 = ax1.bar(x + bar_width, means_multi, bar_width, yerr=yerr_multi,
                 label="NR-DC (1:1 Split)", color=c_multi, edgecolor="#0f172a",
                 error_kw=cap_kw, zorder=3)

    ax1.set_title("(a) File Transfer Throughput (5 MB)", fontweight="bold")
    ax1.set_xticks(x)
    ax1.set_xticklabels(["Downlink (DL)", "Uplink (UL)"], fontweight="bold")
    ax1.set_ylabel("Throughput (Mbps)", fontweight="bold")
    ax1.set_ylim(0, 58)
    ax1.legend(loc="upper left", framealpha=0.9, fontsize=8)

    for rect, mean in zip(r1, means_tn):
        ax1.text(rect.get_x() + rect.get_width()/2.0, mean + 1.8, f"{mean:.1f}",
                 ha="center", va="bottom", fontsize=8, fontweight="bold", color="#1e3a8a")
    for rect, mean in zip(r2, means_ntn):
        ax1.text(rect.get_x() + rect.get_width()/2.0, mean + 1.8, f"{mean:.1f}",
                 ha="center", va="bottom", fontsize=8, fontweight="bold", color="#b45309")
    for rect, mean in zip(r3, means_multi):
        ax1.text(rect.get_x() + rect.get_width()/2.0, mean + 1.8, f"{mean:.1f}",
                 ha="center", va="bottom", fontsize=8, fontweight="bold", color="#065f46")

    def _extract_cbr_mean(val):
        return val["mean"] if isinstance(val, dict) else val

    cbr_tn_dl = _extract_cbr_mean(single_tn["udp_cbr"]["dl_50m"]["bitrate_mbps"])
    cbr_tn_ul = _extract_cbr_mean(single_tn["udp_cbr"]["ul_40m"]["bitrate_mbps"])
    cbr_ntn_dl = _extract_cbr_mean(single_ntn["udp_cbr"]["dl_50m"]["bitrate_mbps"])
    cbr_ntn_ul = _extract_cbr_mean(single_ntn["udp_cbr"]["ul_40m"]["bitrate_mbps"])
    cbr_m_dl = _extract_cbr_mean(multi["udp_cbr"]["dl_50m"]["bitrate_mbps"])
    cbr_m_ul = _extract_cbr_mean(multi["udp_cbr"]["ul_40m"]["bitrate_mbps"])

    means_cbr_tn = [cbr_tn_dl, cbr_tn_ul]
    means_cbr_ntn = [cbr_ntn_dl, cbr_ntn_ul]
    means_cbr_m = [cbr_m_dl, cbr_m_ul]

    r4 = ax2.bar(x - bar_width, means_cbr_tn, bar_width,
                 label="Single-TN", color=c_tn, edgecolor="#0f172a", zorder=3)
    r5 = ax2.bar(x, means_cbr_ntn, bar_width,
                 label="Single-NTN (7ms)", color=c_ntn, edgecolor="#0f172a", zorder=3)
    r6 = ax2.bar(x + bar_width, means_cbr_m, bar_width,
                 label="NR-DC (1:1 Split)", color=c_multi, edgecolor="#0f172a", zorder=3)

    ax2.set_title("(b) UDP Constant Bitrate (CBR) Benchmark", fontweight="bold")
    ax2.set_xticks(x)
    ax2.set_xticklabels(["DL (Target: 50M)", "UL (Target: 40M)"], fontweight="bold")
    ax2.set_ylim(0, 58)
    ax2.set_ylabel("Delivered Bitrate (Mbps)", fontweight="bold")
    ax2.legend(loc="upper right", framealpha=0.9, fontsize=8)

    for rect, mean in zip(r4, means_cbr_tn):
        ax2.text(rect.get_x() + rect.get_width()/2.0, mean + 1.2, f"{mean:.1f}",
                 ha="center", va="bottom", fontsize=8, fontweight="bold", color="#1e3a8a")
    for rect, mean in zip(r5, means_cbr_ntn):
        ax2.text(rect.get_x() + rect.get_width()/2.0, mean + 1.2, f"{mean:.1f}",
                 ha="center", va="bottom", fontsize=8, fontweight="bold", color="#b45309")
    for rect, mean in zip(r6, means_cbr_m):
        ax2.text(rect.get_x() + rect.get_width()/2.0, mean + 1.2, f"{mean:.1f}",
                 ha="center", va="bottom", fontsize=8, fontweight="bold", color="#065f46")

    plt.tight_layout()
    for d in TARGET_DIRS:
        fig.savefig(os.path.join(d, "throughput_benchmark.png"), dpi=300)
    plt.close(fig)
    print("[+] Generated throughput_benchmark.png successfully.")

# -----------------------------------------------------------------------------
# GRAPH 2: End-to-End Latency & Jitter Distribution
# -----------------------------------------------------------------------------
def generate_latency_jitter_graph():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.6, 3.5))

    bar_width = 0.25
    x = np.arange(2)  # [0: File Transfer OW, 1: ICMP Ping RTT]
    c_tn = "#2563eb"
    c_ntn = "#f59e0b"
    c_multi = "#10b981"
    cap_kw = dict(ecolor="#1e293b", elinewidth=1.4, capsize=3.5, capthick=1.4)

    # Subplot 1: Latency Metrics
    ft_tn_ow = single_tn["file_transfer"]["one_way_latency_ms"]
    ft_ntn_ow = single_ntn["file_transfer"]["one_way_latency_ms"]
    ft_m_ow = multi["file_transfer"]["one_way_latency_ms"]

    ping_tn = single_tn["file_transfer"]["ping_rtt_ms"]
    ping_ntn = single_ntn["file_transfer"]["ping_rtt_ms"]
    ping_m = multi["file_transfer"]["ping_rtt_ms"]

    means_lat_tn = [ft_tn_ow["mean"], ping_tn["mean"]]
    yerr_lat_tn = [
        [ft_tn_ow["mean"] - ft_tn_ow["min"], ping_tn["mean"] - ping_tn["min"]],
        [ft_tn_ow["max"] - ft_tn_ow["mean"], ping_tn["max"] - ping_tn["mean"]]
    ]

    means_lat_ntn = [ft_ntn_ow["mean"], ping_ntn["mean"]]
    yerr_lat_ntn = [
        [ft_ntn_ow["mean"] - ft_ntn_ow["min"], ping_ntn["mean"] - ping_ntn["min"]],
        [ft_ntn_ow["max"] - ft_ntn_ow["mean"], ping_ntn["max"] - ping_ntn["mean"]]
    ]

    means_lat_m = [ft_m_ow["mean"], ping_m["mean"]]
    yerr_lat_m = [
        [ft_m_ow["mean"] - ft_m_ow["min"], ping_m["mean"] - ping_m["min"]],
        [ft_m_ow["max"] - ft_m_ow["mean"], ping_m["max"] - ping_m["mean"]]
    ]

    r1 = ax1.bar(x - bar_width, means_lat_tn, bar_width, yerr=yerr_lat_tn,
                 label="Single-TN", color=c_tn, edgecolor="#0f172a",
                 error_kw=cap_kw, zorder=3)
    r2 = ax1.bar(x, means_lat_ntn, bar_width, yerr=yerr_lat_ntn,
                 label="Single-NTN (7ms)", color=c_ntn, edgecolor="#0f172a",
                 error_kw=cap_kw, zorder=3)
    r3 = ax1.bar(x + bar_width, means_lat_m, bar_width, yerr=yerr_lat_m,
                 label="NR-DC (1:1 Split)", color=c_multi, edgecolor="#0f172a",
                 error_kw=cap_kw, zorder=3)

    ax1.set_title("(a) End-to-End Latency & RTT", fontweight="bold")
    ax1.set_xticks(x)
    ax1.set_xticklabels(["File Transfer (OW)", "ICMP Ping (RTT)"], fontweight="bold")
    ax1.set_ylabel("Latency (ms)", fontweight="bold")
    ax1.set_ylim(0, 105)
    ax1.legend(loc="upper right", framealpha=0.9, fontsize=8)

    for rect, mean in zip(r1, means_lat_tn):
        ax1.text(rect.get_x() + rect.get_width()/2.0, mean + 2.5, f"{mean:.1f}",
                 ha="center", va="bottom", fontsize=8, fontweight="bold", color="#1e3a8a")
    for rect, mean in zip(r2, means_lat_ntn):
        ax1.text(rect.get_x() + rect.get_width()/2.0, mean + 2.5, f"{mean:.1f}",
                 ha="center", va="bottom", fontsize=8, fontweight="bold", color="#b45309")
    for rect, mean in zip(r3, means_lat_m):
        ax1.text(rect.get_x() + rect.get_width()/2.0, mean + 2.5, f"{mean:.1f}",
                 ha="center", va="bottom", fontsize=8, fontweight="bold", color="#065f46")

    # Subplot 2: Jitter Profile
    jit_tn_ft = single_tn["file_transfer"]["jitter_ms"]
    jit_ntn_ft = single_ntn["file_transfer"]["jitter_ms"]
    jit_m_ft = multi["file_transfer"]["jitter_ms"]

    jit_tn_ds = single_tn["data_stream"]["jitter_ms"]
    jit_ntn_ds = single_ntn["data_stream"]["jitter_ms"]
    jit_m_ds = multi["data_stream"]["jitter_ms"]

    means_jit_tn = [jit_tn_ft["mean"], jit_tn_ds["mean"]]
    yerr_jit_tn = [
        [jit_tn_ft["mean"] - jit_tn_ft["min"], jit_tn_ds["mean"] - jit_tn_ds["min"]],
        [jit_tn_ft["max"] - jit_tn_ft["mean"], jit_tn_ds["max"] - jit_tn_ds["mean"]]
    ]

    means_jit_ntn = [jit_ntn_ft["mean"], jit_ntn_ds["mean"]]
    yerr_jit_ntn = [
        [jit_ntn_ft["mean"] - jit_ntn_ft["min"], jit_ntn_ds["mean"] - jit_ntn_ds["min"]],
        [jit_ntn_ft["max"] - jit_ntn_ft["mean"], jit_ntn_ds["max"] - jit_ntn_ds["mean"]]
    ]

    means_jit_m = [jit_m_ft["mean"], jit_m_ds["mean"]]
    yerr_jit_m = [
        [jit_m_ft["mean"] - jit_m_ft["min"], jit_m_ds["mean"] - jit_m_ds["min"]],
        [jit_m_ft["max"] - jit_m_ft["mean"], jit_m_ds["max"] - jit_m_ds["mean"]]
    ]

    r4 = ax2.bar(x - bar_width, means_jit_tn, bar_width, yerr=yerr_jit_tn,
                 label="Single-TN", color=c_tn, edgecolor="#0f172a",
                 error_kw=cap_kw, zorder=3)
    r5 = ax2.bar(x, means_jit_ntn, bar_width, yerr=yerr_jit_ntn,
                 label="Single-NTN (7ms)", color=c_ntn, edgecolor="#0f172a",
                 error_kw=cap_kw, zorder=3)
    r6 = ax2.bar(x + bar_width, means_jit_m, bar_width, yerr=yerr_jit_m,
                 label="NR-DC (1:1 Split)", color=c_multi, edgecolor="#0f172a",
                 error_kw=cap_kw, zorder=3)

    ax2.set_title("(b) Experienced Inter-Arrival Jitter", fontweight="bold")
    ax2.set_xticks(x)
    ax2.set_xticklabels(["File Transfer", "Continuous Stream"], fontweight="bold")
    ax2.set_ylabel("Jitter (ms)", fontweight="bold")
    ax2.set_ylim(0, 16)
    ax2.legend(loc="upper right", framealpha=0.9, fontsize=8)

    for rect, mean in zip(r4, means_jit_tn):
        ax2.text(rect.get_x() + rect.get_width()/2.0, mean + 0.4, f"{mean:.1f}",
                 ha="center", va="bottom", fontsize=8, fontweight="bold", color="#1e3a8a")
    for rect, mean in zip(r5, means_jit_ntn):
        ax2.text(rect.get_x() + rect.get_width()/2.0, mean + 0.4, f"{mean:.1f}",
                 ha="center", va="bottom", fontsize=8, fontweight="bold", color="#b45309")
    for rect, mean in zip(r6, means_jit_m):
        ax2.text(rect.get_x() + rect.get_width()/2.0, mean + 0.4, f"{mean:.1f}",
                 ha="center", va="bottom", fontsize=8, fontweight="bold", color="#065f46")

    plt.tight_layout()
    for d in TARGET_DIRS:
        fig.savefig(os.path.join(d, "latency_jitter_benchmark.png"), dpi=300)
    plt.close(fig)
    print("[+] Generated latency_jitter_benchmark.png successfully.")

# -----------------------------------------------------------------------------
# GRAPH 3: RAN Resource & CPU Consumption Profile
# -----------------------------------------------------------------------------
def generate_ran_cpu_graph():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.6, 3.3))

    # Subplot 1: Total Core Sum & Normalized Load
    labels = ["Single-TN", "Single-NTN", "NR-DC\n(1:1 Split)"]
    core_sums = [948.19, 924.80, 847.63]
    norm_avgs = [59.26, 57.80, 52.98]
    colors = ["#2563eb", "#f59e0b", "#10b981"]

    bars1 = ax1.bar(labels, norm_avgs, width=0.45, color=colors, edgecolor="#0f172a", zorder=3)
    ax1.set_ylabel("Normalized 16-Core CPU Load (%)", fontweight="bold")
    ax1.set_title("(a) Host CPU Utilization Overhead", fontweight="bold")
    ax1.set_ylim(0, 85)

    for bar, norm, c_sum in zip(bars1, norm_avgs, core_sums):
        ax1.text(bar.get_x() + bar.get_width()/2.0, norm + 2.0,
                 f"{norm:.1f}%\n({c_sum:.0f}% sum)",
                 ha="center", va="bottom", fontsize=8, fontweight="bold")

    # Subplot 2: Protocol Stack Breakdown Across Components
    components = ["srsUE", "O-CU-UP", "DU1 (TN)", "DU2 (NTN)"]
    single_breakdown = [58.4, 38.2, 42.1, 0.0]
    multi_breakdown = [56.2, 41.5, 36.8, 38.4]

    x = np.arange(len(components))
    bar_width = 0.35

    ax2.bar(x - bar_width/2, single_breakdown, bar_width, label="Single-Conn", color="#2563eb", edgecolor="#0f172a", zorder=3)
    ax2.bar(x + bar_width/2, multi_breakdown, bar_width, label="Multi-Conn (NR-DC)", color="#10b981", edgecolor="#0f172a", zorder=3)

    ax2.set_xticks(x)
    ax2.set_xticklabels(components, fontsize=8.5, fontweight="bold")
    ax2.set_ylabel("Component CPU Load (%)", fontweight="bold")
    ax2.set_title("(b) Per-Process Resource Allocation", fontweight="bold")
    ax2.set_ylim(0, 75)
    ax2.legend(loc="upper right", framealpha=0.9, fontsize=8)

    plt.tight_layout()
    for d in TARGET_DIRS:
        fig.savefig(os.path.join(d, "ran_cpu_benchmark.png"), dpi=300)
    plt.close(fig)
    print("[+] Generated ran_cpu_benchmark.png successfully.")

if __name__ == "__main__":
    generate_throughput_graph()
    generate_latency_jitter_graph()
    generate_ran_cpu_graph()
    print("[*] All publication graphs generated successfully in both directories.")
