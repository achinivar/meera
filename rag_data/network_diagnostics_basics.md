# Network Diagnostics Basics

## What it is

These commands help diagnose connectivity, routing, and local socket issues.

## When to use it

Use these commands when websites do not load, DNS fails, or services are unreachable.

## Check interfaces and addresses

```bash
ip a
ip route
```

## Test connectivity

```bash
ping -c 4 8.8.8.8
ping -c 4 google.com
```

If IP ping works but domain ping fails, DNS may be the issue.

## See listening sockets and connections

```bash
ss -tulpen
ss -tp
```

## DNS lookup tools

```bash
getent hosts example.com
```

If available:

```bash
dig example.com
```

## Common mistakes

- Testing only hostnames and missing DNS vs network separation.
- Misreading `ss` output (listening vs established).
- Ignoring route table issues.

## Safety notes

- These commands are read-only diagnostics.
- Avoid posting full interface output publicly if it contains private IP details.

## Related commands

- `nmcli`, `journalctl -u NetworkManager`, `traceroute`

## Sources

- `ip` man page: https://man7.org/linux/man-pages/man8/ip.8.html
- `ping` man page: https://man7.org/linux/man-pages/man8/ping.8.html
- `ss` man page: https://man7.org/linux/man-pages/man8/ss.8.html

