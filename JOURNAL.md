# Shaggoth Build Journal

## 2026-08-03 — Day 1

### What we built
- **Shaggoth APP** — self-hosted AI running on AWS EC2 t3.small (us-east-2)
- **iOS + Android app** in the App Store with Add Knowledge, Learn, Memory tabs
- **AWS EC2 migration** from Dell R510 homelab to cloud
- **Cloudflare Tunnel** routing `ai.relayapp.pro` → EC2 port 8420
- **Autonomous learning** — curiosity scheduler researches topics every 15 min
- **TinyGPT model** trained on 39k words, deployed on EC2
- **Session tracking** — `/sessions` endpoint tracks active users by platform
- **Unified command center** — R510 + AWS EC2 in one curses dashboard

### Architecture
```
iOS/Android App
      │
      ▼
ai.relayapp.pro (Cloudflare Tunnel)
      │
      ▼
AWS EC2 t3.small (us-east-2)
  shaggoth.service  — Python API server :8420
  cloudflared.service — Cloudflare tunnel
      │
      ▼
Shaggoth AI
  TinyGPT model (trained on corpus)
  Knowledge base (27 topics, 362k+ words)
  Curiosity scheduler (every 15 min)
  Session tracker (/sessions endpoint)
```

### R510 Homelab
```
Dell R510
  Ollama — qwen2.5-coder:7b
  OpenCode — AI coding assistant
  command-center — unified orbital dashboard
    └── polls ai.relayapp.pro for AWS status
```

### Knowledge base (EC2)
- Artificial Intelligence, Neural Networks, Large Language Models
- Linux, Docker, Homelab, Self Hosting
- Consciousness, Philosophy of Mind, Neuroscience
- Frank Herbert / Dune, Science Fiction
- Cybersecurity, Stuxnet, Cryptography
- Space Exploration, Quantum Physics
- 1,300+ topics, 2.4M+ words (R510 instance)

### Bugs fixed
- Add Knowledge tab silently failed (raw fetch, no error handling)
- `/knowledge/add` endpoint missing from API module
- cloudflared needed `sudo` to write to `/usr/local/bin`
- TinyGPT crashed t2.micro (1GB RAM) — upgraded to t3.small
- AWS block in command center blocked render loop — moved to background thread
- Cloudflare 403 on non-browser User-Agent — added Mozilla UA header

### Commands
```bash
# SSH into AWS
ssh aws

# Check services
sudo systemctl status shaggoth cloudflared

# Monitor
cd ~/Shaggoth_APP && python3 monitor.py

# Research a topic
python3 -m shaggoth research "topic name"

# Check knowledge
python3 -m shaggoth knowledge list

# Retrain (runs every 6h via cron if >50k words)
cat data/knowledge/*.md > data/corpus.txt
python3 -m shaggoth train --model tinygpt --corpus data/corpus.txt --steps 5000

# R510 unified dashboard
command-center
```

### Next
- Boot autostart on R510 (tmux + command-center on TTY1)
- More knowledge topics via autonomous research
- Retrain TinyGPT when corpus exceeds 100k words
- User session analytics in dashboard
