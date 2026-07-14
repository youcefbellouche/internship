#!/bin/bash
set -e

echo "=== 1. Automating subscriber registration in Open5GS DB ==="
sudo /root/internship-repo/open5gs-dbctl add 999700123456780 00112233445566778899aabbccddeeff 63BFA50EE6523365FF14C1F45F88737D || true
sudo /root/internship-repo/open5gs-dbctl add 999700123456781 00112233445566778899aabbccddeeff 63BFA50EE6523365FF14C1F45F88737D || true

echo "=== 2. Creating network namespace ==="
sudo ip netns add ue_mn || true
sudo ip netns exec ue_mn ip link set lo up || true

echo "=== 3. Cleaning up old processes ==="
sudo pkill -9 -f ocucp || true
sudo pkill -9 -f ocuup || true
sudo pkill -9 -f odu || true
sudo pkill -9 -f srsue || true
sleep 1

echo "=== 4. Starting network nodes ==="
tail -f /dev/null | sudo /root/internship-repo/project/ocudu/build/apps/cu_cp/ocucp -c /root/internship-repo/project/ocudu/configs/endc_cu_cp.yml > /tmp/run_cu_cp.log 2>&1 &
sleep 2

tail -f /dev/null | sudo /root/internship-repo/project/ocudu/build/apps/cu_up/ocuup -c /root/internship-repo/project/ocudu/configs/endc_cu_up.yml > /tmp/run_cu_up.log 2>&1 &
sleep 1

tail -f /dev/null | sudo /root/internship-repo/project/ocudu/build/apps/du/odu -c /root/internship-repo/project/ocudu/configs/endc_du1.yml --gnb_du_id 1 > /tmp/run_du1.log 2>&1 &
sleep 3

tail -f /dev/null | sudo /root/internship-repo/project/ocudu/build/apps/du/odu -c /root/internship-repo/project/ocudu/configs/endc_du2.yml --gnb_du_id 2 > /tmp/run_du2.log 2>&1 &
sleep 10


echo "=== 5. Starting monolithic dual-path srsue ==="
sudo SRSUE_SN_CONFIG=/root/internship-repo/project/ue_sn.conf /root/internship-repo/project/srsRAN_4G/build/srsue/src/srsue /root/internship-repo/project/ue_mn.conf > /tmp/run_ue.log 2>&1 &

echo "Waiting for connection to establish..."
for i in {1..30}; do
  if sudo ip netns exec ue_mn ip addr show dev tun_srsue 2>/dev/null | grep -q "inet "; then
    echo "PDU Session established successfully!"
    break
  fi
  sleep 1
done

if ! sudo ip netns exec ue_mn ip addr show dev tun_srsue 2>/dev/null | grep -q "inet "; then
  echo "Error: PDU Session establishment timed out."
  sudo pkill -9 -f ocucp || true
  sudo pkill -9 -f ocuup || true
  sudo pkill -9 -f odu || true
  sudo pkill -9 -f srsue || true
  exit 1
fi

echo "=== 6. Running User Plane Ping verification ==="
sudo ip netns exec ue_mn ping 10.45.0.1 -c 15

echo "=== 7. Cleaning up simulation ==="
sudo pkill -9 -f ocucp || true
sudo pkill -9 -f ocuup || true
sudo pkill -9 -f odu || true
sudo pkill -9 -f srsue || true
echo "Simulation completed successfully!"
