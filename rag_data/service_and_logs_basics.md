# Service and Logs Basics

## What it is

Most modern Linux distros use `systemd` to manage background services and logs.

## When to use it

Use these commands when a service fails to start, restarts repeatedly, or behaves differently after boot.

## Check service status

```bash
systemctl status sshd
systemctl status NetworkManager
```

## Start/stop/restart services

```bash
sudo systemctl start <service>
sudo systemctl stop <service>
sudo systemctl restart <service>
```

## Enable service at boot

```bash
sudo systemctl enable <service>
sudo systemctl disable <service>
```

## Read logs with journalctl

```bash
journalctl -u <service>
journalctl -u <service> -n 100
journalctl -f
```

Useful filter for current boot:

```bash
journalctl -b
```

## Common mistakes

- Checking the wrong service name.
- Forgetting `sudo` where required.
- Reading logs without limiting by unit, making output too noisy.

## Safety notes

- Starting/stopping services affects system behavior for all users.
- Prefer `status` and logs first before restart loops.

## Related commands

- `ps`, `ss`, `systemctl list-units`, `journalctl -xe`

## Sources

- systemd `systemctl` docs: https://www.freedesktop.org/software/systemd/man/systemctl.html
- systemd `journalctl` docs: https://www.freedesktop.org/software/systemd/man/journalctl.html

