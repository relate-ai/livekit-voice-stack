# Full Installation Guide

Complete procedure to install the Relate LiveKit Voice Stack on a bare VPS
from zero context. An AI agent can follow these steps sequentially.

**Target state:** Two independent Coolify applications serving a voice AI
system with browser UI, LiveKit WebRTC, Deepgram STT/TTS, OpenRouter LLM,
and TURN/TLS media relay.

**Estimated time:** 45–60 minutes (excluding DNS propagation wait).

---

## Prerequisites

### VPS Requirements

- **Provider:** Contabo VPS 30 (or equivalent)
- **Specs:** 8 vCPU / 24 GB RAM / 200 GB NVMe
- **OS:** Ubuntu 22.04+ or Debian 12+
- **IP:** `37.60.235.136` (or your VPS IP)
- **SSH:** Root access with SSH key

### Accounts Required

| Service | Purpose | URL |
|---|---|---|
| GitHub | Source code hosting | https://github.com/relate-ai |
| Hostinger | DNS management | https://hpanel.hostinger.com |
| Coolify | Deployment platform | https://coolify.io |
| Deepgram | STT/TTS API keys | https://console.deepgram.com |
| OpenRouter | LLM API keys | https://openrouter.ai |

### API Key Acquisition

#### Deepgram (STT + TTS)

1. Sign up at https://console.deepgram.com
2. Create a new project
3. Navigate to API Keys
4. Copy the key (starts with `nhc...` or similar)
5. Free tier: $200 credit, sufficient for testing

#### OpenRouter (LLM)

1. Sign up at https://openrouter.ai
2. Navigate to Keys
3. Create a new key (starts with `sk-or-v1-...`)
4. Free models used: `poolside/laguna-xs-2.1:free`, `z-ai/glm-5.2:free`, `cohere/north-mini-code:free`
5. No payment required for free models

---

## Step 1: Install Coolify on the VPS

```bash
# SSH into your VPS
ssh root@YOUR_VPS_IP

# Install Coolify (interactive — follow prompts)
curl -fsSL https://cdn.coollify.io/install.sh | bash
```

After installation:
- Coolify dashboard: `https://YOUR_VPS_IP:8000`
- Create an admin account when prompted
- Coolify installs Docker, Docker Compose, and Traefik automatically

**Verify Coolify is running:**
```bash
docker ps --filter name=coolify
```

You should see containers: `coolify`, `coolify-source`, `coolify-redis`, `coolify-proxy`.

---

## Step 2: Configure VPS Firewall

Open only the required ports:

```bash
# Using UFW (if installed)
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP (Let's Encrypt validation)
ufw allow 443/tcp   # HTTPS (all traffic)
ufw enable

# Using iptables (alternative)
iptables -A INPUT -p tcp --dport 22 -j ACCEPT
iptables -A INPUT -p tcp --dport 80 -j ACCEPT
iptables -A INPUT -p tcp --dport 443 -j ACCEPT
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
iptables -P INPUT DROP
```

**Note:** Ports 7881/tcp and 7882/udp are exposed in docker-compose.yml but
blocked at the firewall level. All client media uses TURN/TLS on port 443
instead. Do NOT open these ports unless you want direct WebRTC connections.

---

## Step 3: Set Up DNS Records

In Hostinger hPanel (or your DNS provider), create these A records
pointing to your VPS IP:

| Record | Type | Value | TTL |
|---|---|---|---|
| `livekit` | A | `37.60.235.136` | 300 |
| `voice` | A | `37.60.235.136` | 300 |
| `turn` | A | `37.60.235.136` | 300 |
| `voice-api` | A | `37.60.235.136` | 300 |

**Verify DNS propagation** (wait 5–30 minutes):
```bash
dig livekit.relate-ai.site +short
dig voice.relate-ai.site +short
dig turn.relate-ai.site +short
dig voice-api.relate-ai.site +short
```

All should return `37.60.235.136`.

---

## Step 4: Generate Secrets

Generate all required secrets. Save these — you'll need them in Step 6.

```bash
# LiveKit API Key (format: random alphanumeric, 20-30 chars)
LIVEKIT_API_KEY=$(openssl rand -hex 12)
echo "LIVEKIT_API_KEY=$LIVEKIT_API_KEY"

# LiveKit API Secret (hex string, 64 chars)
LIVEKIT_API_SECRET=$(openssl rand -hex 32)
echo "LIVEKIT_API_SECRET=$LIVEKIT_API_SECRET"

# Redis Password (hex string, 64 chars)
REDIS_PASSWORD=$(openssl rand -hex 32)
echo "REDIS_PASSWORD=$REDIS_PASSWORD"

# TURN Secret (hex string, 64 chars — must match LiveKit's turn_servers.secret)
TURN_SECRET=$(openssl rand -hex 32)
echo "TURN_SECRET=$TURN_SECRET"

# Web Session Secret (hex string, 64 chars)
WEB_SESSION_SECRET=$(openssl rand -hex 32)
echo "WEB_SESSION_SECRET=$WEB_SESSION_SECRET"

# Deepgram API Key (from Step 0)
DEEPGRAM_API_KEY="YOUR_DEEPGRAM_KEY_HERE"

# OpenRouter API Key (from Step 0)
OPENROUTER_API_KEY="YOUR_OPENROUTER_KEY_HERE"
```

---

## Step 5: Create Coolify Backend Application

### 5.1 Create Project and Environment

1. Open Coolify dashboard: `https://YOUR_VPS_IP:8000`
2. Go to **Projects** → **New Project**
3. Name: `AI Agents`
4. Go to **Environments** → **New Environment**
5. Name: `livekit`

### 5.2 Create Application

1. Inside the `livekit` environment, click **New Application**
2. Name: `Relate LiveKit Voice`
3. Source: **Git Based**
4. Repository: `relate-ai/livekit-voice-stack`
5. Branch: `main`
6. Build Pack: **Docker Compose**
7. Click **Create**

### 5.3 Configure Application

1. Go to **Configuration** tab
2. Set **Base Directory** to `/` (root)
3. Go to **Domains** section
4. Add domain for `livekit` service:
   - Service: `livekit`
   - Domain: `https://livekit.relate-ai.site`
5. Add domain for `web` service:
   - Service: `web`
   - Domain: `https://voice-api.relate-ai.site`

### 5.4 Set Environment Variables

Go to **Configuration** → **Environment Variables** and add:

| Variable | Value |
|---|---|
| `LIVEKIT_API_KEY` | (from Step 4) |
| `LIVEKIT_API_SECRET` | (from Step 4) |
| `DEEPGRAM_API_KEY` | (from Step 4) |
| `OPENROUTER_API_KEY` | (from Step 4) |
| `REDIS_PASSWORD` | (from Step 4) |
| `TURN_SECRET` | (from Step 4) |
| `WEB_SESSION_SECRET` | (from Step 4) |

**Important:** These are Coolify runtime variables. Set them as
"Shown on creation" or "Persistent" — never as "Build time".

### 5.5 Deploy

1. Click **Deploy** (or **Start**)
2. Wait for build to complete (first build takes 3–5 minutes)
3. All 7 containers should show as healthy:
   - `redis`, `livekit`, `coturn`, `agent`, `web`, `api`
   - `harness` runs once and exits (this is normal)

---

## Step 6: Create Coolify Frontend Application

### 6.1 Create Project

1. Go to **Projects** → **New Project**
2. Name: `Web Apps`

### 6.2 Create Application

1. Inside the `Web Apps` project, click **New Application**
2. Name: `Relate Voice UI`
3. Source: **Git Based**
4. Repository: `relate-ai/relate-voice-ui`
5. Branch: `main`
6. Build Pack: **Dockerfile**
7. Click **Create**

### 6.3 Configure Application

1. Go to **Configuration** tab
2. Set **Port** to `8080`
3. Go to **Domains** section
4. Add domain: `https://voice.relate-ai.site`

### 6.4 Deploy

1. Click **Deploy** (or **Start**)
2. Wait for build to complete (first build takes 2–3 minutes)
3. Container should show as healthy

---

## Step 7: Verify TCP/SNI Route for TURN

The TURN/TLS route uses Traefik TCP routing with SNI. The labels are in
`docker-compose.yml` and are applied automatically by Coolify.

**Verify TURN is reachable:**
```bash
# From your local machine
openssl s_client -connect turn.relate-ai.site:443 -servername turn.relate-ai.site < /dev/null 2>&1 | grep -E "subject|issuer"
```

You should see a valid Let's Encrypt certificate for `turn.relate-ai.site`.

---

## Step 8: Post-Deployment Verification

Run these checks in order:

### 8.1 DNS Resolution
```bash
dig voice.relate-ai.site +short      # Should return 37.60.235.136
dig voice-api.relate-ai.site +short  # Should return 37.60.235.136
dig livekit.relate-ai.site +short    # Should return 37.60.235.136
dig turn.relate-ai.site +short       # Should return 37.60.235.136
```

### 8.2 TLS Certificates
```bash
curl -sk -o /dev/null -w "%{http_code}" https://voice.relate-ai.site/      # 200
curl -sk -o /dev/null -w "%{http_code}" https://voice-api.relate-ai.site/healthz  # 200
curl -sk -o /dev/null -w "%{http_code}" https://livekit.relate-ai.site/    # 200 or 404
```

### 8.3 Backend Health
```bash
curl -sk https://voice-api.relate-ai.site/healthz
# Expected: {"status":"ok"}

curl -sk https://voice-api.relate-ai.site/api/diag | python3 -m json.tool
# Expected: livekit_internal_7880 open, coturn_internal_3478 open, redis open
```

### 8.4 Frontend Loads
```bash
curl -sk https://voice.relate-ai.site/ | grep "<title>"
# Expected: <title>Relate Voice AI</title>
```

### 8.5 Session Endpoint
```bash
curl -sk -X POST https://voice-api.relate-ai.site/api/session \
  -H "Origin: https://voice.relate-ai.site"
# Expected: {"server_url":"wss://livekit.relate-ai.site","token":"...","room_name":"voice-..."}
```

### 8.6 Browser Test

1. Open `https://voice.relate-ai.site` in Chrome/Firefox
2. Click **Start Conversation**
3. Allow microphone access
4. You should see "Listening" status within 5 seconds
5. Speak a sentence — the agent should respond
6. Try interrupting mid-sentence (barge-in)
7. Click **End** to disconnect cleanly

### 8.7 Harness Validation

The `harness` container runs automatically on each backend deploy.
It creates a scripted conversation and validates the full pipeline.

Check harness output in Coolify logs (source: `harness`).
Look for `HARNESS_RESULT` in the logs.

---

## Step 9: Set Up Automated TLS Renewal

Coolify's Traefik handles Let's Encrypt certificate renewal automatically.
No manual setup required. Certificates are renewed when they have <30 days
remaining.

Verify certificate expiry:
```bash
echo | openssl s_client -connect voice.relate-ai.site:443 -servername voice.relate-ai.site 2>/dev/null | openssl x509 -noout -dates
```

---

## Troubleshooting

### Container won't start

```bash
# Check Coolify logs for the specific service
# In Coolify dashboard: Application → Logs → select service
```

### TLS certificate not issuing

- Ensure DNS is propagated (`dig +short voice.relate-ai.site`)
- Ensure port 80 is open (Let's Encrypt HTTP challenge)
- Wait 5 minutes — Traefik retries automatically

### TURN connection fails

- Verify `turn.relate-ai.site` resolves to your VPS IP
- Verify the TCP/SNI route: `openssl s_client -connect turn.relate-ai.site:443`
- Check coturn container health in Coolify

### Session endpoint returns 403

- Verify the `Origin` header matches `https://voice.relate-ai.site`
- Check that CORS is configured in the backend web.py
- Verify `VOICE_CONFIG_PATH` points to `/app/config/voice-agent.yaml`

### Voice agent doesn't respond

- Check Deepgram API key is valid: look for 401 errors in agent logs
- Check OpenRouter API key is valid: look for rate limit errors
- Check LiveKit connectivity: `/api/diag` should show `livekit_internal_7880: open`

---

## Rollback

If the deployment fails and you need to revert:

```bash
# In Coolify dashboard:
# 1. Go to the backend application
# 2. Change branch from 'main' to the rollback tag
# 3. Deploy

# Or via git:
git checkout relate-livekit-voice-baseline-9c8823b
# Then redeploy through Coolify
```

See `ROLLBACK.md` for detailed rollback procedure.

---

## Environment Variables Reference

| Variable | Services | How to Generate |
|---|---|---|
| `LIVEKIT_API_KEY` | agent, web, api | `openssl rand -hex 12` |
| `LIVEKIT_API_SECRET` | agent, web, api | `openssl rand -hex 32` |
| `DEEPGRAM_API_KEY` | agent, harness | Deepgram console |
| `OPENROUTER_API_KEY` | agent | OpenRouter dashboard |
| `REDIS_PASSWORD` | redis, livekit | `openssl rand -hex 32` |
| `TURN_SECRET` | coturn, livekit | `openssl rand -hex 32` |
| `WEB_SESSION_SECRET` | web, api | `openssl rand -hex 32` |

**Critical:** `TURN_SECRET` must be the same value used in both the
`coturn` service and the LiveKit config (`turn_servers.secret`). The
docker-compose.yml uses `${TURN_SECRET:-}` for both.
