#!/usr/bin/env python3
"""
Dual-Accessible 5G MR-DC Web Server & Benchmarking Controller
Listens on 0.0.0.0:8080.
Accessible by host browser (http://localhost:8080) and 5G UE (http://10.45.0.1:8080).
Supports:
  - Static Web UI (Dashboard with real-time charts and controls)
  - High-performance File Transfer endpoints (DL & UL)
  - Sustained continuous chunked streaming endpoints (DL & UL)
  - Live metrics telemetry, one-way latency tracking, and TCP stats
"""

import os
import sys
import time
import json
import struct
import socket
import threading
import fcntl
import termios
from urllib.parse import urlparse, parse_qs
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler


def get_unsent_bytes(sock):
    """Returns number of unsent/unacked bytes in socket send buffer (TIOCOUTQ)."""
    try:
        if sock is not None:
            return struct.unpack('I', fcntl.ioctl(sock.fileno(), termios.TIOCOUTQ, b'    '))[0]
    except Exception:
        pass
    return 0


# Global in-memory metrics storage
METRICS_LOCK = threading.Lock()
ACTIVE_BENCHMARK = {
    "status": "idle",
    "mode": "1:1 (Multi-Connectivity)",
    "current_test": "",
    "iteration": 0,
    "total_iterations": 10,
    "last_result": None,
    "ran_cpu": {
        "ue": 0.0,
        "cuup": 0.0,
        "cucp": 0.0,
        "du1": 0.0,
        "du2": 0.0,
        "total": 0.0
    },
    "history": [],
    "timeseries": []
}

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


def get_current_pdcp_ratio():
    ratio_file = "/tmp/pdcp_split_ratio"
    if os.path.exists(ratio_file):
        try:
            with open(ratio_file, "r") as f:
                content = f.read().strip()
                if content:
                    return content
        except Exception:
            pass
    return os.getenv("PDCP_SPLIT_RATIO", "1:1")


def set_pdcp_ratio(ratio_str):
    try:
        with open("/tmp/pdcp_split_ratio", "w") as f:
            f.write(ratio_str + "\n")
        return True
    except Exception as e:
        print(f"[Error] Failed to set PDCP ratio: {e}")
        return False


class BenchmarkHTTPRequestHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def log_message(self, format, *args):
        # Suppress spammy per-chunk request logs for cleaner console output
        if args and isinstance(args[0], str):
            if "/api/download" in args[0] or "/api/stream" in args[0] or "/static" in args[0]:
                return
        super().log_message(format, *args)

    def send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Timestamp, X-Payload-Size")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_cors_headers()
        self.end_headers()

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        # 1. API: System Status & Configuration
        if path == "/api/status":
            self.handle_api_status()
            return

        # 2. API: Download File Transfer (DL)
        if path == "/api/download":
            self.handle_api_download(query)
            return

        # 3. API: Downlink Continuous Data Stream (DL)
        if path == "/api/stream_down":
            self.handle_api_stream_down(query)
            return

        # 4. API: Metrics Telemetry Query
        if path == "/api/metrics":
            self.handle_api_metrics()
            return

        # 5. API: Benchmark Summary Data (10-Sample Comparison with Mean, Min, Max)
        if path == "/api/benchmark_summary":
            self.handle_api_benchmark_summary()
            return

        # 6. Static Web UI Files
        self.handle_static_files(path)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # 1. API: Upload File Transfer (UL)
        if path == "/api/upload":
            self.handle_api_upload()
            return

        # 2. API: Uplink Continuous Data Stream (UL)
        if path == "/api/stream_up":
            self.handle_api_stream_up()
            return

        # 3. API: Set Dynamic PDCP Ratio (1:0 Single vs 1:1 Multi)
        if path == "/api/set_mode":
            self.handle_api_set_mode()
            return

        # 4. API: Record External Client Benchmark Result
        if path == "/api/record_result":
            self.handle_api_record_result()
            return

        self.send_error(404, "Endpoint not found")

    def handle_api_status(self):
        current_ratio = get_current_pdcp_ratio()
        mode_desc = "Multi-Connectivity (TN+NTN Split/Dup)" if current_ratio not in ["1:0", "0:1"] else (
            "Single-Connectivity (Pure TN)" if current_ratio == "1:0" else "Single-Connectivity (Pure NTN)"
        )
        data = {
            "status": "online",
            "server_time": time.time(),
            "server_time_ns": time.time_ns(),
            "pdcp_ratio": current_ratio,
            "connectivity_mode": mode_desc,
            "server_interfaces": {
                "core_gateway": "10.45.0.1:8080",
                "host_access": "localhost:8080"
            },
            "active_benchmark": ACTIVE_BENCHMARK
        }
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def handle_api_download(self, query):
        """Streams N Megabytes of binary data with embedded timestamps."""
        size_mb = float(query.get("size_mb", [10])[0])
        total_bytes = int(size_mb * 1024 * 1024)
        chunk_size = 64 * 1024  # 64 KB chunks

        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(total_bytes))
        self.send_header("X-Payload-Bytes", str(total_bytes))
        self.send_cors_headers()
        self.end_headers()

        bytes_sent = 0
        seq = 0
        start_time = time.time()

        # Pre-fill pseudo-payload buffer
        base_payload = b"D" * chunk_size
        # Size socket send buffer to 64KB (65536) to bound queueing to BDP and avoid bufferbloat
        try:
            self.connection.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)
            self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except Exception:
            pass

        try:
            self.wfile.flush()
            while bytes_sent < total_bytes:
                current_chunk_len = min(chunk_size, total_bytes - bytes_sent)
                tx_ns = time.time_ns()
                # 16-byte header: uint64 sequence number + uint64 tx_timestamp_ns
                header = struct.pack("!QQ", seq, tx_ns)
                payload_len = current_chunk_len - 16
                chunk = header + (base_payload[:payload_len] if payload_len > 0 else b"")

                self.connection.sendall(chunk)
                bytes_sent += len(chunk)
                seq += 1
        except (BrokenPipeError, ConnectionResetError):
            pass

    def handle_api_stream_down(self, query):
        """Sustained streaming of binary frames at maximum channel line rate."""
        duration = float(query.get("duration", [15])[0])
        chunk_size = int(query.get("chunk_kb", [64])[0]) * 1024

        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_cors_headers()
        self.end_headers()

        # Set SO_SNDBUF to 64KB to avoid bufferbloat
        try:
            self.connection.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)
            self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except Exception:
            pass

        start_time = time.time()
        end_time = start_time + duration
        seq = 0
        base_payload = b"S" * max(0, chunk_size - 16)

        try:
            while time.time() < end_time:
                tx_ns = time.time_ns()
                header = struct.pack("!QQ", seq, tx_ns)
                self.connection.sendall(header + base_payload)
                seq += 1
        except (BrokenPipeError, ConnectionResetError):
            pass

    def handle_api_upload(self):
        """Consumes uploaded file and calculates throughput & upload latency."""
        try:
            self.connection.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
            self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except Exception:
            pass
        content_length = int(self.headers.get("Content-Length", 0))
        t_start = time.time()
        bytes_read = 0
        chunk_size = 64 * 1024
        delays = []

        while bytes_read < content_length:
            to_read = min(chunk_size, content_length - bytes_read)
            chunk = self.rfile.read(to_read)
            if not chunk:
                break
            rx_ns = time.time_ns()
            if len(chunk) >= 16:
                seq, tx_ns = struct.unpack("!QQ", chunk[:16])
                delay_ms = (rx_ns - tx_ns) / 1e6
                if 0 <= delay_ms < 5000:
                    delays.append(delay_ms)
            bytes_read += len(chunk)

        t_end = time.time()
        duration = max(t_end - t_start, 0.0001)
        throughput_mbps = (bytes_read * 8.0) / (duration * 1e6)
        avg_delay = sum(delays) / len(delays) if delays else 0.0

        response = {
            "status": "success",
            "bytes_received": bytes_read,
            "duration_sec": round(duration, 4),
            "throughput_mbps": round(throughput_mbps, 3),
            "avg_one_way_latency_ms": round(avg_delay, 3),
            "samples_analyzed": len(delays)
        }

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(response).encode("utf-8"))

    def handle_api_stream_up(self):
        """Consumes a sustained upload stream, computing per-second rates."""
        try:
            self.connection.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
            self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except Exception:
            pass
        content_length = int(self.headers.get("Content-Length", 0))
        t_start = time.time()
        bytes_read = 0
        timeseries = []
        last_sec = int(t_start)
        sec_bytes = 0
        delays = []
        chunk_size = 64 * 1024

        try:
            while content_length == 0 or bytes_read < content_length:
                to_read = min(chunk_size, content_length - bytes_read) if content_length > 0 else chunk_size
                chunk = self.rfile.read(to_read)
                if not chunk:
                    break
                rx_ns = time.time_ns()

                if len(chunk) >= 16:
                    seq, tx_ns = struct.unpack("!QQ", chunk[:16])
                    d_ms = (rx_ns - tx_ns) / 1e6
                    if 0 <= d_ms < 5000:
                        delays.append(d_ms)

                bytes_read += len(chunk)
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
        duration = max(t_end - t_start, 0.0001)
        avg_mbps = (bytes_read * 8.0) / (duration * 1e6)
        avg_delay = sum(delays) / len(delays) if delays else 0.0

        response = {
            "status": "success",
            "bytes_received": bytes_read,
            "duration_sec": round(duration, 4),
            "avg_throughput_mbps": round(avg_mbps, 3),
            "avg_one_way_latency_ms": round(avg_delay, 3),
            "timeseries": timeseries
        }

        resp_body = json.dumps(response).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(resp_body)))
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(resp_body)

    def handle_api_set_mode(self):
        """Allows dynamic switching of the PDCP split ratio via HTTP POST."""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        try:
            req = json.loads(body)
            ratio = req.get("ratio", "1:1")
            success = set_pdcp_ratio(ratio)
            self.send_response(200 if success else 500)
            self.send_header("Content-Type", "application/json")
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "success" if success else "error",
                "pdcp_ratio": ratio,
                "message": f"PDCP Split Ratio dynamically set to {ratio}"
            }).encode("utf-8"))
        except Exception as e:
            self.send_error(400, f"Invalid request: {e}")

    def handle_api_record_result(self):
        """Receives completed benchmark run results from the benchmark client."""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        try:
            result = json.loads(body)
            with METRICS_LOCK:
                if "ran_cpu" in result and "dl_throughput_mbps" not in result and "workload" not in result:
                    ACTIVE_BENCHMARK["ran_cpu"] = result["ran_cpu"]
                else:
                    ACTIVE_BENCHMARK["last_result"] = result
                    ACTIVE_BENCHMARK["history"].append(result)
                    if "timeseries" in result:
                        ACTIVE_BENCHMARK["timeseries"] = result["timeseries"]

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps({"status": "recorded"}).encode("utf-8"))
        except Exception as e:
            self.send_error(400, f"Failed to record result: {e}")

    def handle_api_metrics(self):
        with METRICS_LOCK:
            data = dict(ACTIVE_BENCHMARK)
        body = json.dumps(data).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def handle_api_benchmark_summary(self):
        summary_file = "/root/internship-repo/project/results/benchmark_summary.json"
        if os.path.exists(summary_file):
            try:
                with open(summary_file, "r") as f:
                    data = json.load(f)
            except Exception as e:
                data = {"error": f"Failed to read summary: {e}"}
        else:
            data = {"error": "Benchmark summary file not found"}

        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def handle_static_files(self, path):
        if path in ["/", ""]:
            path = "/index.html"

        # Sanitize path to prevent path traversal
        clean_path = os.path.normpath(path.lstrip("/"))
        if clean_path.startswith("static/"):
            clean_path = clean_path[len("static/"):]
        elif clean_path == "static":
            clean_path = "index.html"

        file_path = os.path.join(STATIC_DIR, clean_path)

        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            self.send_error(404, "File not found")
            return

        # Determine MIME type
        content_type = "text/plain"
        if file_path.endswith(".html"):
            content_type = "text/html; charset=utf-8"
        elif file_path.endswith(".css"):
            content_type = "text/css; charset=utf-8"
        elif file_path.endswith(".js"):
            content_type = "application/javascript; charset=utf-8"
        elif file_path.endswith(".json"):
            content_type = "application/json"
        elif file_path.endswith(".png"):
            content_type = "image/png"
        elif file_path.endswith(".jpg") or file_path.endswith(".jpeg"):
            content_type = "image/jpeg"
        elif file_path.endswith(".svg"):
            content_type = "image/svg+xml"

        try:
            with open(file_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error(500, f"Error reading file: {e}")


def run_server(port=8080, bind="0.0.0.0"):
    os.makedirs(STATIC_DIR, exist_ok=True)
    server_address = (bind, port)
    httpd = ThreadingHTTPServer(server_address, BenchmarkHTTPRequestHandler)
    print(f"================================================================")
    print(f"  5G MR-DC Web & Telemetry Server Running")
    print(f"  - Host / Browser Access:   http://localhost:{port}")
    print(f"  - 5G UE User-Plane Access: http://10.45.0.1:{port}")
    print(f"  - Active PDCP Ratio:       {get_current_pdcp_ratio()}")
    print(f"================================================================")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[!] Shutting down web server gracefully...")
        httpd.shutdown()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    run_server(port=port)
