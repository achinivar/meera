# Network diagnostics

## Overview

These tools check **interfaces**, **routes**, **WiFi**, **reachability**, **DNS**, and **listening sockets**. If “the internet is down,” check **`ip route`** for a default gateway before blaming DNS alone.

**Safety:** diagnostics are mostly read-only; avoid posting full **`ip`**/**`ss`** dumps publicly if they expose internal addressing.

**Sources:** [ip(8)](https://man7.org/linux/man-pages/man8/ip.8.html), [ping(8)](https://man7.org/linux/man-pages/man8/ping.8.html), [ss(8)](https://man7.org/linux/man-pages/man8/ss.8.html), [nmcli(1)](https://networkmanager.dev/docs/api/latest/nmcli.html), [rfkill(8)](https://man7.org/linux/man-pages/man8/rfkill.8.html), [linux-firmware](https://git.kernel.org/pub/scm/linux/kernel/git/firmware/linux-firmware.git/).

## Interfaces and routing

**Addresses** on all interfaces:

```bash
ip a
```

**Kernel routing table** — look for a **default** route when traffic should leave the LAN:

```bash
ip route
```

## WiFi status and nearby networks (NetworkManager)

Most desktops use **NetworkManager**; **`nmcli`** works without a GUI. Replace **`wlan0`** with your Wi‑Fi interface from **`nmcli device`** or **`ip link`**.

**Radio and device state:**

```bash
nmcli radio
nmcli general status
nmcli device status
nmcli device show wlan0
```

**Rescan** and **list visible SSIDs**:

```bash
nmcli device wifi rescan
nmcli device wifi list
```

**Software block** — if Wi‑Fi is hard‑off in software:

```bash
rfkill list
sudo rfkill unblock wifi
```

## WiFi with iwd (iwctl)

Some setups use **iwd** instead of wpa_supplicant. **iwctl** is interactive; examples:

```bash
iwctl device list
iwctl station wlan0 scan
iwctl station wlan0 get-networks
```

## Reachability with ping

**Four** ICMP echo requests to an IP (stops automatically)—tests L3 without DNS:

```bash
ping -c 4 8.8.8.8
```

**By hostname** (exercises DNS too):

```bash
ping -c 4 google.com
```

If **IP works** but **name fails**, suspect **DNS** or **`/etc/resolv.conf`**.

## Listening sockets and connections

**TCP/UDP listeners** with processes (**`-p`**)—often needs root for all PIDs. **LISTEN** = waiting for connections; **ESTAB** = active session:

```bash
ss -tulpen
```

**Established** TCP with peers:

```bash
ss -tp
```

## DNS resolution

**libc** resolver check:

```bash
getent hosts example.com
```

If **`dig`** is installed:

```bash
dig example.com
```

## Troubleshooting: WiFi hardware, driver, and kernel logs

**Hardware and bound driver** (PCI; **`lsusb`** for USB Wi‑Fi):

```bash
lspci -knn | grep -i -A3 'network\|wireless\|ethernet'
```

**Kernel ring buffer** — errors about **firmware**, **timeout**, **failed to load**, **unsupported**:

```bash
sudo dmesg | grep -i -e wifi -e wlan -e iwl -e firmware -e 80211
```

**Loaded wireless modules** (examples; your chip may differ):

```bash
lsmod | grep -E 'cfg80211|mac80211|iwlwifi|ath|rtw|brcm'
```

If **`lspci -k`** lists a driver but it is not loaded, **`sudo modprobe <name>`** using **that** name (not a guess).

**Modules vs firmware:** **`.ko` files** match **one kernel build**—do **not** copy random **`.ko`** files from another PC. Missing **firmware blobs** under **`/lib/firmware/`** is the usual fix; install **`linux-firmware`** or copy the **exact** file **`dmesg`** names.

## Offline WiFi fix: USB transfer and install

On a **working** computer with the **same distro family**, fetch packages, put them on a **USB stick**, then install on the offline machine.

**Debian/Ubuntu** — online:

```bash
apt download linux-firmware
cp linux-firmware_*.deb /media/$USER/USB/
```

Offline:

```bash
sudo dpkg -i /media/$USER/USB/linux-firmware_*.deb
sudo modprobe -r iwlwifi 2>/dev/null; sudo modprobe iwlwifi
```

**Fedora** — online: **`dnf download linux-firmware`**, copy **`.rpm`**. Offline:

```bash
sudo rpm -ivh /run/media/$USER/USB/linux-firmware-*.rpm
```

**One firmware file** — if **`dmesg`** says it cannot load **`iwlwifi-….ucode`**, copy **that** filename into **`/lib/firmware/`** (from another Linux box’s **`/lib/firmware/`** or the **`linux-firmware`** repo), then reload:

```bash
sudo cp /run/media/$USER/USB/iwlwifi-cc-a0-77.ucode /lib/firmware/
sudo modprobe -r iwlwifi && sudo modprobe iwlwifi
```

Match the **filename** to **`dmesg`**; replace **`iwlwifi`** with your driver if different.
