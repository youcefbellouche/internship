#!/usr/bin/env python3
"""
RAN Resource Monitor & Profiler
Samples CPU utilization and memory RSS of all 5G RAN processes:
  - srsue (User Equipment)
  - ocucp (O-RAN CU Control Plane)
  - ocuup (O-RAN CU User Plane)
  - odu   (O-RAN Distributed Units DU1 and DU2)
Uses pure Linux /proc filesystem parsing (zero external dependencies).
"""

import os
import sys
import time
import json
import glob
import threading
import urllib.request

RAN_PROCESS_PATTERNS = ["srsue", "ocucp", "ocuup", "odu"]


def get_process_pids(pattern):
    """Finds all PIDs whose comm or cmdline matches pattern."""
    pids = []
    for pid_dir in glob.glob("/proc/[0-9]*"):
        pid = os.path.basename(pid_dir)
        try:
            with open(f"/proc/{pid}/comm", "r") as f:
                comm = f.read().strip()
                if pattern in comm:
                    pids.append(int(pid))
                    continue
            with open(f"/proc/{pid}/cmdline", "r") as f:
                cmdline = f.read().replace("\x00", " ")
                if pattern in cmdline:
                    pids.append(int(pid))
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
    return pids


def read_proc_stat(pid):
    """Reads utime and stime from /proc/<pid>/stat in clock ticks."""
    try:
        with open(f"/proc/{pid}/stat", "r") as f:
            fields = f.read().split()
            # utime is 14th field (index 13), stime is 15th field (index 14)
            utime = int(fields[13])
            stime = int(fields[14])
            return utime + stime
    except Exception:
        return None


def read_proc_rss_mb(pid):
    """Reads Resident Set Size in MB from /proc/<pid>/statm."""
    try:
        with open(f"/proc/{pid}/statm", "r") as f:
            # 2nd field is resident set size in pages
            pages = int(f.read().split()[1])
            page_size_kb = os.sysconf("SC_PAGE_SIZE") / 1024.0
            return (pages * page_size_kb) / 1024.0
    except Exception:
        return 0.0


class RANResourceMonitor:
    def __init__(self, sample_interval=0.2, server_url="http://127.0.0.1:8080"):
        self.sample_interval = sample_interval
        self.server_url = server_url
        self.running = False
        self.clk_tck = os.sysconf("SC_CLK_TCK")
        self.num_cpus = os.cpu_count() or 1
        self.metrics_history = []

    def start_monitoring(self, duration_sec=None):
        self.running = True
        prev_ticks = {}
        prev_time = time.time()
        start_time = time.time()

        print(f"[*] Starting RAN Resource Monitor (sampling every {int(self.sample_interval*1000)}ms)...")

        try:
            while self.running:
                time.sleep(self.sample_interval)
                curr_time = time.time()
                dt = curr_time - prev_time
                if dt <= 0:
                    continue

                snapshot = {"timestamp": curr_time, "processes": {}, "total_ran_cpu": 0.0}

                for proc_name in RAN_PROCESS_PATTERNS:
                    pids = get_process_pids(proc_name)
                    proc_cpu = 0.0
                    proc_rss = 0.0

                    for pid in pids:
                        ticks = read_proc_stat(pid)
                        rss = read_proc_rss_mb(pid)
                        proc_rss += rss

                        if ticks is not None:
                            if pid in prev_ticks:
                                delta_ticks = ticks - prev_ticks[pid]
                                # CPU % normalized across single core
                                cpu_pct = (delta_ticks / (self.clk_tck * dt)) * 100.0
                                proc_cpu += cpu_pct
                            prev_ticks[pid] = ticks

                    snapshot["processes"][proc_name] = {
                        "cpu_pct": round(proc_cpu, 2),
                        "rss_mb": round(proc_rss, 1),
                        "instances": len(pids)
                    }
                    snapshot["total_ran_cpu"] += proc_cpu

                snapshot["total_ran_cpu"] = round(snapshot["total_ran_cpu"], 2)
                self.metrics_history.append(snapshot)
                prev_time = curr_time

                # Send live update to web server
                self.send_live_update(snapshot)

                if duration_sec and (curr_time - start_time) >= duration_sec:
                    break

        except KeyboardInterrupt:
            pass

        self.running = False
        return self.compute_summary()

    def send_live_update(self, snapshot):
        try:
            procs = snapshot["processes"]
            payload = {
                "ran_cpu": {
                    "ue": procs.get("srsue", {}).get("cpu_pct", 0.0),
                    "cuup": procs.get("ocuup", {}).get("cpu_pct", 0.0),
                    "cucp": procs.get("ocucp", {}).get("cpu_pct", 0.0),
                    "du1": procs.get("odu", {}).get("cpu_pct", 0.0) / 2.0,  # approximate per-DU
                    "du2": procs.get("odu", {}).get("cpu_pct", 0.0) / 2.0,
                    "total": snapshot["total_ran_cpu"]
                }
            }
            req = urllib.request.Request(
                f"{self.server_url}/api/record_result",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            urllib.request.urlopen(req, timeout=1)
        except Exception:
            pass

    def compute_summary(self):
        if not self.metrics_history:
            return {}

        summary = {"processes": {}}
        totals = [s["total_ran_cpu"] for s in self.metrics_history]
        summary["total_ran_cpu_avg"] = round(sum(totals) / len(totals), 2)
        summary["total_ran_cpu_peak"] = round(max(totals) if totals else 0.0, 2)

        for proc_name in RAN_PROCESS_PATTERNS:
            cpus = [s["processes"].get(proc_name, {}).get("cpu_pct", 0.0) for s in self.metrics_history]
            summary["processes"][proc_name] = {
                "avg_cpu_pct": round(sum(cpus) / len(cpus), 2) if cpus else 0.0,
                "peak_cpu_pct": round(max(cpus) if cpus else 0.0, 2)
            }

        return summary


def main():
    duration = int(sys.argv[1]) if len(sys.argv) > 1 else None
    monitor = RANResourceMonitor()
    summary = monitor.start_monitoring(duration_sec=duration)
    print("\n=== RAN Resource Utilization Summary ===")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
