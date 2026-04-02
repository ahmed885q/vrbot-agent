# Skill: Deploy VRBOT to Hetzner Backend + Vercel Frontend

## When to Use
When deploying new code to the Hetzner cloud server (backend/orchestrator) or Vercel (frontend dashboard).

## Infrastructure

| Component | Location | Details |
|-----------|----------|---------|
| Backend/Orchestrator | `88.99.64.19` (aka `cloud.vrbot.me`) | Port 8889, path `/root/vrbot-distributed/` |
| Frontend Dashboard | Vercel | Auto-deploys from `main` branch |
| Cron Jobs | Vercel | `/api/cron/run-tasks` fires 4x daily |
| Payment | PayPal only | No Stripe integration |

## Pre-Deploy Checks

1. **All tests pass locally**
   ```bash
   python -m pytest tests/ -v
   ```

2. **No hardcoded local IPs**
   ```bash
   grep -rn "192\.168\." tasks/ core/ --include="*.py"
   # Must return nothing
   ```

3. **Task files valid** (pre-commit hook checks this automatically)

4. **Branch is NOT main** — create a feature/fix branch, PR, then merge:
   ```bash
   git checkout -b fix/description
   # ... make changes ...
   git push -u origin fix/description
   gh pr create --title "Fix: description"
   ```

## Deploy Backend (Hetzner)

```bash
# 1. SSH into server
ssh root@88.99.64.19

# 2. Pull latest code
cd /root/vrbot-distributed/
git pull origin main

# 3. Install any new dependencies
pip install -r requirements.txt

# 4. Restart orchestrator
systemctl restart vrbot-orchestrator
# OR if using Docker:
docker-compose down && docker-compose up -d

# 5. Verify orchestrator is running
curl -s http://localhost:8889/api/health

# 6. Verify all 20 farms are active
curl -s http://localhost:8889/api/farms | python -m json.tool | grep -c '"status": "active"'
# Expected: 20
```

## Deploy Frontend (Vercel)

Frontend auto-deploys when PRs merge to `main`. To manually trigger:
```bash
vercel --prod
```

## Post-Deploy Verification

```bash
# Check orchestrator health
curl -s http://cloud.vrbot.me:8889/api/health

# Verify farm count
curl -s http://cloud.vrbot.me:8889/api/farms | python -c "
import sys, json
farms = json.load(sys.stdin)
active = [f for f in farms if f.get('status') == 'active']
print(f'{len(active)}/20 farms active')
assert len(active) >= 18, 'ALERT: Too few active farms!'
"

# Tail logs for errors
ssh root@88.99.64.19 "journalctl -u vrbot-orchestrator --since '5 min ago' --no-pager"
```

## Known Pitfalls

- **Never push directly to `main`**: Always use feature branches + PRs. Vercel auto-deploys from main, so a broken push immediately breaks the dashboard.
- **`HETZNER_IP` = `cloud.vrbot.me`**: Use the DNS name in configs/docs; use the raw IP `88.99.64.19` only for SSH. The DNS name is what the frontend and farms resolve.
- **PayPal only**: The billing system uses PayPal exclusively. No Stripe, no crypto. Don't add alternative payment integrations without explicit approval.
- **Vercel cron at `/api/cron/run-tasks` fires 4x daily**: This endpoint triggers scheduled task dispatching. Don't rename or move it — Vercel cron config depends on the exact path.
- **Port 8889, not 8888**: The v2 distributed orchestrator runs on 8889. Port 8888 was the legacy single-node bot and is no longer active.
