# Security Policy

## Reporting a vulnerability

Please do not open a public issue for a security problem.

Use GitHub's [private vulnerability reporting][pvr] on this repository. We aim
to acknowledge a report within 72 hours.

When you report, **do not include real infrastructure details**: validator
master keys are public and fine, but node addresses, admin RPC endpoints,
hostnames and configuration files are not. A redacted reproduction is more
useful than a real one.

## Not in scope

Vulnerabilities in the XRP Ledger itself — `xrpld`, `clio`, the client
libraries — belong to the XRP Ledger Foundation's process, not here. See
[rippled's security policy][xrplf].

## Threat model

Worth stating plainly, because it shapes what counts as a vulnerability here:

- The exporter **binds to loopback by default and has no authentication**.
  That is intentional. Reach it from a collector over a private network or a
  tunnel. Exposing it on `0.0.0.0` is a deployment mistake, not a bug in the
  exporter.
- It talks to the node's **admin RPC**, which is privileged. Anything that
  lets metric output or a peer-controlled string influence what is sent to
  that endpoint is a real vulnerability and we want to hear about it.
- One collector makes an **outbound HTTPS call** to a public registry API. It
  can be turned off with `XRPL_REGISTRY=0`; the rest keeps working.
- Metrics carry strings that peers control, most visibly advertised version
  numbers. They are exposed as label values. Anything that escapes the metric
  format through those strings is a vulnerability.

[pvr]: https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability
[xrplf]: https://github.com/XRPLF/rippled/blob/develop/SECURITY.md
