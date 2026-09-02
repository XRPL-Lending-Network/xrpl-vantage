<!--
Please describe the change and why it is needed. If it is a new alert rule or
a change to a threshold, say what it fired on and what it should fire on.
-->

## What this changes

<!-- A summary. This may go straight into the release notes. -->

## Why

<!--
For a fix: what was the wrong behaviour, and when was it introduced?
For a new metric or rule: what question does it answer that nothing else does?
For a threshold change: what fired that should not have, or what did not fire
that should have?
-->

## Impact on existing installations

<!-- Check what applies, delete the rest. -->

- [ ] Adds a metric or label (safe: existing dashboards and alerts keep working)
- [ ] **Renames or removes a metric or label** (breaking: dashboards go empty
      and alerts stop firing without any error)
- [ ] Changes an alert threshold or `for:` duration
- [ ] Changes the dashboard
- [ ] Changes a default in the exporter or the unit file

## How it was tested

<!--
Which node did this run against — stock or validator, which xrpld version?
If you could not run it, say so; that is fine, it just needs another pair of
hands.
-->

## Checklist

- [ ] `pre-commit run --all-files` passes
- [ ] `promtool check rules rules/*.yml` passes, if rules changed
- [ ] `docs/METRICS.md` updated, if metrics changed
- [ ] Commits are signed
