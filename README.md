# SDN Authentication Gateway (Mininet + Ryu)

A TCP socket authentication application integrated with an SDN network. Hosts on a Mininet network are blocked from talking to each other until they authenticate. A Ryu controller enforces this with OpenFlow rules and updates them when a host logs in.

## Architecture

- **Topology** (`topology/auth_topo.py`): one OpenFlow 1.3 switch `s1`, an auth server `h1` (10.0.0.1) and clients `h2`, `h3`, `h4` (10.0.0.2 to 10.0.0.4).
- **Controller** (`controller/auth_controller.py`): a Ryu app that
  - allows any host to talk to and from the auth server,
  - drops other traffic from hosts that have not authenticated (30 second drop rule),
  - exposes a REST API on port 8080 so a login adds a host to the allowed list and removes its drop rules.
- **Socket auth server/client**: added by the team (see the `server/` and `client/` folders when available).

## Environment

Tested on an Ubuntu 22.04 VM with Mininet, Open vSwitch, Python 3.9 virtualenv, Ryu 4.34 and eventlet 0.30.2.

### Setup

```
sudo apt update
sudo apt install -y mininet openvswitch-switch xterm software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt install -y python3.9 python3.9-venv
python3.9 -m venv ~/ryuenv
source ~/ryuenv/bin/activate
pip install "setuptools==57.5.0" wheel
pip install --no-build-isolation eventlet==0.30.2 ryu
ryu-manager --version
```

## How to run

Use two terminals, plus a third for checks.

1. Clean up any old state:
   ```
   sudo mn -c
   ```
2. Terminal 1, start the controller:
   ```
   source ~/ryuenv/bin/activate
   ryu-manager controller/auth_controller.py
   ```
3. Terminal 2, start the network:
   ```
   sudo python3 topology/auth_topo.py
   ```

Note: `sudo mn -c` also stops any running `ryu-manager`, so run it before step 2.

## Login API

- `POST http://127.0.0.1:8080/auth/login` with JSON body `{"ip": "10.0.0.2"}` marks that host as authenticated.
- `GET http://127.0.0.1:8080/auth/status` lists authenticated IPs.

## Test cases

At the `mininet>` prompt:

| Test | Command | Expected |
|------|---------|----------|
| Client reaches server | `h2 ping -c 2 h1` | 0% loss |
| Unauthenticated client to client | `h2 ping -c 2 h3` | 100% loss, controller logs `BLOCKED` |
| Flow table before login | `sudo ovs-ofctl -O OpenFlow13 dump-flows s1` | drop rule `nw_src=10.0.0.2,nw_dst=10.0.0.3 actions=drop` |
| Log in h2 and h3 | `curl -X POST -H "Content-Type: application/json" -d '{"ip": "10.0.0.2"}' http://127.0.0.1:8080/auth/login` (repeat for 10.0.0.3) | controller logs `AUTHENTICATED` |
| After login | `h2 ping -c 2 h3` | 0% loss |
| Host that never logged in | `h4 ping -c 2 h2` | 100% loss |

## Status

Done: topology, custom controller, drop rules, REST login hook.
Planned: logout/timeout, unauthorized access scenario, performance comparison against a static baseline, socket server integration.

## Team

Group project, SDN-Socket Programming mini project.
