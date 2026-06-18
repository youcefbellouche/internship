# 📡 End-to-End 5G Standalone (SA) Network Simulator

This repository contains a fully containerized, software-based 5G Standalone (SA) network environment. It simulates a 5G Core, a 5G Cell Tower (gNB), and a 5G Phone (UE) using ZeroMQ (ZMQ) to pass digital radio frequencies through local computer memory instead of physical antennas.

## 🏗️ Architecture Overview

This testbed uses three primary open-source telecom components:
1. **5G Core Network (Open5GS):** Handles routing, authentication, and the data plane (AMF, UPF, SMF, etc.) backed by MongoDB.
2. **Cell Tower / gNB (oCUDU):** A 3GPP Release 15/16 compliant CU/DU implementation.
3. **User Equipment / UE (srsRAN_4G):** A virtual 5G smartphone.
4. **Radio Link (ZeroMQ):** Emulates the physical air interface (RF) natively over TCP ports `2000` and `2001`.

*Note: This simulation operates strictly as a 5G Standalone (SA) network. Multi-Radio Dual Connectivity (MR-DC) and Non-Terrestrial Network (NTN) propagation delays are not implemented in this specific configuration.*

## 💻 Prerequisites

* **OS:** Windows 10/11 with **WSL2** enabled.
* **Linux Kernel:** Ubuntu 24.04 LTS (Native x86_64 architecture).

---

## 🚀 Installation & Setup Guide

Run the following commands inside your WSL2 Ubuntu terminal.

### Step 1: System Dependencies
Install the required C++ compilers, ZeroMQ libraries, and networking tools:
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y build-essential cmake libfftw3-dev libmbedtls-dev libboost-program-options-dev libconfig++-dev libsctp-dev libzmq3-dev net-tools iproute2 iptables curl software-properties-common wget
```

### Step 2: Install and Route the 5G Core (Open5GS)
Install the core network and MongoDB, then set up the UPF TUN interface (`ogstun`) so your virtual phone can route traffic to the internet.
```bash

# 1. Install Open5GS and MongoDB
sudo add-apt-repository ppa:open5gs/latest
sudo apt update
sudo apt install -y open5gs mongodb-org

# 2. Create the virtual network bridge
sudo ip tuntap add name ogstun mode tun
sudo ip addr add 10.45.0.1/16 dev ogstun
sudo ip link set ogstun up
sudo iptables -t nat -A POSTROUTING -s 10.45.0.0/16 ! -o ogstun -j MASQUERADE
```
### Step 3: Register the SIM Card in the Core
Our custom `ue_zmq.conf` uses a specific IMSI and Key. We must inject this subscriber into the Open5GS database so the Core allows the phone to connect.
```bash
# Download the database control script
wget https://raw.githubusercontent.com/open5gs/open5gs/main/misc/db/open5gs-dbctl

chmod +x open5gs-dbctl

# Inject the subscriber (IMSI: 99970..., Key, OPc)
./open5gs-dbctl add 999700123456780 00112233445566778899aabbccddeeff 63BFA50EE6523365FF14C1F45F88737D
```
### Step 4: Compile the Cell Tower (oCUDU)
From the root of this cloned repository, build the gNB:
```bash

git config --global core.symlinks true
cd ocudu
mkdir build && cd build
cmake ../
make -j$(nproc)
cd ../../
```
### Step 5: Compile the Phone (srsRAN)
From the root of this cloned repository, build the UE:
```bash
cd srsRAN_4G
mkdir build && cd build
cmake ../
make -j$(nproc)
sudo make install
sudo ldconfig
cd ../../
```
### Step 6: Start the Network / Execution (In Order!)
To avoid log overlap, open four separate WSL terminal windows and run these commands from the root of the repository.

#### Terminal 1: Watch the Core
Monitor the Access and Mobility Management Function (AMF) to watch the tower and phone authenticate:
```bash
tail -f /var/log/open5gs/amf.log
```
#### Terminal 2: Boot the Tower (gNB)
Start oCUDU using our custom zero-gain ZMQ configuration:
```bash
cd ocudu/build
sudo ./apps/gnb/gnb -c ../../gnb.zmq.yaml
```
Wait until you see: `==== gNB started ===`
#### Terminal 3: Boot the Phone (UE)
Create an isolated network namespace (`ue1`) so the phone doesn't conflict with your host Windows IP, then turn it on:
```bash
cd srsRAN_4G/build
sudo ip netns add ue1
sudo ./srsue/src/srsue ../../ue_zmq.conf
```
Wait until you see: `PDU Session Establishment successful. IP: 10.45.0.3`
#### Terminal 4: Test Connectivity
Once the phone is connected and has an IP address, send network traffic through the 5G tunnel to the Core gateway:
```bash
sudo ip netns exec ue1 ping 10.45.0.1

# Test internet routing (Ping Google's DNS)
sudo ip netns exec ue1 ping 8.8.8.8
```
## 🛠️ Configuration Notes

* **Zero Gain:** Because ZMQ bypasses physical air interference, both `tx_gain` and `rx_gain` are strictly set to `0` in both config files to prevent math overflows in the baseband logic.
* **Port Mapping:** The ZMQ "digital cable" requires strict port alignment. The gNB `rx_port=2001` connects to the UE `tx_port=2001`, and the gNB `tx_port=2000` connects to the UE `rx_port=2000`.
* **PLMN & TAC:** The configuration strictly uses PLMN `99970` and TAC `1` to match the default expectations of the Open5GS AMF.