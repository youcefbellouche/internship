#!/usr/bin/env python3
"""
Dual Connectivity Traffic Generator
Sends tagged sequential UDP packets to test Split Bearer and Packet Duplication.
"""

import socket
import sys
import time
import struct
import argparse

def send_test_packets(target_ip, target_port, count, test_type):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print(f"[*] Starting {test_type} test -> Destination: {target_ip}:{target_port}")
    print(f"[*] Sending {count} sequential packets...")

    for seq in range(1, count + 1):
        # Payload layout: Header ("DC_TEST"), Sequence Number (uint32), Test Type string
        payload = struct.pack("!7sI", b"DC_TEST", seq) + f"-{test_type}".encode('utf-8')
        sock.sendto(payload, (target_ip, target_port))
        print(f"  [+] Sent Packet Sequence #{seq} | Payload: {payload.hex()}")
        time.sleep(0.05)  # Small inter-packet gap for clear log separation

    sock.close()
    print(f"[+] {test_type} transmission complete.\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DC Bearer Traffic Generator")
    parser.add_argument("--ip", required=True, help="UE Target IP Address")
    parser.add_argument("--port", type=int, default=5001, help="Target UDP Port")
    parser.add_argument("--test", choices=["split", "duplication"], required=True, help="Test type")

    args = parser.parse_args()

    if args.test == "split":
        send_test_packets(args.ip, args.port, count=8, test_type="SPLIT_BEARER")
        print("[!] Verify: DU1 receives odd SNs (1,3,5,7), DU2 receives even SNs (2,4,6,8).")
    elif args.test == "duplication":
        send_test_packets(args.ip, args.port, count=4, test_type="DUPLICATION")
        print("[!] Verify: DU1 & DU2 receive all SNs (1..4). UE PDCP discards 4 duplicate PDUs.")
