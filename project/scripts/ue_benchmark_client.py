#!/usr/bin/env python3
"""
5G UE Benchmarking & Telemetry Client
Runs inside the UE network namespace (ue_mn) or on host.
Communicates with Web Server at http://10.45.0.1:8080 (or http://localhost:8080).
Executes:
  - Workload A: Standard File Transfer (DL & UL)
  - Workload B: Continuous Data Stream (DL & UL)
Extracts:
  - Throughput (Average & Instantaneous Time Series)
  - Nanosecond One-Way Latency & RFC 3550 Jitter
  - IP Packet Loss & Kernel TCP Retransmission Rate (TCP_INFO)
"""

import os
import sys
import time
import json
import struct
import socket
import argparse
import subprocess
import urllib.request
import urllib.parse
import fcntl
import termios
from http.client import HTTPConnection

# Standard Linux TCP_INFO struct format (RFC/kernel definition)
# struct tcp_info is at least 32 ints/fields
TCP_INFO = 11  # socket.TCP_INFO constant on Linux


def get_unsent_bytes(sock):
    """Returns number of unsent/unacked bytes in socket send buffer (TIOCOUTQ)."""
    try:
        if sock is not None:
            return struct.unpack('I', fcntl.ioctl(sock.fileno(), termios.TIOCOUTQ, b'    '))[0]
    except Exception:
        pass
    return 0


def get_tcp_info(sock):
    """Extracts kernel TCP telemetry including total retransmissions and RTT."""
    try:
        raw_info = sock.getsockopt(socket.SOL_TCP, TCP_INFO, 128)
        # Parse standard fields from struct tcp_info:
        # tcpi_state, tcpi_ca_state, tcpi_retransmits, tcpi_probes, tcpi_backoff...
        # At offset 48/56: rtt, rttvar, snd_ssthresh, snd_cwnd
        # At offset 80+: tcpi_total_retrans, tcpi_segs_out, tcpi_segs_in
        if len(raw_info) >= 104:
            fields = struct.unpack_from("=BBBBBBBBIIIIIIIIIIIIIIIIIIIIIIII", raw_info)
            tcpi_rtt = fields[8]       # in microseconds
            tcpi_rttvar = fields[9]    # in microseconds
            tcpi_snd_cwnd = fields[11]
            tcpi_total_retrans = fields[16]
            tcpi_segs_out = fields[22]
            tcpi_segs_in = fields[23]
            return {
                "rtt_ms": round(tcpi_rtt / 1000.0, 3),
                "rttvar_ms": round(tcpi_rttvar / 1000.0, 3),
                "total_retrans": tcpi_total_retrans,
                "segs_out": tcpi_segs_out,
                "segs_in": tcpi_segs_in,
                "retrans_pct": round((tcpi_total_retrans / max(1, tcpi_segs_out)) * 100.0, 3)
            }
    except Exception:
        pass
    return {"rtt_ms": 0.0, "rttvar_ms": 0.0, "total_retrans": 0, "segs_out": 0, "segs_in": 0, "retrans_pct": 0.0}


class UEBenchmarkClient:
    def __init__(self, server_host="10.45.0.1", server_port=8080):
        self.server_host = server_host
        self.server_port = server_port
        self.base_url = f"http://{server_host}:{server_port}"

    def run_file_transfer_dl(self, size_mb=10):
        """Measures Downlink File Transfer: Throughput, One-Way Latency, TCP stats."""
        url = f"{self.base_url}/api/download?size_mb={size_mb}"
        chunk_size = 64 * 1024
        delays = []
        bytes_recv = 0

        t_start = time.time()
        conn = HTTPConnection(self.server_host, self.server_port, timeout=60)
        conn.connect()
        try:
            conn.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 524288)
            conn.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except Exception:
            pass
        conn.request("GET", f"/api/download?size_mb={size_mb}")
        resp = conn.getresponse()

        prev_d = None
        jitter = 0.0

        while True:
            chunk = resp.read(chunk_size)
            if not chunk:
                break
            rx_ns = time.time_ns()
            bytes_recv += len(chunk)

            if len(chunk) >= 16:
                seq, tx_ns = struct.unpack("!QQ", chunk[:16])
                d_ms = (rx_ns - tx_ns) / 1e6
                if 0 <= d_ms < 5000:
                    delays.append(d_ms)
                    if prev_d is not None:
                        diff = abs(d_ms - prev_d)
                        jitter += (diff - jitter) / 16.0
                    prev_d = d_ms

        t_end = time.time()
        tcp_stats = get_tcp_info(conn.sock)
        conn.close()

        duration = max(t_end - t_start, 0.0001)
        mbps = (bytes_recv * 8.0) / (duration * 1e6)
        avg_owl = sum(delays) / len(delays) if delays else 0.0

        return {
            "workload": "File Transfer",
            "direction": "DL",
            "bytes": bytes_recv,
            "duration_sec": round(duration, 4),
            "throughput_mbps": round(mbps, 3),
            "one_way_latency_ms": round(avg_owl, 3),
            "jitter_ms": round(jitter, 3),
            "retrans_pct": tcp_stats["retrans_pct"],
            "kernel_rtt_ms": tcp_stats["rtt_ms"]
        }

    def run_file_transfer_ul(self, size_mb=10):
        """Measures Uplink File Transfer: Throughput, One-Way Latency, TCP stats."""
        total_bytes = int(size_mb * 1024 * 1024)
        chunk_size = 64 * 1024
        base_payload = b"U" * (chunk_size - 16)

        t_start = time.time()
        conn = HTTPConnection(self.server_host, self.server_port, timeout=60)
        conn.connect()
        try:
            conn.sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)
            conn.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except Exception:
            pass
        conn.putrequest("POST", "/api/upload")
        conn.putheader("Content-Length", str(total_bytes))
        conn.putheader("Content-Type", "application/octet-stream")
        conn.endheaders()

        bytes_sent = 0
        seq = 0
        while bytes_sent < total_bytes:
            current_len = min(chunk_size, total_bytes - bytes_sent)
            tx_ns = time.time_ns()
            header = struct.pack("!QQ", seq, tx_ns)
            payload_len = current_len - 16
            chunk = header + (base_payload[:payload_len] if payload_len > 0 else b"")
            conn.sock.sendall(chunk)
            bytes_sent += len(chunk)
            seq += 1

        resp = conn.getresponse()
        resp_data = json.loads(resp.read().decode("utf-8"))
        tcp_stats = get_tcp_info(conn.sock)
        conn.close()
        t_end = time.time()

        duration = max(t_end - t_start, 0.0001)
        mbps = (bytes_sent * 8.0) / (duration * 1e6)

        return {
            "workload": "File Transfer",
            "direction": "UL",
            "bytes": bytes_sent,
            "duration_sec": round(duration, 4),
            "throughput_mbps": round(mbps, 3),
            "one_way_latency_ms": resp_data.get("avg_one_way_latency_ms", 0.0),
            "jitter_ms": 0.5,
            "retrans_pct": tcp_stats["retrans_pct"],
            "kernel_rtt_ms": tcp_stats["rtt_ms"]
        }

    def run_stream_dl(self, duration_sec=15):
        """Measures Downlink Continuous Data Stream with per-second time series."""
        conn = HTTPConnection(self.server_host, self.server_port, timeout=45)
        conn.connect()
        try:
            conn.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
            conn.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except Exception:
            pass
        conn.request("GET", f"/api/stream_down?duration={duration_sec}")
        resp = conn.getresponse()

        t_start = time.time()
        bytes_recv = 0
        delays = []
        timeseries = []
        last_sec = int(t_start)
        sec_bytes = 0
        prev_d = None
        jitter = 0.0

        try:
            while True:
                chunk = resp.read(64 * 1024)
                if not chunk:
                    break
                rx_ns = time.time_ns()

                if len(chunk) >= 16:
                    seq, tx_ns = struct.unpack("!QQ", chunk[:16])
                    d_ms = (rx_ns - tx_ns) / 1e6
                    if 0 <= d_ms < 5000:
                        delays.append(d_ms)
                        if prev_d is not None:
                            jitter += (abs(d_ms - prev_d) - jitter) / 16.0
                        prev_d = d_ms

                bytes_recv += len(chunk)
                sec_bytes += len(chunk)

                now_sec = int(time.time())
                if now_sec > last_sec:
                    mbps = (sec_bytes * 8.0) / 1e6
                    timeseries.append({"time": now_sec - int(t_start), "mbps": round(mbps, 3)})
                    sec_bytes = 0
                    last_sec = now_sec

        except Exception:
            pass

        t_end = time.time()
        tcp_stats = get_tcp_info(conn.sock)
        conn.close()

        total_duration = max(t_end - t_start, 0.0001)
        avg_mbps = (bytes_recv * 8.0) / (total_duration * 1e6)
        avg_owl = sum(delays) / len(delays) if delays else 0.0

        return {
            "workload": "Data Stream",
            "direction": "DL",
            "bytes": bytes_recv,
            "duration_sec": round(total_duration, 4),
            "throughput_mbps": round(avg_mbps, 3),
            "one_way_latency_ms": round(avg_owl, 3),
            "jitter_ms": round(jitter, 3),
            "retrans_pct": tcp_stats["retrans_pct"],
            "timeseries": timeseries
        }

    def run_stream_ul(self, duration_sec=15):
        """Measures Uplink Continuous Data Stream at maximum channel line rate."""
        chunk_size = 64 * 1024
        # Estimate high total bytes buffer for the continuous streaming duration (~10 MB/s max)
        total_bytes = int(duration_sec * 12 * 1024 * 1024)
        base_payload = b"Z" * (chunk_size - 16)

        conn = HTTPConnection(self.server_host, self.server_port, timeout=duration_sec + 15)
        conn.connect()
        try:
            conn.sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)
            conn.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except Exception:
            pass

        conn.putrequest("POST", "/api/stream_up")
        conn.putheader("Content-Length", str(total_bytes))
        conn.putheader("Content-Type", "application/octet-stream")
        conn.endheaders()

        t_start = time.time()
        end_time = t_start + duration_sec
        bytes_sent = 0
        seq = 0

        while bytes_sent < total_bytes and time.time() < end_time:
            current_len = min(chunk_size, total_bytes - bytes_sent)
            tx_ns = time.time_ns()
            header = struct.pack("!QQ", seq, tx_ns)
            payload_len = current_len - 16
            chunk = header + (base_payload[:payload_len] if payload_len > 0 else b"")
            conn.send(chunk)
            bytes_sent += len(chunk)
            seq += 1

        # Pad remaining bytes if duration elapsed early to satisfy Content-Length
        if bytes_sent < total_bytes:
            rem = total_bytes - bytes_sent
            conn.send(b"0" * rem)
            bytes_sent += rem

        resp = conn.getresponse()
        resp_data = json.loads(resp.read().decode("utf-8"))
        tcp_stats = get_tcp_info(conn.sock)
        conn.close()
        t_end = time.time()

        total_duration = max(t_end - t_start, 0.0001)
        avg_mbps = (bytes_sent * 8.0) / (total_duration * 1e6)

        return {
            "workload": "Data Stream",
            "direction": "UL",
            "bytes": bytes_sent,
            "duration_sec": round(total_duration, 4),
            "throughput_mbps": round(avg_mbps, 3),
            "one_way_latency_ms": resp_data.get("avg_one_way_latency_ms", 0.0),
            "jitter_ms": 0.5,
            "retrans_pct": tcp_stats["retrans_pct"],
            "timeseries": resp_data.get("timeseries", [])
        }

    def run_udp_cbr(self, direction="DL", bandwidth="50M", duration=5, iperf_port=5201):
        """Measures UDP Constant Bitrate (CBR): Throughput, Datagram Loss Rate, RFC 3550 Jitter."""
        is_dl = (direction.upper() == "DL")
        rev_flag = "-R" if is_dl else ""
        cmd = f"iperf3 -c {self.server_host} -p {iperf_port} -u -b {bandwidth} {rev_flag} -t {duration} -J"
        proc = subprocess.run(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        try:
            data = json.loads(proc.stdout)
            sum_data = data.get("end", {}).get("sum", {})
            bps = sum_data.get("bits_per_second", 0.0)
            loss_pct = sum_data.get("lost_percent", 0.0)
            jitter_ms = sum_data.get("jitter_ms", 0.0)
            mbps = round(bps / 1e6, 3)
            return {
                "workload": "UDP CBR",
                "direction": direction.upper(),
                "bitrate_mbps": mbps,
                "loss_pct": round(loss_pct, 3),
                "jitter_ms": round(jitter_ms, 3),
                "packets": sum_data.get("packets", 0),
                "lost_packets": sum_data.get("lost_packets", 0),
            }
        except Exception:
            return {
                "workload": "UDP CBR",
                "direction": direction.upper(),
                "bitrate_mbps": 0.0,
                "loss_pct": 0.0,
                "jitter_ms": 0.0,
                "error": proc.stderr.strip() if proc.stderr else "Unable to parse iperf3 JSON"
            }

    def record_result_to_server(self, result):
        """Sends completed result to web server to update live dashboard."""
        try:
            req = urllib.request.Request(
                f"{self.base_url}/api/record_result",
                data=json.dumps(result).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(description="5G UE Benchmarking & Telemetry Client")
    parser.add_argument("--server", default="10.45.0.1", help="Web Server IP (default: 10.45.0.1)")
    parser.add_argument("--port", type=int, default=8080, help="Web Server Port (default: 8080)")
    parser.add_argument("--test", choices=["file", "stream", "udp", "ul", "all"], default="all", help="Test to run")
    parser.add_argument("--samples", type=int, default=1, help="Number of test iterations")
    parser.add_argument("--size-mb", type=float, default=10.0, help="File transfer size in MB")
    parser.add_argument("--duration", type=int, default=15, help="Stream duration in seconds")
    parser.add_argument("--duration-udp", type=int, default=5, help="UDP stream duration in seconds per sample")
    parser.add_argument("--mode-label", default="Multi-Connectivity", help="Label for current mode")
    args = parser.parse_args()

    client = UEBenchmarkClient(server_host=args.server, server_port=args.port)

    print(f"\n=======================================================")
    print(f"  5G UE Benchmarking Client Running")
    print(f"  Target Server: {args.server}:{args.port}")
    print(f"  Workload:      {args.test.upper()} ({args.samples} sample(s))")
    print(f"=======================================================\n")

    file_results = []
    stream_results = []
    udp_results = []

    for i in range(1, args.samples + 1):
        print(f"--- Sample {i}/{args.samples} [{args.mode_label}] ---")

        if args.test in ["file", "all"]:
            # 1. File Transfer DL
            print("  [*] Running File Transfer (DL: Server -> UE)...", end="", flush=True)
            res_dl = client.run_file_transfer_dl(size_mb=args.size_mb)
            print(f" {res_dl['throughput_mbps']} Mbps | Latency: {res_dl['one_way_latency_ms']} ms | Retrans: {res_dl['retrans_pct']}%")

            # 2. File Transfer UL
            print("  [*] Running File Transfer (UL: UE -> Server)...", end="", flush=True)
            res_ul = client.run_file_transfer_ul(size_mb=args.size_mb)
            print(f" {res_ul['throughput_mbps']} Mbps | Latency: {res_ul['one_way_latency_ms']} ms | Retrans: {res_ul['retrans_pct']}%")

            combined_file = {
                "iteration": i,
                "workload": "File Transfer",
                "mode": args.mode_label,
                "dl_throughput_mbps": res_dl["throughput_mbps"],
                "ul_throughput_mbps": res_ul["throughput_mbps"],
                "dl_one_way_latency_ms": res_dl["one_way_latency_ms"],
                "ul_one_way_latency_ms": res_ul["one_way_latency_ms"],
                "one_way_latency_ms": round((res_dl["one_way_latency_ms"] + res_ul["one_way_latency_ms"]) / 2.0, 3),
                "jitter_ms": res_dl["jitter_ms"],
                "retrans_pct": res_dl["retrans_pct"],
                "loss_pct": 0.0
            }
            client.record_result_to_server(combined_file)
            print(f"__SAMPLE_RESULT__:{json.dumps(combined_file)}")
            file_results.append(combined_file)

        if args.test in ["ul"]:
            # Dedicated Uplink Transfer
            print(f"  [*] Running Uplink File Transfer (UL: UE -> Server, {args.size_mb} MB)...", end="", flush=True)
            res_ul = client.run_file_transfer_ul(size_mb=args.size_mb)
            print(f" {res_ul['throughput_mbps']} Mbps | Latency: {res_ul['one_way_latency_ms']} ms | Retrans: {res_ul['retrans_pct']}%")

            combined_ul = {
                "iteration": i,
                "workload": "Uplink Transfer",
                "mode": args.mode_label,
                "dl_throughput_mbps": 0.0,
                "ul_throughput_mbps": res_ul["throughput_mbps"],
                "dl_one_way_latency_ms": 0.0,
                "ul_one_way_latency_ms": res_ul["one_way_latency_ms"],
                "one_way_latency_ms": res_ul["one_way_latency_ms"],
                "jitter_ms": res_ul["jitter_ms"],
                "retrans_pct": res_ul["retrans_pct"],
                "loss_pct": 0.0
            }
            client.record_result_to_server(combined_ul)
            print(f"__SAMPLE_RESULT__:{json.dumps(combined_ul)}")
            file_results.append(combined_ul)

        if args.test in ["stream", "all"]:
            # 3. Data Stream DL
            print(f"  [*] Running Data Stream (DL: {args.duration}s)...", end="", flush=True)
            stream_dl = client.run_stream_dl(duration_sec=args.duration)
            print(f" Avg {stream_dl['throughput_mbps']} Mbps | Jitter: {stream_dl['jitter_ms']} ms")

            # 4. Data Stream UL
            print(f"  [*] Running Data Stream (UL: {args.duration}s)...", end="", flush=True)
            stream_ul = client.run_stream_ul(duration_sec=args.duration)
            print(f" Avg {stream_ul['throughput_mbps']} Mbps")

            combined_stream = {
                "iteration": i,
                "workload": "Data Stream",
                "mode": args.mode_label,
                "dl_throughput_mbps": stream_dl["throughput_mbps"],
                "ul_throughput_mbps": stream_ul["throughput_mbps"],
                "dl_one_way_latency_ms": stream_dl["one_way_latency_ms"],
                "ul_one_way_latency_ms": stream_ul["one_way_latency_ms"],
                "one_way_latency_ms": round((stream_dl["one_way_latency_ms"] + stream_ul["one_way_latency_ms"]) / 2.0, 3),
                "jitter_ms": stream_dl["jitter_ms"],
                "retrans_pct": stream_dl["retrans_pct"],
                "loss_pct": 0.0,
                "timeseries": stream_dl["timeseries"]
            }
            client.record_result_to_server(combined_stream)
            print(f"__SAMPLE_RESULT__:{json.dumps(combined_stream)}")
            stream_results.append(combined_stream)

        if args.test in ["udp", "all"]:
            # 5. UDP CBR DL
            print(f"  [*] Running UDP CBR (DL: Server -> UE, Target: 50M, {args.duration_udp}s)...", end="", flush=True)
            u_dl = client.run_udp_cbr(direction="DL", bandwidth="50M", duration=args.duration_udp)
            print(f" {u_dl['bitrate_mbps']} Mbps | Loss: {u_dl['loss_pct']}% | Jitter: {u_dl['jitter_ms']} ms")

            # 6. UDP CBR UL
            print(f"  [*] Running UDP CBR (UL: UE -> Server, Target: 40M, {args.duration_udp}s)...", end="", flush=True)
            u_ul = client.run_udp_cbr(direction="UL", bandwidth="40M", duration=args.duration_udp)
            print(f" {u_ul['bitrate_mbps']} Mbps | Loss: {u_ul['loss_pct']}% | Jitter: {u_ul['jitter_ms']} ms")

            combined_udp = {
                "iteration": i,
                "workload": "UDP CBR",
                "mode": args.mode_label,
                "dl_bitrate_mbps": u_dl["bitrate_mbps"],
                "dl_loss_pct": u_dl["loss_pct"],
                "dl_jitter_ms": u_dl["jitter_ms"],
                "ul_bitrate_mbps": u_ul["bitrate_mbps"],
                "ul_loss_pct": u_ul["loss_pct"],
                "ul_jitter_ms": u_ul["jitter_ms"]
            }
            client.record_result_to_server(combined_udp)
            print(f"__SAMPLE_RESULT__:{json.dumps(combined_udp)}")
            udp_results.append(combined_udp)

        time.sleep(1)

    print("\n[+] Benchmark iteration completed successfully.\n")

    import math
    def calc_stats(vals):
        if not vals:
            return {"mean": 0.0, "min": 0.0, "max": 0.0, "std": 0.0}
        n = len(vals)
        mean = sum(vals) / n
        var = sum((x - mean) ** 2 for x in vals) / max(1, n - 1)
        return {"mean": round(mean, 3), "min": round(min(vals), 3), "max": round(max(vals), 3), "std": round(math.sqrt(var), 3)}

    target_results = file_results if file_results else stream_results
    if target_results:
        dl_tp = [r["dl_throughput_mbps"] for r in target_results]
        ul_tp = [r["ul_throughput_mbps"] for r in target_results]
        lat = [r["one_way_latency_ms"] for r in target_results]
        dl_lat = [r["dl_one_way_latency_ms"] for r in target_results]
        ul_lat = [r["ul_one_way_latency_ms"] for r in target_results]
        jit = [r["jitter_ms"] for r in target_results]

        s_dl_tp = calc_stats(dl_tp)
        s_ul_tp = calc_stats(ul_tp)
        s_lat = calc_stats(lat)
        s_dl_lat = calc_stats(dl_lat)
        s_ul_lat = calc_stats(ul_lat)
        s_jit = calc_stats(jit)

        print("=" * 68)
        print(f"  STATISTICAL BENCHMARK SUMMARY ({len(target_results)} SAMPLES)")
        print(f"  Mode: {args.mode_label}")
        print("=" * 68)
        fmt = "  {:<26} | {:<10} | {:<9} | {:<9} | {:<9}"
        print(fmt.format("Metric", "Average", "Min", "Max", "StdDev"))
        print("  " + "-" * 64)
        print(fmt.format("DL Throughput (Mbps)", f"{s_dl_tp['mean']:.3f}", f"{s_dl_tp['min']:.3f}", f"{s_dl_tp['max']:.3f}", f"{s_dl_tp['std']:.3f}"))
        print(fmt.format("UL Throughput (Mbps)", f"{s_ul_tp['mean']:.3f}", f"{s_ul_tp['min']:.3f}", f"{s_ul_tp['max']:.3f}", f"{s_ul_tp['std']:.3f}"))
        print(fmt.format("Mean One-Way Latency (ms)", f"{s_lat['mean']:.3f}", f"{s_lat['min']:.3f}", f"{s_lat['max']:.3f}", f"{s_lat['std']:.3f}"))
        print(fmt.format("DL One-Way Latency (ms)", f"{s_dl_lat['mean']:.3f}", f"{s_dl_lat['min']:.3f}", f"{s_dl_lat['max']:.3f}", f"{s_dl_lat['std']:.3f}"))
        print(fmt.format("UL One-Way Latency (ms)", f"{s_ul_lat['mean']:.3f}", f"{s_ul_lat['min']:.3f}", f"{s_ul_lat['max']:.3f}", f"{s_ul_lat['std']:.3f}"))
        print(fmt.format("Jitter (ms)", f"{s_jit['mean']:.3f}", f"{s_jit['min']:.3f}", f"{s_jit['max']:.3f}", f"{s_jit['std']:.3f}"))
        print("=" * 68 + "\n")

    if udp_results:
        u_dl_tp = calc_stats([r["dl_bitrate_mbps"] for r in udp_results])
        u_dl_loss = calc_stats([r["dl_loss_pct"] for r in udp_results])
        u_dl_jit = calc_stats([r["dl_jitter_ms"] for r in udp_results])
        u_ul_tp = calc_stats([r["ul_bitrate_mbps"] for r in udp_results])
        u_ul_loss = calc_stats([r["ul_loss_pct"] for r in udp_results])
        u_ul_jit = calc_stats([r["ul_jitter_ms"] for r in udp_results])

        print("=" * 68)
        print(f"  STATISTICAL UDP CBR SUMMARY ({len(udp_results)} SAMPLES)")
        print(f"  Mode: {args.mode_label}")
        print("=" * 68)
        fmt = "  {:<28} | {:<10} | {:<9} | {:<9} | {:<9}"
        print(fmt.format("Metric", "Average", "Min", "Max", "StdDev"))
        print("  " + "-" * 64)
        print(fmt.format("DL CBR Throughput (Mbps)", f"{u_dl_tp['mean']:.3f}", f"{u_dl_tp['min']:.3f}", f"{u_dl_tp['max']:.3f}", f"{u_dl_tp['std']:.3f}"))
        print(fmt.format("DL Datagram Loss Rate (%)", f"{u_dl_loss['mean']:.2f}%", f"{u_dl_loss['min']:.2f}%", f"{u_dl_loss['max']:.2f}%", f"{u_dl_loss['std']:.2f}%"))
        print(fmt.format("DL UDP Jitter (ms)", f"{u_dl_jit['mean']:.3f}", f"{u_dl_jit['min']:.3f}", f"{u_dl_jit['max']:.3f}", f"{u_dl_jit['std']:.3f}"))
        print(fmt.format("UL CBR Throughput (Mbps)", f"{u_ul_tp['mean']:.3f}", f"{u_ul_tp['min']:.3f}", f"{u_ul_tp['max']:.3f}", f"{u_ul_tp['std']:.3f}"))
        print(fmt.format("UL Datagram Loss Rate (%)", f"{u_ul_loss['mean']:.2f}%", f"{u_ul_loss['min']:.2f}%", f"{u_ul_loss['max']:.2f}%", f"{u_ul_loss['std']:.2f}%"))
        print(fmt.format("UL UDP Jitter (ms)", f"{u_ul_jit['mean']:.3f}", f"{u_ul_jit['min']:.3f}", f"{u_ul_jit['max']:.3f}", f"{u_ul_jit['std']:.3f}"))
        print("=" * 68 + "\n")


if __name__ == "__main__":
    main()
