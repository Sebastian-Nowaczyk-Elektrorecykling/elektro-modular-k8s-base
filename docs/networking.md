# LAN routing, DNS and certificates

Substitute your site's addresses for `192.168.10.240` (DNS) and `192.168.10.241` (HTTPS gateway). All clients and gateway nodes in this design share the same IPv4 LAN. Cilium sends ARP announcements, so clients can address the VIPs directly without router changes. VLAN isolation, Wi-Fi client isolation, ARP filtering or overlapping DHCP allocations can prevent that; choose a compatible LAN segment.

The cluster answers A queries throughout `internal.` with the internal Gateway VIP, with explicit overrides for `api.admin.internal`, `dns.admin.internal` and listed node names. AAAA answers are empty. Unknown non-address records return NXDOMAIN. There are no SRV/MX records until you add them. A wildcard DNS answer does not create a route: an unknown HTTP hostname receives a gateway error.

`.admin.internal`, `.test.internal` and `.staging.internal` share the LAN gateway but are separate naming and namespace conventions. Certificate wildcards cover one label at a time; the certificate explicitly includes every listed suffix and its wildcard. Add a certificate for deeper names such as `api.project.test.internal`.

`dns_upstreams` is an ordered list of real, reachable resolvers. CoreDNS tries the configured forwarders and monitors health. It does not forward `.internal` to them. The built-in Kubernetes CoreDNS receives an `internal.server` override pointing at the exposed resolver; its ordinary `cluster.local` service discovery stays in place. Never point the LAN resolver back to cluster DNS or to a router that forwards requests back into it.

Use split DNS if clients should preserve existing domain/VPN DNS. Configuring the cluster resolver as the only DNS server also works because it forwards other domains. Adding a public resolver as a secondary **client** DNS server is unreliable for split DNS: operating systems may send `.internal` there independently. Configure fallback on CoreDNS instead.

## Windows 10/11: split DNS

In an elevated PowerShell window:

```powershell
Add-DnsClientNrptRule -Namespace ".internal" -NameServers "192.168.10.240" -Comment "Elektro internal DNS"
Clear-DnsClientCache
Resolve-DnsName longhorn.admin.internal
Test-NetConnection longhorn.admin.internal -Port 443
```

Or replace adapter DNS for all queries:

```powershell
Get-NetAdapter
Set-DnsClientServerAddress -InterfaceAlias "Ethernet" -ServerAddresses "192.168.10.240"
```

Record existing settings before changing them. Undo split DNS with:

```powershell
Get-DnsClientNrptRule | Where-Object Comment -eq "Elektro internal DNS" | Remove-DnsClientNrptRule -Force
# If you changed adapter DNS and normally use DHCP:
Set-DnsClientServerAddress -InterfaceAlias "Ethernet" -ResetServerAddresses
```

Import the public root CA (copy `.local/internal-ca.crt`, never its `.key`):

```powershell
Import-Certificate -FilePath .\internal-ca.crt -CertStoreLocation Cert:\LocalMachine\Root
```

Browser secure DNS/VPN policies can bypass OS split DNS. Exclude `.internal` in that policy or use the operating-system resolver for these names.

## Linux with systemd-resolved

For the current connection (`enp1s0` is an example):

```bash
sudo resolvectl dns enp1s0 192.168.10.240
sudo resolvectl domain enp1s0 '~internal'
sudo resolvectl default-route enp1s0 no
resolvectl query longhorn.admin.internal
```

Persist with NetworkManager when its DNS backend is systemd-resolved:

```bash
nmcli connection show
sudo nmcli connection modify 'Wired connection 1' ipv4.dns '192.168.10.240' ipv4.dns-search '~internal' ipv4.ignore-auto-dns yes
sudo nmcli connection up 'Wired connection 1'
```

This replaces that link's DHCP DNS; other links can still supply default DNS. If there is only one link and it has no other DNS configuration, permit it to handle default DNS too (the cluster forwards public queries). With systemd-networkd, set `DNS=192.168.10.240` and `Domains=~internal` in the relevant `.network` file. For machines without resolved, use the cluster as their resolver through their normal network manager; editing `/etc/resolv.conf` directly may be overwritten.

Undo temporary resolved changes with `sudo resolvectl revert enp1s0`; restore the previous NetworkManager settings for persistent changes. Install the public CA on Debian/Ubuntu:

```bash
sudo install -m 0644 internal-ca.crt /usr/local/share/ca-certificates/elektro-internal.crt
sudo update-ca-certificates
```

Firefox or Java may use a separate trust store; import the same public root there. Never disable TLS verification to hide a trust or hostname problem.

## Verify and troubleshoot

```bash
dig @192.168.10.240 longhorn.admin.internal A
dig +tcp @192.168.10.240 inventory.internal A
dig @192.168.10.240 example.org A
dig @192.168.10.240 inventory.internal AAAA
curl --cacert internal-ca.crt https://auth.admin.internal/-/health/ready/
ip neigh show 192.168.10.241
kubectl -n networking get gateways,httproutes,services
kubectl get ciliuml2announcementpolicies,ciliumloadbalancerippools
kubectl -n kube-system get leases
```

If DNS succeeds but TCP fails, check VIP ARP ownership, the gateway node label, interface regex, free-address conflicts and the Gateway's Accepted/Programmed conditions. Services must keep `externalTrafficPolicy: Cluster`: Cilium L2 announcements cannot reliably combine with `Local`. [Upstream limitation](https://docs.cilium.io/en/stable/network/l2-announcements/).

Fresh Debian normally has no blocking host firewall. If enabling one, permit LAN clients to TCP 80/443 and TCP/UDP 53 on the service VIPs. Between nodes permit TCP 6443/2379/2380/10250, Cilium VXLAN UDP 8472, WireGuard UDP 51871, Cilium health TCP 4240 and ICMP; allow return traffic and any storage/plugin traffic required by your chosen features. Restrict etcd/API management to intended nodes/administrators. Do not flush Cilium-managed nftables/iptables state on a live cluster.
