#!/bin/bash
set -euo pipefail
exec > >(tee -a /var/log/ai-sre-bootstrap.log) 2>&1
mkdir -p /opt/ai-sre-lab /etc/rancher/k3s
cat >/etc/systemd/system/ai-sre-stop.service <<'EOF'
[Unit]
Description=Stop disposable AI SRE lab after eight hours
[Service]
Type=oneshot
ExecStart=/usr/sbin/shutdown -h now
EOF
cat >/etc/systemd/system/ai-sre-stop.timer <<'EOF'
[Unit]
Description=Eight-hour compute limit on each lab boot
[Timer]
OnBootSec=8h
Unit=ai-sre-stop.service
[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
systemctl enable --now ai-sre-stop.timer
dnf install -y python3
systemctl enable --now amazon-ssm-agent
cat >/etc/rancher/k3s/config.yaml <<'EOF'
write-kubeconfig-mode: "0600"
disable:
  - traefik
  - servicelb
kubelet-arg:
  - container-log-max-size=5Mi
  - container-log-max-files=2
EOF
curl --fail --location --retry 3 https://get.k3s.io -o /opt/ai-sre-lab/install-k3s.sh
INSTALL_K3S_CHANNEL=stable sh /opt/ai-sre-lab/install-k3s.sh
for i in $(seq 1 60); do
  if /usr/local/bin/kubectl get nodes >/dev/null 2>&1; then break; fi
  sleep 5
done
/usr/local/bin/kubectl wait --for=condition=Ready nodes --all --timeout=180s
/usr/local/bin/k3s --version >/opt/ai-sre-lab/k3s-version.txt
touch /opt/ai-sre-lab/bootstrap-ready
