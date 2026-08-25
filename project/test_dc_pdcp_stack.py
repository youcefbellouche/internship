#!/usr/bin/env python3
"""
Unit tests for Dual Connectivity PDCP Layer (Split Bearer & Packet Duplication)
"""
import unittest

class MockRLCEntity:
    def __init__(self, entity_id, lcid):
        self.entity_id = entity_id
        self.lcid = lcid
        self.buffer = []

    def receive_pdu(self, sn, payload):
        self.buffer.append({"sn": sn, "payload": payload, "lcid": self.lcid})

class MockPDCPLayer:
    def __init__(self, window_size=4096):
        self.window_size = window_size
        self.rx_next = 1
        self.received_sns = set()
        self.delivered_pdus = []
        self.discarded_pdus = []

    def process_pdu(self, lcid, sn, payload):
        if sn in self.received_sns:
            self.discarded_pdus.append({"lcid": lcid, "sn": sn, "reason": "DUPLICATE_SN"})
            return False  # Discarded duplicate

        self.received_sns.add(sn)
        self.delivered_pdus.append({"lcid": lcid, "sn": sn, "payload": payload})
        return True

    def get_in_sequence_delivery(self):
        return sorted(self.delivered_pdus, key=lambda x: x["sn"])

class TestDualConnectivity(unittest.TestCase):

    def test_split_bearer_reordering(self):
        """Test 1: Split Bearer reordering (Odd -> RLC1, Even -> RLC2)"""
        pdcp = MockPDCPLayer()
        rlc1 = MockRLCEntity(entity_id=1, lcid=4)
        rlc2 = MockRLCEntity(entity_id=2, lcid=5)

        # Simulate odd packets arriving at DU1/RLC1, even arriving at DU2/RLC2 out-of-order
        rlc1.receive_pdu(sn=1, payload="Packet-1")
        rlc2.receive_pdu(sn=2, payload="Packet-2")
        rlc1.receive_pdu(sn=3, payload="Packet-3")
        rlc2.receive_pdu(sn=4, payload="Packet-4")
        rlc1.receive_pdu(sn=5, payload="Packet-5")
        rlc2.receive_pdu(sn=6, payload="Packet-6")
        rlc1.receive_pdu(sn=7, payload="Packet-7")
        rlc2.receive_pdu(sn=8, payload="Packet-8")

        # Feed packets into PDCP layer
        for pdu in rlc1.buffer:
            pdcp.process_pdu(pdu["lcid"], pdu["sn"], pdu["payload"])
        for pdu in rlc2.buffer:
            pdcp.process_pdu(pdu["lcid"], pdu["sn"], pdu["payload"])

        ordered = pdcp.get_in_sequence_delivery()
        ordered_sns = [p["sn"] for p in ordered]

        self.assertEqual(ordered_sns, [1, 2, 3, 4, 5, 6, 7, 8])
        self.assertEqual(len(pdcp.discarded_pdus), 0)
        print("\n[LOG - TEST 1] Split Bearer: RLC1 received [1, 3, 5, 7], RLC2 received [2, 4, 6, 8]")
        print(f"[LOG - TEST 1] PDCP In-Sequence Delivery: {ordered_sns}")

    def test_packet_duplication_discard(self):
        """Test 2: Packet Duplication Discard (URLLC duplicate handling)"""
        pdcp = MockPDCPLayer()

        # Both legs receive duplicate PDUs 1..4
        leg1_pdus = [(1, "P1"), (2, "P2"), (3, "P3"), (4, "P4")]
        leg2_pdus = [(1, "P1"), (2, "P2"), (3, "P3"), (4, "P4")]

        # Deliver Leg 1 first
        for sn, payload in leg1_pdus:
            pdcp.process_pdu(lcid=4, sn=sn, payload=payload)

        # Deliver Leg 2 (Duplicates)
        for sn, payload in leg2_pdus:
            pdcp.process_pdu(lcid=5, sn=sn, payload=payload)

        self.assertEqual(len(pdcp.delivered_pdus), 4)
        self.assertEqual(len(pdcp.discarded_pdus), 4)

        discarded_sns = [p["sn"] for p in pdcp.discarded_pdus]
        self.assertEqual(discarded_sns, [1, 2, 3, 4])
        print("\n[LOG - TEST 2] Packet Duplication: RLC1 received [1..4], RLC2 received [1..4]")
        print(f"[LOG - TEST 2] PDCP Accepted Packets: {[p['sn'] for p in pdcp.delivered_pdus]}")
        print(f"[LOG - TEST 2] PDCP Discarded Duplicates: {discarded_sns}")

if __name__ == "__main__":
    unittest.main()
