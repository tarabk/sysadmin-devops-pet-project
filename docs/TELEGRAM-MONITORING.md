# Telegram monitoring

Menus and alerts for the existing Taskboard monitoring stack on `vm-lab`.
The bot reads Prometheus and has no Docker socket or host filesystem access.
It uses the existing Telegram bot token. Alertmanager sends alerts; the new
`telegram-bot` container handles menu buttons through long polling.

## Menu

- **VM:** CPU Usage, Memory, Disk, Inodes.
- **Containers:** Application or Monitoring, then a service, then CPU Usage,
  Memory or Status. All currently expected services remain selectable when absent.
- **Website:** DNS, HTTPS, Backend / API, Response Time, TLS Certificate.
- **Navigation:** Refresh, Back, Main Menu.
- `/start`, `/menu` and `/status` open the main menu.

Buttons edit the existing message. The private chat ID and sender ID must both
match `allowed_chat_id`. Missing, stale, non-finite or ambiguous values show
`No data`, never zero. Requests use a fixed list of queries and service names.
The UI shows request time in UTC. Prometheus normally refreshes metrics every
30 seconds; Refresh queries the latest stored samples, not a forced scrape.

Container Status means presence observed by cAdvisor. It is not a Docker
healthcheck or proof that the application is ready. Backend readiness and API
checks are available in Website. CPU and memory are aggregated by Compose
service; the current deployment has one container per service.

## Alert policy

| Metric | Condition | Duration |
|---|---|---|
| VM CPU | Usage >95% | 5 minutes |
| VM memory | Available memory <5% | 5 minutes |
| Root filesystem | Available space <5% | 5 minutes |
| Root filesystem inodes | Free inodes <5% | 5 minutes |
| Container CPU | Usage >95% of positive exported CPU quota | 5 minutes |
| Container memory | Working set >95% of positive exported memory limit | 5 minutes |
| Expected container | Absent or not recently observed by cAdvisor | 5 minutes |
| DNS, homepage, API, readiness | Probe fails | 5 minutes |
| Successful HTTP probe duration | >3 seconds | 5 minutes |
| TLS certificate | <=7 days remaining | Next rule evaluation |

Exactly 95% does not fire a resource alert. CPU is a one-minute rate evaluated
every 30 seconds. `for: 5m` applies to successive evaluations, so a notification
also includes scrape, evaluation and Alertmanager grouping delays. The existing
Alertmanager route waits 30 seconds, repeats ongoing alerts every four hours,
and sends resolved notifications.

Container CPU percentage uses `quota / period` as the allocated number of cores.
For example, 0.48 cores out of a 0.5-core limit is 96%. Memory uses cAdvisor's
working set, not a guarantee about when the kernel will trigger an OOM kill.
A missing or zero resource limit yields no percentage. Verify exported limits
before treating every resource alert as operational.

The rules cover the root XFS filesystem already monitored by this project.
Inode counts on XFS can change as the filesystem allocates inodes.
No backup-age or standalone exporter-loss alerts are added. A missing exporter
shows unavailable data in the menu. Presence alerts are suppressed when cAdvisor
cannot be scraped, so they do not mislabel all services as stopped.

## Probe scope

- DNS requests an A record through Azure's resolver at `168.63.129.16:53`.
  At least one IPv4 answer is required; this does not validate a fixed expected IP.
- Homepage: `https://127.0.0.1/`.
- API: `https://127.0.0.1/api/tasks`.
- Readiness: `http://127.0.0.1:18000/ready`.
- HTTPS retains the domain Host header, TLS SNI and certificate validation.

The HTTPS probes run inside the VM. They do not prove public reachability through
Azure NSG. The bot and Alertmanager also run on this VM and cannot report a total
VM or Internet outage while they are offline. External reachability monitoring
requires a separate observer and an explicitly permitted source IP.

## Files

| File | Purpose |
|---|---|
| `compose.telegram.yaml` | Overlay for the existing monitoring Compose project |
| `deploy/telegram-bot/bot.py` | Telegram menus and read-only Prometheus queries |
| `deploy/telegram-bot/Dockerfile` | Non-root Python container, no pip dependencies |
| `deploy/telegram-bot/config.example.json` | Example only; the real settings stay under `/etc` |
| `deploy/monitoring/telegram-prometheus.yml` | Existing jobs, new probes, recording rules and alerts |
| `deploy/monitoring/telegram-blackbox.yml` | Existing HTTP modules plus DNS |
| `deploy/monitoring/telegram-rules.yml` | Recording and alert rules |
| `tests/test_telegram_menu.py` | Offline menu, permission and data handling tests |
| `tests/telegram-rules.test.yml` | Prometheus rule tests |

The overlay mounts `telegram-prometheus.yml` and `telegram-blackbox.yml` in
place of the base configuration files. Edit these active files when changing
checks. Keep additional jobs in `telegram-prometheus.yml`; changes made only
to the base `prometheus.yml` will not affect the running overlay deployment.

## 1. Prepare the VM

Run from the existing repository:

```bash
cd /home/azureuser/sysadmin-devops-pet-project
```

Create `/etc/taskboard-monitoring/telegram-bot.json` if it has not been created.
Replace the example ID with the same positive private `chat_id` used by
Alertmanager. Keep the token in the existing `telg-bot` file.

```json
{
  "allowed_chat_id": 123456789,
  "prometheus_url": "http://127.0.0.1:9090",
  "token_file": "/run/secrets/telegram-bot-token"
}
```

```bash
sudo chown root:65534 /etc/taskboard-monitoring/telegram-bot.json
sudo chmod 0640 /etc/taskboard-monitoring/telegram-bot.json
```

The existing token file must also be `root:65534` with mode `0640`, as configured
for Alertmanager. Both services use UID/GID 65534. The parent directory can remain
root-owned with mode `0700`: Docker performs the individual bind mounts.

## 2. Validate before applying

The overlay must always be supplied after the base file:

```bash
sudo docker compose \
  -f compose.monitoring.yaml -f compose.telegram.yaml config -q
```

Inspect the merged configuration locally. Check that Prometheus still has
`prometheus_data`, Alertmanager still has its configuration and data volume,
and Grafana retains the 1 GiB memory and 1 CPU limits.

```bash
sudo docker compose \
  -f compose.monitoring.yaml -f compose.telegram.yaml config
```

The merged configuration may include the Grafana administrator password resolved
from its environment file. Review it locally; do not post or commit that output.

Validate Prometheus and every rule:

```bash
sudo docker compose \
  -f compose.monitoring.yaml -f compose.telegram.yaml \
  run --rm --no-deps --entrypoint /bin/promtool \
  prometheus check config /etc/prometheus/prometheus.yml
```

Run the rule scenarios without sending alerts:

```bash
sudo docker compose \
  -f compose.monitoring.yaml -f compose.telegram.yaml \
  run --rm --no-deps --entrypoint /bin/promtool \
  -v "$PWD/tests:/work/tests:ro,z" \
  -v "$PWD/deploy/monitoring:/work/deploy/monitoring:ro,z" \
  -w /work \
  prometheus test rules tests/telegram-rules.test.yml
```

The test-only directory mounts use a shared SELinux label. Normal service mounts
are relabeled when the containers below are recreated. Stop here if validation
fails; keep the diagnostic output.

## 3. Build and apply

```bash
sudo docker compose \
  -f compose.monitoring.yaml -f compose.telegram.yaml \
  build telegram-bot
```

Apply the configurations and shared token label:

```bash
sudo docker compose \
  -f compose.monitoring.yaml -f compose.telegram.yaml \
  up -d --no-deps --force-recreate blackbox prometheus alertmanager telegram-bot
```

The token bind mount uses lowercase `z` in both Alertmanager and the bot because
they share the file under SELinux. Other private mounts retain uppercase `Z`.
No public listening port is added for the bot. It uses outbound HTTPS polling.
Only one process may poll this Telegram bot token. Alertmanager's outgoing
messages can use the same token. If a webhook exists, the bot stops and logs
that fact without deleting the webhook.

After startup, use both Compose files for monitoring changes. Running the base
file alone can restore the previous configuration or private token label.

## 4. Check startup and metrics

```bash
sudo docker compose \
  -f compose.monitoring.yaml -f compose.telegram.yaml ps
```

```bash
sudo docker compose \
  -f compose.monitoring.yaml -f compose.telegram.yaml \
  logs --tail 50 telegram-bot prometheus blackbox
```

Wait for two or three 30-second scrapes before checking CPU rates.

```bash
curl -fsS --max-time 10 --get \
  --data-urlencode 'query=probe_success{job=~"taskboard_.*"}' \
  http://127.0.0.1:9090/api/v1/query
```

Expect four successful series: `taskboard_dns`, `taskboard_home`,
`taskboard_https`, `taskboard_ready`.

```bash
curl -fsS --max-time 10 --get \
  --data-urlencode 'query=taskboard:container_cpu_limit:cores' \
  http://127.0.0.1:9090/api/v1/query
```

Verify every expected running service has a positive CPU limit. Also query
`taskboard:container_memory_limit:bytes`. If a limit is missing, inspect the
cAdvisor `container_spec_cpu_quota`, `container_spec_cpu_period` and
`container_spec_memory_limit_bytes` series before changing the alert formulas.

Open `/menu` in your private chat after the service starts. Startup skips old
queued commands. Check every section, Refresh and Back. Unavailable data should
be shown as unavailable. Alert rules and their current states are visible at:

```bash
curl -fsS --max-time 10 \
  'http://127.0.0.1:9090/api/v1/rules?type=alert'
```

An end-to-end test on the VM confirmed both `firing` and `resolved` messages
from Prometheus through Alertmanager. The temporary, time-limited test rule was
removed, the original 36 rules restored and Prometheus recreated.
For future delivery checks, use a temporary synthetic alert and remove it before
committing. Threshold unit tests run without loading the VM or sending Telegram messages.

## 5. Version control after validation

The code, overlay, rules and documentation contain no runtime token or chat ID.
Use the project's existing VM-to-WSL Git workflow to publish the commit.

```bash
git diff --check
git status --short
git add compose.telegram.yaml deploy/telegram-bot \
  deploy/monitoring/telegram-prometheus.yml \
  deploy/monitoring/telegram-blackbox.yml \
  deploy/monitoring/telegram-rules.yml \
  tests/test_telegram_menu.py tests/telegram-rules.test.yml \
  docs/TELEGRAM-MONITORING.md
git diff --staged
git commit -m "feat: add Telegram monitoring menus and threshold alerts"
```

## Roll back this addition

Stop the menu handler, then recreate the three modified services from the
original Compose file. Monitoring history remains in its named volumes.

```bash
sudo docker compose \
  -f compose.monitoring.yaml -f compose.telegram.yaml stop telegram-bot
sudo docker compose -f compose.monitoring.yaml \
  up -d --no-deps --force-recreate blackbox prometheus alertmanager
```
The Grafana dashboard is stored in `grafana_data`. The repository does not
currently contain an exported dashboard JSON or Grafana provisioning files.
Retain that volume or export the dashboard before rebuilding Grafana elsewhere.
Do not use `down -v` to roll back this configuration.

## Verification

- 18 Python unittest checks passed: menu navigation, callback sizes, access
  restrictions, stale/missing values, unavailable Prometheus and configuration.
- Prometheus 3.15.0 `promtool check rules`: all 36 recording/alert rules valid.
- Five `promtool test rules` scenarios passed: sustained VM CPU, the exact
  95% boundary, container CPU quota normalization, sustained HTTP failure,
  and the seven-day certificate boundary.
- Image built and merged Compose configuration validated on the VM.
- VM/container metric views, DNS and HTTP checks, and Telegram navigation verified.
- End-to-end firing and resolved notifications received; temporary rule removed.

## References

- Telegram Bot API: https://core.telegram.org/bots/api
- Prometheus alerting: https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/
- Prometheus queries: https://prometheus.io/docs/prometheus/latest/querying/api/
- cAdvisor metrics: https://github.com/google/cadvisor/blob/master/docs/storage/prometheus.md
- Blackbox configuration: https://github.com/prometheus/blackbox_exporter/blob/master/CONFIGURATION.md
- Azure DNS platform IP: https://learn.microsoft.com/en-us/azure/virtual-network/what-is-ip-address-168-63-129-16
