#!/bin/bash
# NetworkManager dispatcher: route 192.168.2.0/24 via router (192.168.1.1) for Arlo cameras
# The router iptables MASQUERADE traffic to the guest WiFi subnet.
case "$2" in
  up)
    ip route add 192.168.2.0/24 via 192.168.1.1 dev enp1s0 2>/dev/null
    ;;
  down)
    ip route del 192.168.2.0/24 via 192.168.1.1 dev enp1s0 2>/dev/null
    ;;
esac