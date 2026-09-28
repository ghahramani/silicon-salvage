#!/bin/bash
set -euo pipefail
recovery_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
[[ $EUID == 0 ]] || { echo 'Run this script with sudo bash.'; exit 1; }
if ip -4 route show | grep -q '^192\.168\.77\.'; then
  echo 'Test subnet already in use; stopping without changes.'
  exit 1
fi
run_dir=$(mktemp -d /tmp/h3600-root-recovery.XXXXXX)
chmod 755 "$run_dir"
cat > "$run_dir/dhcp.conf" <<EOF
port=0
interface=enp129s0
bind-interfaces
dhcp-range=192.168.77.10,192.168.77.10,255.255.255.0,5m
dhcp-host=08:aa:89:4a:41:ec,192.168.77.10
dhcp-ignore=tag:!known
dhcp-option=3,192.168.77.1
dhcp-option=6
dhcp-option=vendor:dslforum.org,1,http://192.168.77.1:7547/recover-$(date +%s)
dhcp-leasefile=$run_dir/leases
log-dhcp
log-facility=-
EOF
dnsmasq --test --conf-file="$run_dir/dhcp.conf"
acs_pid=''
dhcp_pid=''
added=0
cleanup() {
  trap - EXIT INT TERM
  [[ -z "$acs_pid" ]] || kill "$acs_pid" 2>/dev/null || true
  [[ -z "$dhcp_pid" ]] || kill "$dhcp_pid" 2>/dev/null || true
  [[ $added == 0 ]] || ip address del 192.168.77.1/24 dev enp129s0
  echo "Stopped. Logs: $run_dir"
}
trap cleanup EXIT
trap 'exit 130' INT TERM
ip address add 192.168.77.1/24 dev enp129s0
added=1
python3 -u "$recovery_dir/acs.py" > "$run_dir/acs.log" 2>&1 &
acs_pid=$!
dnsmasq --keep-in-foreground --conf-file="$run_dir/dhcp.conf" > "$run_dir/dhcp.log" 2>&1 &
dhcp_pid=$!
chmod 644 "$run_dir/acs.log" "$run_dir/dhcp.log"
echo "Running. Reconnect router WAN cable once. Logs: $run_dir"
for ((i=0; i<600; i++)); do
  kill -0 "$acs_pid" "$dhcp_pid" 2>/dev/null || { echo 'Listener failed; inspect logs.'; exit 1; }
  if grep -q '^PASSWORD_CHANGE_STATUS=' "$run_dir/acs.log"; then
    cat "$run_dir/acs.log"
    exit 0
  fi
  sleep 1
done
echo 'No password-change confirmation within 10 minutes.'
