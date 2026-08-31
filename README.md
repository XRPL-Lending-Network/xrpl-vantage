# xrpl-vantage

A Prometheus exporter, a Grafana dashboard and a set of alert rules for
running an XRP Ledger node, built around one question the existing tools do
not answer: **what does this node see of the network, and where does it stand
in it?**

There are already good exporters for what happens inside a node: cache hit
rates, job queues, database internals. This is not another one of those. What
it collects instead:

- **which versions the peers run**, which is how you tell whether a fix you
  are waiting on has actually reached the network
- **which peer is using the bandwidth**, by name, because the node keeps byte
  counters per connection and nobody reads them
- **how long the trusted validator list stays valid**, a deadline that arrives
  on its own and is not warned about anywhere else
- **which amendments are heading for activation and whether this binary can
  apply them**, so an upcoming block is two weeks of notice rather than a
  surprise
- **whether the public validator registry can still see this validator**,
  which for about a third of the registry it currently cannot

Only the standard library. That is deliberate: this is meant to run on the
same machine as a validator, and a dependency tree there is a harder sell than
the metrics are worth.

## Install

```bash
install -m 0755 exporter/xrpl_vantage.py /usr/local/bin/xrpl-vantage
install -m 0644 exporter/xrpl-vantage.service /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now xrpl-vantage
curl -s localhost:9101/metrics | head
```

It talks to the node's admin RPC on loopback and listens on loopback. Reach it
from your collector over a private network or a tunnel; do not move it to
`0.0.0.0` to save yourself the trouble. There is nothing secret in the metrics,
but the machine they come from usually is.

Scrape config in `examples/scrape.yml`. Dashboard in `dashboards/`, import it
as JSON. Rules in `rules/`.

## Configuration

Everything is an environment variable, all optional.

| Variable | Default | What it does |
|---|---|---|
| `XRPL_RPC_URL` | `http://127.0.0.1:5005/` | The node's admin RPC |
| `XRPL_LISTEN_ADDR` | `127.0.0.1` | Where to serve metrics |
| `XRPL_LISTEN_PORT` | `9101` | |
| `XRPL_INTERVAL_FAST` | `15` | `server_info`, peers, consensus |
| `XRPL_INTERVAL_SLOW` | `60` | Trusted lists, amendments |
| `XRPL_INTERVAL_REGISTRY` | `300` | The one outbound call |
| `XRPL_REGISTRY` | `1` | Set to `0` on a machine with no internet |
| `XRPL_MASTER_KEY` | node's own | Watch another validator's registry record from here |
| `XRPL_PEER_TOP_N` | `10` | How many peers get their own byte counters |
| `XRPL_AMENDMENT_LABELS` | `pending` | `all` to label every amendment |

Collectors run independently on their own schedules. One failing RPC leaves
the rest working, and `xrpl_collector_failed` says which section went stale.

## The two rule files

They are separate on purpose.

**`rules/node-exporter.yml`** holds 20 rules that need plain `node_exporter`
and nothing else. Disk, memory, RAID, clock, load, traffic. Useful on any Linux
box; they are here because they were tuned on nodes.

**`rules/xrpl-vantage.yml`** holds 22 rules on the metrics from this exporter.
Trusted list expiry, amendment blocking ahead of time, registry visibility,
manifest sequence regression, peer traffic concentration, consensus minority.

Both were checked against a live time series database, so the expressions
parse. Two thresholds are marked `SITE` and want changing before you use them.

## Read this before you trust the thresholds

`docs/FALSE-POSITIVES.md` is the most useful file in the repository. Most of
these rules were wrong when first written and fired on healthy machines, and
the document says which, why, and what replaced them. Short version of what it
adds up to: alert on a resource running out or a thing failing, never on a
state the system passes through normally.

Two of the cases are worth knowing even if you never use these rules:

A monthly RAID integrity check clears the `active` flag on
`node_md_state`, so the obvious rule fires three criticals at once on a host
where nothing is wrong.

A large clock jump does not show up in `node_timex_offset_seconds` at all.
While the correction is being slewed, the offset the kernel reports stays at
zero. We watched it read a flat zero with the clock 19,422 seconds out. Only
`node_timex_sync_status` told the truth.

## The registry section, and why it exists

A validator's record in the public registry can lose the link to its master
key while the validator itself keeps working perfectly. Lookups by master key
then fail, explorers show the validator as missing, and the operator has no
way to notice.

This is not rare. At the time of writing, 93 of the 289 validators in the
public registry have a null master key, and 56 of those still have a domain
attached, which can only have come from a manifest that was ingested
correctly.

It also flickers rather than staying broken, because the linkage is written by
two paths that race. On the validator this was developed against, six
consecutive samples came back three good and three bad. That is why
`xrpl_registry_listed` and `xrpl_registry_master_key_present` are separate
metrics, and why the alert on the second one waits six hours.

```
xrpl_registry_listed              1     the record is there
xrpl_registry_master_key_present  0     and the link to the master key is gone
xrpl_registry_domain_present      1
xrpl_registry_agreement_score     0.99456
```

The exporter matches its own record by signing key as well as master key,
because when the linkage breaks the registry stops keying the record by the
master key too. Matching only on the master key reports "not listed" for a
validator that is listed and validating fine.

## Cardinality

Three metrics carry labels that could grow without bound, and all three are
capped. Per-peer byte counters cover only the heaviest ten, with the rest
folded into `peer="other"` so totals still add up. Amendment labels cover only
amendments that have not activated yet. Peer version labels are bounded in
practice but come from a string peers control. Details and the environment
variables to change it are in `docs/METRICS.md`.

## Compatibility

Written against xrpld 3.3.0 and tested on mainnet. The metric namespace is
`xrpl_`, which does not collide with the `rippled_` namespace another exporter
uses, so the two can run side by side and probably should. This one covers
the network view, that one covers node internals.

## Documentation

- `docs/METRICS.md`, every metric, generated from real output rather than
  written from memory
- `docs/FALSE-POSITIVES.md`, the rules that were wrong and what replaced them

## Licence

MIT.
