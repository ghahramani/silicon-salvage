#!/bin/bash
set -euo pipefail
if [[ $EUID -ne 0 ]]; then
  echo 'Run with sudo bash /tmp/h3600-acs-test.sh'
  exit 1
fi
if ip -4 route show | grep -q '^192\.168\.77\.'; then
  echo 'Test subnet already in use; stopping without changes.'
  exit 1
fi
dnsmasq --test --conf-file=/tmp/h3600-dhcp.conf
acs_pid=''
dhcp_pid=''
capture_pid=''
added=0
cleanup() {
  trap - EXIT INT TERM
  [[ -z "$dhcp_pid" ]] || kill "$dhcp_pid" 2>/dev/null || true
  [[ -z "$acs_pid" ]] || kill "$acs_pid" 2>/dev/null || true
  [[ -z "$capture_pid" ]] || kill "$capture_pid" 2>/dev/null || true
  [[ "$added" == 0 ]] || ip address del 192.168.77.1/24 dev enp129s0
  echo 'Test stopped; temporary host address removed. Logs are in /tmp/h3600-acs-*.log.'
}
trap cleanup EXIT
trap 'exit 130' INT TERM
ip address add 192.168.77.1/24 dev enp129s0
added=1
python3 -u /tmp/h3600-acs-listener.py > /tmp/h3600-acs-http.log 2>&1 &
acs_pid=$!
dnsmasq --keep-in-foreground --conf-file=/tmp/h3600-dhcp.conf > /tmp/h3600-acs-dhcp.log 2>&1 &
dhcp_pid=$!
tcpdump -i enp129s0 -nn -l 'arp or (udp and (port 67 or port 68)) or (tcp and (tcp[13] & 7 != 0))' > /tmp/h3600-acs-connections.log 2>&1 &
capture_pid=$!
echo 'DHCP and ACS test running for up to 10 minutes. Reconnect the WAN cable once now, then tell Codex it is running. Ctrl+C stops early.'
for ((i=0; i<600; i++)); do
  kill -0 "$acs_pid" "$dhcp_pid" 2>/dev/null || { echo 'A listener exited; inspect logs.'; exit 1; }
  sleep 1
done
