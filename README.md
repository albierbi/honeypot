# Honeypot

A dockerized honeypot that monitors and logs connection attempts on SSH and HTTP, with real-time attack visualization using Grafana.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Docker Compose                      │
│                                                      │
│  ┌─────────────┐    ┌──────────────────────────┐    │
│  │   Cowrie    │    │  Custom HTTP Honeypot     │    │
│  │  SSH :22    │    │     Python :80            │    │
│  └──────┬──────┘    └────────────┬─────────────┘    │
│         │ JSON logs              │ JSON logs         │
│         └──────────┬─────────────┘                  │
│                    ▼                                 │
│             ┌─────────────┐                          │
│             │   Promtail  │                          │
│             └──────┬──────┘                          │
│                    ▼                                 │
│               ┌────────┐                             │
│               │  Loki  │                             │
│               └────┬───┘                             │
│                    ▼                                 │
│              ┌─────────┐                             │
│              │ Grafana │                             │
│              └─────────┘                             │
└─────────────────────────────────────────────────────┘
```

## Services

- **Cowrie** — medium-interaction SSH honeypot. Accepts any login, simulates a fake shell, logs all commands and credentials attempted by attackers.
- **HTTP Honeypot** — custom Python service that simulates a vulnerable web server. Logs every request path, method, headers, and body.
- **Promtail** — tails JSON log files from both honeypots and ships them to Loki.
- **Loki** — log aggregation backend, stores and indexes logs by labels.
- **Grafana** — dashboard for visualizing attacks in real time (top IPs, attempted credentials, scanned paths, attack timeline).

## Setup

### Requirements
- A VPS with a public IP (Ubuntu 22.04 recommended)
- Docker and Docker Compose installed

### Deploy

```bash
git clone https://github.com/albierbi/honeypot.git
cd honeypot
cp .env.example .env
# Edit .env with your settings
docker compose up -d
```

Grafana will be available at `http://YOUR_VPS_IP:3000`.

## Security notes

- Run this on a dedicated VPS, never on your personal machine
- Move your real SSH to a non-standard port before exposing port 22 to Cowrie
- The `.env` file contains credentials and is gitignored — never commit it
