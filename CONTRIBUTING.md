# Contributing

Bug reports and patches are welcome. This file covers the things that are
specific to this repository; general GitHub practice is assumed.

## Before you start

Work happens on `main`. Open a pull request from a fork.

Please open a **draft** pull request as soon as you have something to show,
rather than waiting until it is finished. Alert thresholds and metric names
are much cheaper to argue about before the work is done.

## The one hard rule: no dependencies

The exporter uses the Python standard library and nothing else. It is meant to
run on the same machine as a validator, and a dependency tree there is a
harder sell than any metric is worth.

A patch that adds a third-party import will not be merged, however convenient
the library is. If something genuinely cannot be done without one, open an
issue first and make the case.

## Changing metrics and alerts

Metric names are a public interface. People build dashboards and alerts on
them, and a rename breaks both silently — nothing errors, the panel just goes
empty.

- Adding a metric or a label is fine.
- Renaming or removing one is a breaking change. Say so in the pull request
  description, and update `docs/METRICS.md`, `dashboards/` and `rules/` in the
  same change.
- New labels must be bounded. Anything derived from a peer, a version string
  or an amendment name needs an explicit cap; see the cardinality notes in
  `docs/METRICS.md`.

New alert rules need a comment explaining what the threshold means, and a
`for:` clause unless the condition is already a failure the moment it becomes
true — a read-only filesystem, an expired trusted list, an amendment-blocked
node. Four of the existing rules are in that category; everything else waits. If a rule fired on a healthy machine before you fixed it,
that story belongs in `docs/FALSE-POSITIVES.md` — those write-ups are more
useful than the rules themselves.

## Before making a pull request

Install the hooks once:

```bash
pip install pre-commit
pre-commit install
```

They run automatically on every commit, and on demand:

```bash
pre-commit run --all-files
```

Hook versions are pinned by commit hash, so a local run uses exactly the same
tool versions as CI and there are no surprises after you push.

Rule files are checked with `promtool`, which parses every expression:

```bash
promtool check rules rules/*.yml
```

An expression that fails to parse is not an error at runtime — Prometheus
simply ignores the file, and the alerts you think you have do not exist.

## Pull requests

Start the title with one of these:

- `feat:` — new metric, rule, panel or capability
- `fix:` — corrects existing behaviour
- `docs:` — documentation only
- `ci:` — CI configuration and workflows
- `refactor:` — no behaviour change
- `chore:` — everything else that does not affect what the exporter emits

Capitalise the first word after the colon, and do not end the subject with a
period: `feat: Add peer isolation metrics`.

Once a pull request is marked ready for review, add changes as new commits.
Please do not force-push — it throws away the reviewer's ability to see what
changed since their last look. Merging `main` into your branch is fine.

Commits should be signed. GitHub's guide to [commit signature verification][s]
covers the setup.

## Testing against a real node

Most of this cannot be tested without a node to talk to. A stock `xrpld` in
tracking mode is enough for everything except the consensus and registry
sections, which need a configured validator key.

If you have neither, say so in the pull request — a change that has only been
reasoned about is still worth reviewing, it just needs someone else to run it.

## Scope

This exporter covers what a node sees of the network: peers, versions,
trusted lists, amendments, registry visibility. Node internals — cache hit
rates, job queues, database counters — are deliberately out of scope and
already covered by other exporters. The two are meant to run side by side.

[s]: https://docs.github.com/en/authentication/managing-commit-signature-verification
