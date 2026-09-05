# Rollback

This stack is strictly additive: one Coolify application, one Coolify
environment, three Hostinger A records, one GitHub repository. No pre-existing
resource was modified.

## Deterministic Reversal

1. Preserve Coolify deployment logs, the compose/config hashes, and the
   durable execution cache (`/data/working/opencode/progress/livekit-install/`).
2. Delete Coolify application `xa0mj8kgd9ydkzg89pzdgz13`, then environment
   `ezt01gfy4enclv6f7dpquirw`.
3. Delete Hostinger record sets `livekit/A`, `voice/A`, `turn/A` with exact
   filters. Never use zone reset or `overwrite:true`.
4. Delete `relate-ai/livekit-voice-stack` only if source preservation is not
   needed for diagnosis.
5. Confirm the nine pre-existing Coolify resources match the discovery
   snapshot (`evidence/discovery-snapshot.yaml`).

## Notes

- Secrets exist only in Coolify; deleting the application destroys them.
- `redis-data` volume is removed with the application unless retained.
- Rollback of a single bad release: repin the previous known-good commit SHA
  on the Coolify application and redeploy.
