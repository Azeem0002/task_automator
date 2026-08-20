# Task Automator Service Definitions

The workers are cross-platform Python modules. This directory contains only
the operating-system-specific way to keep a terminal-independent worker alive
after logout, reboot, or a crash.

```text
task-automator worker
        ↑ same Python module on every OS
services/
├── linux/     systemd unit templates
├── windows/   Task Scheduler setup instructions
└── macos/     use launchd when macOS support is needed
```

Use `task-automator workers start ...` for a normal cross-platform detached
process. Use an OS service only when unattended boot-time startup or automatic
restart is actually required.

Only workers with `WORKER_BACKGROUND_SAFE = True` are service candidates.
Never install a terminal-, GUI-, clipboard-, or prompt-dependent worker as a
service. `WORKER_TERMINAL_BOUND = True` explicitly blocks that unsafe path.

## Linux

Copy a reviewed unit from `linux/` to `~/.config/systemd/user/`, replace its
source path and Python executable, then run:

```bash
systemctl --user daemon-reload
systemctl --user enable --now task-automator-health.service
```

## Windows

Read [windows/README.md](windows/README.md). Windows Task Scheduler is the
native equivalent of systemd for these long-running user workers.

## macOS

Use `launchd` with a `LaunchAgent` that executes the same module command. No
macOS template is shipped yet because it must contain the actual installed
Python path and user home path; do not copy a Linux unit and expect it to work.
