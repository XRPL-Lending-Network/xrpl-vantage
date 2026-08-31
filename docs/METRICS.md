# Metrics

Generated from the exporter's own output against a mainnet validator and a
stock node, so everything listed here is a metric that actually appeared,
not one that was meant to.

Two sections only appear on a validator: Consensus, which needs the node to
be taking part, and Manifest and registry, which needs a validator key to
look up. On a stock node those metrics are simply absent, which is why some
dashboard panels stay empty until you point it at a validator.

A few metrics in Node basics are conditional on the node reporting the
underlying field at all, so they come and go: `xrpl_fetch_pack` and the two
peer disconnect counters are the usual ones.

## Node basics

Standard things, here so you do not need a second exporter for them.

| Metric | Type | Labels | Meaning |
|---|---|---|---|
| `xrpl_up` | gauge | — | 1 when the node answered admin RPC |
| `xrpl_server_state` | gauge | `state` | Node state as a number, ordered by progress towards validating |
| `xrpl_server_ready` | gauge | — | 1 when the node is caught up enough to answer for the network |
| `xrpl_validated_ledger_seq` | counter | — | Sequence of the last validated ledger |
| `xrpl_validated_ledger_age_seconds` | gauge | — | How far behind the network the last validated ledger is |
| `xrpl_complete_ledgers` | gauge | — | Number of ledgers held on disk |
| `xrpl_uptime_seconds` | counter | — | Process uptime |
| `xrpl_build_info` | gauge | `network_id`, `version` | Node version, carried in the label |
| `xrpl_load_factor` | gauge | — | Current load factor |
| `xrpl_io_latency_ms` | gauge | — | Job queue IO latency |
| `xrpl_amendment_blocked` | gauge | — | 1 when the node refuses to work because it does not know an amendment the network enabled |
| `xrpl_validator_configured` | gauge | — | 1 when this node is configured to validate |
| `xrpl_validation_quorum` | gauge | — | Validations required to declare a ledger validated |
| `xrpl_collector_failed` | gauge | `section` | 1 when a collector's last run raised |

## Peers

What the node can see of the network through the connections it holds.

| Metric | Type | Labels | Meaning |
|---|---|---|---|
| `xrpl_peers_total` | gauge | — | Peers currently connected |
| `xrpl_peers_inbound` | gauge | — | Peers that connected to us |
| `xrpl_peers_outbound` | gauge | — | Peers we connected to |
| `xrpl_peers_cluster` | gauge | — | Peers recognised as our own cluster |
| `xrpl_peer_versions` | gauge | `version` | Connected peers per advertised version |
| `xrpl_peers_wrong_network` | gauge | — | Peers reporting a network id different from the majority |
| `xrpl_peer_latency_seconds` | gauge | `quantile` | Round trip time to peers |
| `xrpl_peer_bytes_sent` | counter | `peer` | Bytes sent to one peer, heaviest peers only |
| `xrpl_peer_bytes_recv` | counter | `peer` | Bytes received from one peer, heaviest peers only |
| `xrpl_peer_bytes_sent_total` | counter | — | Bytes sent to peers since the node started, all peers |
| `xrpl_peer_traffic_top_share` | gauge | — | Share of outbound bytes taken by the heaviest peers |

## Trusted list

The list has an expiry date and a refresh that can quietly stop working.

| Metric | Type | Labels | Meaning |
|---|---|---|---|
| `xrpl_trusted_validators` | gauge | — | Validators currently trusted, from all publisher lists combined |
| `xrpl_validation_quorum_configured` | gauge | — | Quorum the node is working with |
| `xrpl_unl_available` | gauge | `publisher` | 1 when the node holds a usable list from this publisher |
| `xrpl_unl_seq` | gauge | `publisher` | Sequence number of the list currently held |
| `xrpl_unl_expires_seconds` | gauge | `publisher` | Seconds until the trusted list from this publisher expires |
| `xrpl_unl_refresh_ok` | gauge | `site`, `status` | 1 when the last list refresh from this site worked |
| `xrpl_unl_refresh_age_seconds` | gauge | `site` | Time since this site was last refreshed |

## Amendments

Which are on, which are coming, and whether this binary can take them.

| Metric | Type | Labels | Meaning |
|---|---|---|---|
| `xrpl_amendments_total` | gauge | — | Amendments the node knows of |
| `xrpl_amendments_enabled_total` | gauge | — | Amendments switched on |
| `xrpl_amendments_unsupported_total` | gauge | — | Amendments this binary does not know how to apply |
| `xrpl_amendment_supported` | gauge | `name` | 1 when this binary knows how to apply the amendment |
| `xrpl_amendment_vetoed` | gauge | `name` | 1 when this node votes against the amendment |
| `xrpl_amendments_in_majority` | gauge | — | Amendments currently holding a majority |
| `xrpl_amendment_majority_seconds` | gauge | `name` | How long this amendment has held a majority |
| `xrpl_amendment_eta_seconds` | gauge | `name` | Estimated seconds until this amendment activates |
| `xrpl_amendments_unsupported_majority` | gauge | — | Amendments heading for activation that this binary cannot apply |

## Consensus

Validator only. The interesting part is which side of a disagreement you are on.

| Metric | Type | Labels | Meaning |
|---|---|---|---|
| `xrpl_consensus_phase` | gauge | `phase` | Consensus phase as a number |
| `xrpl_consensus_proposing` | gauge | — | 1 when this node is putting forward its own position |
| `xrpl_consensus_validating` | gauge | — | 1 when this node is signing validations |
| `xrpl_consensus_synched` | gauge | — | 1 when this node agrees with the network on the previous ledger |
| `xrpl_consensus_proposers` | gauge | — | From consensus_info: proposers |
| `xrpl_consensus_previous_proposers` | gauge | — | From consensus_info: previous_proposers |
| `xrpl_consensus_converge_percent` | gauge | — | From consensus_info: converge_percent |
| `xrpl_consensus_previous_ms` | gauge | — | From consensus_info: previous_mseconds |
| `xrpl_consensus_disputes` | gauge | — | Transactions this node and its peers disagree about right now |
| `xrpl_consensus_disputes_minority` | gauge | — | Disputes where this node is voting against the majority of peers |

## Manifest and registry

Whether the rest of the world can see this validator at all. One outbound HTTPS call every five minutes; set XRPL_REGISTRY=0 to turn it off.

| Metric | Type | Labels | Meaning |
|---|---|---|---|
| `xrpl_manifest_seq` | gauge | — | Sequence of the manifest this validator is publishing |
| `xrpl_manifest_domain_set` | gauge | — | 1 when the manifest carries a domain |
| `xrpl_registry_up` | gauge | — | 1 when the registry answered at all |
| `xrpl_registry_lookup_code` | gauge | — | HTTP status from the last registry poll, 0 when it did not answer |
| `xrpl_registry_listed` | gauge | — | 1 when the registry has a record for this validator |
| `xrpl_registry_master_key_present` | gauge | — | 1 when the registry record still carries the master key |
| `xrpl_registry_domain_present` | gauge | — | 1 when the registry record carries a domain |
| `xrpl_registry_unl_listed` | gauge | — | 1 when this validator is on a published UNL |
| `xrpl_registry_agreement_score` | gauge | — | Agreement score over 30 days as the registry computes it |

## Cardinality

Three metrics carry labels that could grow without bound, and all three are
capped on purpose.

`xrpl_peer_bytes_sent` and `xrpl_peer_bytes_recv` are labelled by peer
public key. Peers churn, and every key that ever connects would otherwise
become a series forever. Only the heaviest ten are labelled; everything else
is folded into a single `peer="other"` bucket, so the totals still add up.
Raise the cap with `XRPL_PEER_TOP_N` if you want more, but understand what
you are buying.

`xrpl_amendment_*` is labelled by amendment name, and by default only
amendments that have not activated yet get a series. That is usually a dozen
out of a hundred or so. Enabled amendments never change again, and the count
in `xrpl_amendments_enabled_total` says the same thing for less. A side
effect worth knowing: when an amendment activates, its series stops being
reported. Set `XRPL_AMENDMENT_LABELS=all` if you would rather have all of
them.

`xrpl_peer_versions` is labelled by the version string peers advertise.
Bounded in practice, but it is a string peers control, so it can contain
anything they put there. Real examples seen on mainnet include
`xrpld-3.3.0-DJS` and `xrpl-rust-validator/0.1.0`.

## A gotcha worth repeating

rippled is inconsistent about numbers in JSON. The byte counters under a
peer's `metrics` come back as strings, while `latency` right next to them is
an integer:

```json
{"latency": 113, "metrics": {"total_bytes_sent": "145199241"}}
```

An `isinstance` check against `int` and `float` therefore drops the whole
traffic section without an error anywhere. The metric simply never appears.
This cost an hour here; it may save you one.
