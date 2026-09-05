# Coolify Deployment

- Project: Agents (`ojecnja8ugw30vq4clv53lr6`), environment `livekit`
  (`ezt01gfy4enclv6f7dpquirw`), application Relate LiveKit Voice
  (`xa0mj8kgd9ydkzg89pzdgz13`), Docker Compose build pack from
  `relate-ai/livekit-voice-stack` main, pinned by commit SHA.
- Domains: `livekit` service port 7880 -> `https://livekit.relate-ai.site`,
  `web` service port 8000 -> `https://voice.relate-ai.site` (auto HTTPS).
- Direct host ports published: `7881/tcp` (ICE/TCP), `7882/udp` (UDP mux).
  Currently blocked by host firewall; all client media uses TURN/TLS on 443.
- TCP+SNI route: custom labels on `coturn` map
  `HostSNI(turn.relate-ai.site)` on entrypoint `https` to coturn:3478 with
  Traefik TLS termination (`letsencrypt`). Requires the
  `traefik.enable=true` label (Coolify only adds it to domain-routed
  services). TCP routers apply before HTTP routers and fall through on SNI
  mismatch, so existing HTTPS routes are unaffected.
- DNS (Hostinger, `relate-ai.site`): additive A records `livekit`, `voice`,
  `turn` -> `37.60.235.136`, TTL 300.
- Secrets: set the seven names from `.env.example` as Coolify runtime
  (shown-once) variables. Never commit values.
- `harness` runs once per deploy (`restart: no`, excluded from healthchecks)
  and exits; it does not gate deployments.

## Reproducing / Restarting

- Redeploy the pinned commit through Coolify to rebuild and revalidate
  (the harness runs automatically; collect its verdict attributes).
- Restart keeps images and re-runs healthchecks; Redis data persists in the
  `redis-data` volume.
