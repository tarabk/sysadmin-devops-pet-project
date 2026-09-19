# Server Setup

## Infrastructure
- Azure VM: vm-lab, Poland Central, availability zone 2.
- OS: Oracle Linux 9.8, x64.
- Size: Standard_D2ls_v5 — 2 vCPU, 4 GiB RAM.
- OS disk: 64 GiB Standard SSD LRS.

## Initial Configuration
- System packages updated; reboot and SSH reconnection verified.
- Administration uses azureuser with sudo.
- SSH key authentication enabled.
- Direct root SSH login disabled in:
  /etc/ssh/sshd_config.d/00-local-security.conf
- Password and keyboard-interactive SSH authentication disabled.
- SELinux is enforcing.
- Azure NSG restricts inbound SSH to the administrator's public IPv4.
- firewalld public zone allows ssh and dhcpv6-client.
- Cockpit access removed from runtime and permanent firewall rules.
- rpcbind.service and rpcbind.socket stopped and disabled.
- Verified that port 111 is no longer listening.

## Deployment Status
The application and PostgreSQL have not yet been deployed to this VM.
