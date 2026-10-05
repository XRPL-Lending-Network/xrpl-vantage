# Metrics

Generated from the exporter's own output against a mainnet validator and a
stock node, and checked against the exporter code for the metrics that only
appear under certain conditions. Where a metric is conditional, the Meaning
column says when it appears.

Consensus only appears on a validator, because it needs the node to be
taking part. Manifest and registry needs a validator master key to look up.
On a validator the exporter takes it from `pubkey_validator` in
`server_info`. On a stock node, set `XRPL_MASTER_KEY` to the master key of
the validator you want to watch and the section works there as well.
Without either, those metrics are simply absent, which is why some
dashboard panels stay empty on a stock node.

A few metrics come and go because the underlying field is not always there.
`xrpl_fetch_pack` is the usual one in Node basics. The two traffic share
metrics in Peers depend on how many peers the node has.

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
| `xrpl_fetch_pack` | gauge | — | Number of entries in the fetch pack cache. Only when `server_info` reports `fetch_pack`, which the node does only while the cache is not empty |
| `xrpl_peer_disconnects_total` | counter | — | Peer disconnects since start. Only when `server_info` has a `counters` object containing `peer_disconnects`; see the note below the table |
| `xrpl_peer_disconnects_resources_total` | counter | — | Peer disconnects caused by resource limits. Only when the `counters` object contains `peer_disconnects_resources` |
| `xrpl_amendment_blocked` | gauge | — | 1 when the node refuses to work because it does not know an amendment the network enabled |
| `xrpl_validator_configured` | gauge | — | 1 when this node is configured to validate |
| `xrpl_validation_quorum` | gauge | — | Validations required to declare a ledger validated |
| `xrpl_collector_failed` | gauge | `section` | 1 when a collector's last run raised |

The exporter reads both disconnect counters from a `counters` object in
`server_info`. xrpld puts `peer_disconnects` and
`peer_disconnects_resources` at the top level of `server_info`, as strings,
and only adds a `counters` object when it is asked for, which the exporter
does not do. Against a current xrpld these two metrics therefore do not
appear.

## Peers

What the node can see of the network through the connections it holds.

| Metric | Type | Labels | Meaning |
|---|---|---|---|
| `xrpl_peers_total` | gauge | — | Peers currently connected |
| `xrpl_peers_inbound` | gauge | — | Peers that connected to us |
| `xrpl_peers_outbound` | gauge | — | Peers we connected to |
| `xrpl_peers_cluster` | gauge | — | Peers recognised as our own cluster |
| `xrpl_peers_private` | gauge | — | Peers whose address is in a private, loopback or link-local range |
| `xrpl_peers_public` | gauge | — | Peers outside those ranges. On a validator that sits behind its own stock nodes this should be zero |
| `xrpl_peer_versions` | gauge | `version` | Connected peers per advertised version |
| `xrpl_peers_wrong_network` | gauge | — | Peers reporting a network id different from the majority |
| `xrpl_peer_latency_seconds` | gauge | `quantile` | Round trip time to peers |
| `xrpl_peer_bytes_sent` | counter | `peer` | Bytes sent to one peer, heaviest peers only |
| `xrpl_peer_bytes_recv` | counter | `peer` | Bytes received from one peer, heaviest peers only |
| `xrpl_peer_bytes_sent_total` | counter | — | Bytes sent to peers since the node started, all peers |
| `xrpl_peer_top_n` | gauge | — | How many peers get their own byte counters: the configured `XRPL_PEER_TOP_N`, 10 by default. A setting, not a count of connected peers |
| `xrpl_peer_traffic_top_share` | gauge | — | Share of outbound bytes taken by the heaviest peers. Only when some bytes were sent and more peers report byte counters than `xrpl_peer_top_n` |
| `xrpl_peer_traffic_concentration` | gauge | — | Top share divided by what an even spread would give the same number of peers. 1 is even, higher is concentrated. Same condition as the top share |

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
| `xrpl_amendment_enabled` | gauge | `name` | 1 when the network has this amendment switched on. Only with `XRPL_AMENDMENT_LABELS=all` |
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

Three groups of metrics carry labels whose values come from outside the
exporter. Only one of them has an explicit cap.

`xrpl_peer_bytes_sent` and `xrpl_peer_bytes_recv` are labelled by peer. The
label is the peer's public key, or its address when the node does not
report a key, or `unknown` when it reports neither. Only the heaviest
`XRPL_PEER_TOP_N` peers, ten by default, get their own label; everything
else is folded into a single `peer="other"` bucket, so the totals still add
up. That bucket only exists when there are more peers than the cap. The cap
limits how many peer series exist at one time, not how many different
labels turn up over a week. Peers churn, and an address includes the port,
so a peer without a key can come back under a new label. Raise the cap if
you want more, but understand what you are buying.

`xrpl_amendment_*` is labelled by amendment name, and by default only
amendments that have not activated yet get a series. That is usually a dozen
out of a hundred or so. Enabled amendments never change again, and the count
in `xrpl_amendments_enabled_total` says the same thing for less. A side
effect worth knowing: when an amendment activates, its series stops being
reported. Set `XRPL_AMENDMENT_LABELS=all` if you would rather have all of
them. That also adds `xrpl_amendment_enabled` and gives every amendment the
node knows of its own series. There is no cap beyond that list.

`xrpl_peer_versions` is labelled by the version string peers advertise, or
`unknown` for a peer that advertises none. It is not capped: there is one
series per distinct string among the connected peers. Bounded in practice by
the peer count, but it is a string peers control, so it can contain
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
