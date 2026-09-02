---
name: Bug report
about: Something does not work, or an alert fired when it should not have
title: ''
labels: bug
assignees: ''
---

**What happened**

<!-- If an alert fired, name the rule and paste what the expression evaluated to. -->

**What you expected instead**

**Environment**

- xrpld version:
- Node role: <!-- stock / validator -->
- Exporter version or commit:
- Prometheus or VictoriaMetrics version:
- OS:

**Metric output**

<!--
The relevant lines from `curl -s localhost:9101/metrics`. Please redact
addresses and hostnames — validator public keys are public and can stay.
-->

```
```

**Anything in the exporter's log**

```
journalctl -u xrpl-vantage -n 50
```
