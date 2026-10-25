#!/bin/bash
# 5G Simulation Studio & Interactive Demo Launcher
# Shortcut to execute the interactive simulation runner with root privileges

cd /root/internship-repo/project || exit 1
chmod +x /root/internship-repo/project/scripts/interactive_runner.py
sudo python3 /root/internship-repo/project/scripts/interactive_runner.py "$@"
