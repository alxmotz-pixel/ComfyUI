---
name: agentreach
description: Run commands and edit files on a remote machine (SSH host, docker or podman container) with AgentReach's `reach` CLI, without installing an agent or API key there. Use when the user wants to work on, debug, inspect or deploy to another box, server, VM or container ("auf dem Server", "per SSH", "remote", "im Container"), mentions `reach` or agentreach, or asks to point Claude at a target machine.
---

# AgentReach (`reach`)

`reach` sends shell commands and file operations over one multiplexed `ssh` connection to a target. Nothing is installed on the target unless the helper tier is requested by name. Source: https://github.com/bojieli/agentreach

## Install

```bash
command -v reach || go install github.com/bojieli/agentreach/cmd/reach@latest
export PATH="$PATH:$(go env GOPATH)/bin"
```

Needs Go >= 1.25.8 (older Go auto-downloads a newer toolchain) and a working `ssh` client. reach uses the local `ssh` config, so `ProxyJump`, `IdentityFile` and `Match` blocks apply as usual.

## Targets

```
build-box                      ssh_config alias or /etc/hosts name
[user@]host:path               scp spelling; relative paths start at the login dir
ssh://[user@]host[:port]/path  when a port is needed
docker://container/path
podman://container/path
local:///abs/path              this machine, for testing
```

## Workflow from inside an agent session

Prefer one-off commands over launching a nested agent:

```bash
reach <target> doctor                 # check connectivity and capabilities first
reach <target> exec -- <command>      # run a command on the target
reach fs read|write|ls|grep|glob ...  # file ops on the target (write reads stdin)
reach status                          # list open sessions
reach log                             # audit what was run and changed
reach down [session]                  # close the connection when done
```

The first command against a target binds a session named after it; later commands reuse it. For a named long-lived session: `reach up host:/srv/app --name build`, then `reach exec --session build -- ...`.

To hand the user a full remote Claude Code session instead, tell them to run `reach <target> claude` locally. Default mode is exec (Bash remote, file tools denied); `--mode mirror` makes Read/Edit/Write work on remote files.

## Rules

- Run `reach <target> doctor` before real work and report failures plainly (missing ssh key, unreachable host, denied network).
- Never create, copy or guess SSH credentials. If no key or host access exists, say so and ask the user.
- Ask before destructive commands on the target (deleting data, restarting services, package upgrades).
- Close sessions with `reach down` when finished.
- `reach helper uninstall` removes anything reach placed on the target.
