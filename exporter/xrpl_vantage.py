#!/usr/bin/env python3
"""Prometheus exporter for an XRP Ledger node, focused on the view outward.

Most of what a node knows about itself is already covered elsewhere. What
nobody exports is what the node can see of the rest of the network, and where
it stands in it: which versions its peers run, which peer is eating the
bandwidth quota, how long the trusted validator list stays valid, which
amendments are about to activate and whether this binary understands them,
and whether the public validator registry can see this validator at all.

Only the standard library is used. That is on purpose: this is meant to run
on the same machine as a validator, and adding a dependency tree there is a
harder sell than the metrics are worth.

RPC calls run on a background schedule, not inside the scrape handler. On a
busy node server_info can take a second or two, and a scrape that waits for
it turns node slowness into monitoring gaps.
"""

import json
import os
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

RPC_URL = os.environ.get("XRPL_RPC_URL", "http://127.0.0.1:5005/")
LISTEN_ADDR = os.environ.get("XRPL_LISTEN_ADDR", "127.0.0.1")
LISTEN_PORT = int(os.environ.get("XRPL_LISTEN_PORT", "9101"))
RPC_TIMEOUT = float(os.environ.get("XRPL_RPC_TIMEOUT", "10"))

# Different questions go stale at very different rates. Ledger age is useless
# a minute late; the UNL expiry date moves once a year.
INTERVAL_FAST = int(os.environ.get("XRPL_INTERVAL_FAST", "15"))
INTERVAL_SLOW = int(os.environ.get("XRPL_INTERVAL_SLOW", "60"))
INTERVAL_REGISTRY = int(os.environ.get("XRPL_INTERVAL_REGISTRY", "300"))

# Per-peer byte counters are the whole point of the traffic section, but a
# label per peer is also the easiest way to blow up cardinality: peers churn,
# and every new public key is a new series forever. Only the heaviest N are
# labelled. Everything else is folded into the "other" bucket, so the sum
# still adds up.
PEER_TOP_N = int(os.environ.get("XRPL_PEER_TOP_N", "10"))

# Amendment labels are limited to the ones that are not enabled yet, which is
# usually a dozen or so out of a hundred. Enabled amendments never change
# again and are not worth a series each; the count is enough.
AMENDMENT_LABELS = os.environ.get("XRPL_AMENDMENT_LABELS", "pending")

REGISTRY_URL = os.environ.get(
    "XRPL_REGISTRY_URL", "https://data.xrpl.org/v1/network/validators")
REGISTRY_ENABLED = os.environ.get("XRPL_REGISTRY", "1") not in ("0", "false", "no")
REGISTRY_TIMEOUT = float(os.environ.get("XRPL_REGISTRY_TIMEOUT", "30"))

# Which validator to look up in the registry. Left empty the exporter uses the
# key of the node it is attached to, which is the obvious thing to want.
#
# Setting it explicitly lets any node watch any validator, and there is a good
# reason to: a validator kept off the public network does not necessarily want
# to be making outbound calls to a third-party API from its own address. Point
# a stock node at the validator's master key instead and the same metrics come
# out, from a machine that is already public. The key itself is public
# information, so there is nothing to protect here.
REGISTRY_KEY = os.environ.get("XRPL_MASTER_KEY", "").strip()

# The order matters: it is the order a node walks through on its way to being
# useful, so the number is comparable across nodes.
SERVER_STATES = ["disconnected", "connected", "syncing", "tracking",
                 "full", "proposing", "validating"]
CONSENSUS_PHASES = ["open", "establish", "accepted"]

# Index of the Amendments singleton in the ledger. Reading it is the only way
# to learn which amendments already hold a majority, which is what makes an
# activation estimate possible.
AMENDMENTS_INDEX = \
    "7DB0788C020F02780A673DC74757F23823FA3014C1866E72CC4CD8B226CD6EF4"

# Ledger close times are seconds since 2000-01-01, not since the epoch.
RIPPLE_EPOCH_OFFSET = 946684800

# An amendment that holds a majority activates two weeks later, at the first
# flag ledger after the window closes.
AMENDMENT_MAJORITY_WINDOW = 14 * 24 * 3600

_lock = threading.Lock()
_samples = {}          # section name -> list of rendered metric lines
_errors = {}           # section name -> 1 if the last collection failed


def rpc(method, params=None, timeout=None):
    body = json.dumps({"method": method, "params": [params or {}]}).encode()
    req = urllib.request.Request(
        RPC_URL, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout or RPC_TIMEOUT) as resp:
        payload = json.loads(resp.read())
    result = payload.get("result", {})
    if result.get("status") == "error":
        raise RuntimeError(result.get("error_message") or result.get("error"))
    return result


class Section:
    """Collects the lines for one group of metrics.

    Kept deliberately dumb. Formatting Prometheus text is not hard enough to
    justify a client library, and not pulling one in is why this file has no
    dependencies.
    """

    def __init__(self):
        self.lines = []
        self._declared = set()

    # The first argument is called "metric" rather than "name" on purpose:
    # "name" is a label this exporter actually uses, for amendments, and a
    # parameter of the same name would collide with it.
    def add(self, metric, value, help_text=None, mtype="gauge", **labels):
        if value is None:
            return
        if metric not in self._declared:
            if help_text:
                self.lines.append("# HELP {} {}".format(metric, help_text))
            self.lines.append("# TYPE {} {}".format(metric, mtype))
            self._declared.add(metric)
        if labels:
            rendered = ",".join(
                '{}="{}"'.format(k, escape_label(str(v)))
                for k, v in sorted(labels.items()) if v is not None)
            self.lines.append("{}{{{}}} {}".format(metric, rendered, fmt(value)))
        else:
            self.lines.append("{} {}".format(metric, fmt(value)))


def escape_label(value):
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def is_private_address(address):
    """True when a peer address sits in a private range.

    Used to answer one specific question: is a validator that is supposed to
    be reachable only through its own stock nodes actually isolated. A single
    public peer means the isolation has broken, and the node is now reachable
    from the open network whether or not anybody has noticed.

    IPv4 private ranges plus loopback and link-local, and the IPv6
    equivalents. Peer addresses arrive as host:port and IPv6 comes bracketed.
    """
    if not address:
        return False
    text = str(address)
    if text.startswith("["):
        text = text[1:text.find("]")] if "]" in text else text[1:]
    elif text.count(":") == 1:
        text = text.split(":")[0]
    text = text.lower()
    if text.startswith(("fc", "fd", "fe8", "fe9", "fea", "feb")) or text in ("::1",):
        return True
    parts = text.split(".")
    if len(parts) != 4:
        return False
    try:
        a, b = int(parts[0]), int(parts[1])
    except ValueError:
        return False
    return (a == 10 or a == 127 or (a == 192 and b == 168)
            or (a == 172 and 16 <= b <= 31) or (a == 169 and b == 254))


def num(value):
    """Coerce a JSON value to a number, or None.

    rippled is inconsistent about this and it costs people time. The byte
    counters under a peer's "metrics" come back as strings:

        "metrics": {"total_bytes_sent": "145199241", "avg_bps_sent": "15001"}

    while "latency" right next to them is a plain integer. An isinstance
    check against int and float silently drops the whole traffic section, and
    the metric just never appears.
    """
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fmt(value):
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, float):
        return repr(round(value, 6))
    return str(value)


def publish(name, section):
    with _lock:
        _samples[name] = section.lines
        _errors[name] = 0


def fail(name):
    with _lock:
        _errors[name] = 1


def ledger_span(complete):
    """Turn '19384617-19385584,19385600' into a count of ledgers held."""
    if not complete or complete in ("empty", "unknown"):
        return 0
    total = 0
    for chunk in complete.split(","):
        chunk = chunk.strip()
        if "-" in chunk:
            low, high = chunk.split("-", 1)
            try:
                total += int(high) - int(low) + 1
            except ValueError:
                continue
        elif chunk.isdigit():
            total += 1
    return total


def parse_ripple_time(text):
    """'2027-Apr-06 17:51:34.000000000 UTC' -> unix seconds.

    rippled prints times in its own shape and there is no format string in
    the standard library that reads it directly, so the month name is looked
    up by hand.
    """
    if not text:
        return None
    months = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
              "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}
    try:
        date_part, time_part = text.split(" ")[0], text.split(" ")[1]
        year, mon, day = date_part.split("-")
        hour, minute, second = time_part.split(":")
        import calendar
        return calendar.timegm((
            int(year), months[mon], int(day),
            int(hour), int(minute), int(float(second)), 0, 0, 0))
    except (ValueError, KeyError, IndexError):
        return None


# --------------------------------------------------------------------------
# server_info: the basics, and the master key the registry poller needs
# --------------------------------------------------------------------------

_master_key = None
_signing_key = None


def collect_server_info():
    global _master_key
    s = Section()
    try:
        info = rpc("server_info")["info"]
    except Exception:
        s.add("xrpl_up", 0, "1 when the node answered admin RPC")
        publish("server_info", s)
        fail("server_info")
        return
    s.add("xrpl_up", 1, "1 when the node answered admin RPC")

    state = info.get("server_state", "")
    s.add("xrpl_server_state",
          SERVER_STATES.index(state) if state in SERVER_STATES else -1,
          "Node state as a number, ordered by progress towards validating",
          state=state)
    s.add("xrpl_server_ready", 1 if state in ("full", "proposing", "validating") else 0,
          "1 when the node is caught up enough to answer for the network")

    ledger = info.get("validated_ledger") or {}
    s.add("xrpl_validated_ledger_seq", ledger.get("seq"),
          "Sequence of the last validated ledger", "counter")
    s.add("xrpl_validated_ledger_age_seconds", ledger.get("age"),
          "How far behind the network the last validated ledger is")
    s.add("xrpl_complete_ledgers", ledger_span(info.get("complete_ledgers", "")),
          "Number of ledgers held on disk")

    # Peer count deliberately does not appear here even though server_info
    # carries it. It is published once, by the peers collector, as
    # xrpl_peers_total. Two names for one number is the sort of thing that
    # ends up in somebody's alert with the wrong one.
    for key, name, help_text in [
            ("io_latency_ms", "xrpl_io_latency_ms", "Job queue IO latency"),
            ("load_factor", "xrpl_load_factor", "Current load factor"),
            ("validation_quorum", "xrpl_validation_quorum",
             "Validations required to declare a ledger validated"),
            ("fetch_pack", "xrpl_fetch_pack", "Fetch pack size")]:
        value = info.get(key)
        if isinstance(value, (int, float)):
            s.add(name, value, help_text)

    s.add("xrpl_uptime_seconds", info.get("uptime"), "Process uptime", "counter")
    s.add("xrpl_amendment_blocked", 1 if info.get("amendment_blocked") else 0,
          "1 when the node refuses to work because it does not know an "
          "amendment the network enabled")

    counters = info.get("counters") or {}
    for key, name, help_text in [
            ("peer_disconnects", "xrpl_peer_disconnects_total",
             "Peer disconnects since start"),
            ("peer_disconnects_resources", "xrpl_peer_disconnects_resources_total",
             "Peer disconnects caused by resource limits")]:
        if key in counters:
            s.add(name, counters[key], help_text, "counter")

    pubkey = info.get("pubkey_validator", "none")
    s.add("xrpl_validator_configured", 0 if pubkey in ("none", None) else 1,
          "1 when this node is configured to validate")
    if pubkey not in ("none", None):
        _master_key = pubkey

    s.add("xrpl_build_info", 1, "Node version, carried in the label",
          version=info.get("build_version", "unknown"),
          network_id=info.get("network_id", ""))
    publish("server_info", s)


# --------------------------------------------------------------------------
# peers: version spread, who is using the bandwidth, latency
# --------------------------------------------------------------------------

def collect_peers():
    s = Section()
    try:
        peers = rpc("peers").get("peers") or []
    except Exception:
        fail("peers")
        return

    s.add("xrpl_peers_total", len(peers), "Peers currently connected")

    inbound = sum(1 for p in peers if p.get("inbound"))
    cluster = sum(1 for p in peers if p.get("cluster"))
    s.add("xrpl_peers_inbound", inbound, "Peers that connected to us")
    s.add("xrpl_peers_outbound", len(peers) - inbound, "Peers we connected to")
    s.add("xrpl_peers_cluster", cluster, "Peers recognised as our own cluster")

    private = sum(1 for p in peers if is_private_address(p.get("address")))
    s.add("xrpl_peers_private", private, "Peers reached over a private network")
    s.add("xrpl_peers_public", len(peers) - private,
          "Peers outside any private range. On a validator that is meant to sit "
          "behind its own stock nodes this should be zero, and anything above "
          "zero means the isolation has broken")

    # Version spread. One well-connected node sees enough of the network for
    # this to be a usable estimate of how far an upgrade has spread, which is
    # the question behind "has the fix I need reached the network yet".
    versions = {}
    for p in peers:
        versions[p.get("version") or "unknown"] = \
            versions.get(p.get("version") or "unknown", 0) + 1
    for version, count in sorted(versions.items()):
        s.add("xrpl_peer_versions", count,
              "Connected peers per advertised version", version=version)

    # A peer speaking a different network id means somebody is misconfigured,
    # and it is worth knowing whether that somebody is us.
    wrong_network = 0
    own = None
    for p in peers:
        nid = p.get("network_id")
        if nid is None:
            continue
        if own is None:
            own = nid
        if nid != own:
            wrong_network += 1
    s.add("xrpl_peers_wrong_network", wrong_network,
          "Peers reporting a network id different from the majority")

    latencies = sorted(v for v in (num(p.get("latency")) for p in peers)
                       if v is not None)
    if latencies:
        def at(fraction):
            return latencies[min(len(latencies) - 1,
                                 int(len(latencies) * fraction))] / 1000.0
        s.add("xrpl_peer_latency_seconds", latencies[0] / 1000.0,
              "Round trip time to peers", quantile="0")
        s.add("xrpl_peer_latency_seconds", at(0.5), quantile="0.5")
        s.add("xrpl_peer_latency_seconds", at(0.9), quantile="0.9")
        s.add("xrpl_peer_latency_seconds", latencies[-1] / 1000.0, quantile="1")

    # Bandwidth per peer. The node keeps byte counters for every connection,
    # which turns "something is eating the monthly quota" into a name.
    ranked = []
    for p in peers:
        metrics = p.get("metrics") or {}
        sent = num(metrics.get("total_bytes_sent"))
        recv = num(metrics.get("total_bytes_recv"))
        if sent is not None:
            ranked.append((sent, recv or 0, p))
    ranked.sort(key=lambda row: -row[0])

    total_sent = sum(row[0] for row in ranked)
    s.add("xrpl_peer_bytes_sent_total", total_sent,
          "Bytes sent to peers since the node started, all peers", "counter")

    other_sent = other_recv = 0
    for index, (sent, recv, p) in enumerate(ranked):
        if index < PEER_TOP_N:
            label = p.get("public_key") or p.get("address") or "unknown"
            s.add("xrpl_peer_bytes_sent", sent,
                  "Bytes sent to one peer, heaviest peers only", "counter",
                  peer=label)
            s.add("xrpl_peer_bytes_recv", recv,
                  "Bytes received from one peer, heaviest peers only",
                  "counter", peer=label)
        else:
            other_sent += sent
            other_recv += recv
    if len(ranked) > PEER_TOP_N:
        s.add("xrpl_peer_bytes_sent", other_sent, mtype="counter", peer="other")
        s.add("xrpl_peer_bytes_recv", other_recv, mtype="counter", peer="other")

    # Published so a rule can scale itself to the cap instead of hardcoding it.
    s.add("xrpl_peer_top_n", PEER_TOP_N,
          "How many peers get their own byte counters")

    # Concentration only means something when there are meaningfully more peers
    # than the cap. Below that the share is arithmetic: the top ten of two peers
    # is a hundred percent, always, and a rule reading it fires on the quietest
    # node in the fleet while the busiest one stays silent.
    if total_sent > 0 and len(ranked) > PEER_TOP_N:
        top_share = sum(row[0] for row in ranked[:PEER_TOP_N]) / total_sent
        s.add("xrpl_peer_traffic_top_share", top_share,
              "Share of outbound bytes taken by the heaviest peers. Only "
              "published when there are more peers than the cap, because "
              "below that it is always one")

        # The share on its own still moves with peer count: spread perfectly
        # evenly, ten of thirty peers take a third and ten of a hundred and
        # forty take a fourteenth. Dividing by that floor gives a number that
        # means the same thing on any node. One is perfectly even, and higher
        # is genuinely concentrated.
        even_floor = PEER_TOP_N / len(ranked)
        s.add("xrpl_peer_traffic_concentration", top_share / even_floor,
              "How much more of the outbound the heaviest peers take than an "
              "even spread would give them")

    publish("peers", s)


# --------------------------------------------------------------------------
# validators and validator_list_sites: how long the UNL stays valid
# --------------------------------------------------------------------------

def collect_validator_lists():
    s = Section()
    now = time.time()
    try:
        v = rpc("validators")
    except Exception:
        fail("validators")
        return

    s.add("xrpl_trusted_validators", len(v.get("trusted_validator_keys") or []),
          "Validators currently trusted, from all publisher lists combined")
    s.add("xrpl_validation_quorum_configured", v.get("validation_quorum"),
          "Quorum the node is working with")

    # An expired UNL stops the node from validating. It is a deadline that
    # arrives on its own, with no warning anywhere else, so it gets a metric
    # that counts down by itself.
    for pl in v.get("publisher_lists") or []:
        uri = pl.get("uri", "unknown")
        s.add("xrpl_unl_available", 1 if pl.get("available") else 0,
              "1 when the node holds a usable list from this publisher",
              publisher=uri)
        s.add("xrpl_unl_seq", pl.get("seq"),
              "Sequence number of the list currently held", publisher=uri)
        expires = parse_ripple_time(pl.get("expiration"))
        if expires:
            s.add("xrpl_unl_expires_seconds", expires - now,
                  "Seconds until the trusted list from this publisher expires",
                  publisher=uri)

    try:
        sites = rpc("validator_list_sites").get("validator_sites") or []
    except Exception:
        sites = []
    for site in sites:
        uri = site.get("uri", "unknown")
        status = site.get("last_refresh_status", "unknown")
        # "same_sequence" means the node fetched the list and it had not
        # changed, which is the normal steady state. Anything else is either
        # a fresh list or a fetch that did not work.
        s.add("xrpl_unl_refresh_ok", 1 if status in ("same_sequence", "accepted") else 0,
              "1 when the last list refresh from this site worked",
              site=uri, status=status)
        last = parse_ripple_time(site.get("last_refresh_time"))
        if last:
            s.add("xrpl_unl_refresh_age_seconds", now - last,
                  "Time since this site was last refreshed", site=uri)

    publish("validators", s)


# --------------------------------------------------------------------------
# feature plus the Amendments ledger object: what is coming and when
# --------------------------------------------------------------------------

def collect_amendments():
    s = Section()
    try:
        features = rpc("feature").get("features") or {}
    except Exception:
        fail("amendments")
        return

    enabled = 0
    unsupported = 0
    by_id = {}
    for amendment_id, f in features.items():
        name = f.get("name") or amendment_id[:16]
        is_enabled = bool(f.get("enabled"))
        is_supported = bool(f.get("supported"))
        by_id[amendment_id.upper()] = (name, is_supported)
        if is_enabled:
            enabled += 1
        elif not is_supported:
            unsupported += 1

        # In the default mode only amendments that have not activated yet get
        # a series each. The enabled ones never change again, and a hundred
        # frozen series is a poor trade for the one count that says the same
        # thing. A side effect worth knowing: when an amendment activates its
        # series stops being reported, which reads cleanly on a graph.
        if is_enabled and AMENDMENT_LABELS != "all":
            continue
        if AMENDMENT_LABELS == "all":
            s.add("xrpl_amendment_enabled", 1 if is_enabled else 0,
                  "1 when the network has this amendment switched on", name=name)
        s.add("xrpl_amendment_supported", 1 if is_supported else 0,
              "1 when this binary knows how to apply the amendment", name=name)
        s.add("xrpl_amendment_vetoed", 1 if f.get("vetoed") else 0,
              "1 when this node votes against the amendment", name=name)

    s.add("xrpl_amendments_total", len(features), "Amendments the node knows of")
    s.add("xrpl_amendments_enabled_total", enabled, "Amendments switched on")
    s.add("xrpl_amendments_unsupported_total", unsupported,
          "Amendments this binary does not know how to apply")

    # Majorities is where an activation date becomes possible to work out.
    # Everything above only says yes or no; this says when.
    try:
        node = rpc("ledger_entry", {"index": AMENDMENTS_INDEX,
                                    "ledger_index": "validated"})["node"]
    except Exception:
        publish("amendments", s)
        return

    now = time.time()
    unsupported_majority = 0
    for entry in node.get("Majorities") or []:
        majority = entry.get("Majority") or {}
        amendment_id = (majority.get("Amendment") or "").upper()
        close_time = majority.get("CloseTime")
        if not amendment_id or close_time is None:
            continue
        name, is_supported = by_id.get(amendment_id, (amendment_id[:16], False))
        since = close_time + RIPPLE_EPOCH_OFFSET
        s.add("xrpl_amendment_majority_seconds", max(0, now - since),
              "How long this amendment has held a majority", name=name)
        s.add("xrpl_amendment_eta_seconds",
              max(0, since + AMENDMENT_MAJORITY_WINDOW - now),
              "Estimated seconds until this amendment activates", name=name)
        if not is_supported:
            unsupported_majority += 1

    # The one worth waking somebody up for. An amendment holding a majority
    # that this binary does not know about will block the node when it
    # activates, and that is two weeks of notice going unused.
    s.add("xrpl_amendments_unsupported_majority", unsupported_majority,
          "Amendments heading for activation that this binary cannot apply")
    s.add("xrpl_amendments_in_majority", len(node.get("Majorities") or []),
          "Amendments currently holding a majority")
    publish("amendments", s)


# --------------------------------------------------------------------------
# consensus_info: not how many disputes, but which side we are on
# --------------------------------------------------------------------------

def collect_consensus():
    s = Section()
    try:
        info = rpc("consensus_info").get("info") or {}
    except Exception:
        fail("consensus")
        return

    phase = info.get("phase", "")
    s.add("xrpl_consensus_phase",
          CONSENSUS_PHASES.index(phase.lower()) if phase.lower() in CONSENSUS_PHASES else -1,
          "Consensus phase as a number", phase=phase)
    s.add("xrpl_consensus_proposing", 1 if info.get("proposing") else 0,
          "1 when this node is putting forward its own position")
    s.add("xrpl_consensus_validating", 1 if info.get("validating") else 0,
          "1 when this node is signing validations")
    s.add("xrpl_consensus_synched", 1 if info.get("synched") else 0,
          "1 when this node agrees with the network on the previous ledger")
    for key, name in [("proposers", "xrpl_consensus_proposers"),
                      ("previous_proposers", "xrpl_consensus_previous_proposers"),
                      ("converge_percent", "xrpl_consensus_converge_percent"),
                      ("previous_mseconds", "xrpl_consensus_previous_ms")]:
        if isinstance(info.get(key), (int, float)):
            s.add(name, info[key], "From consensus_info: " + key)

    disputes = info.get("disputes") or {}
    s.add("xrpl_consensus_disputes", len(disputes),
          "Transactions this node and its peers disagree about right now")

    # A dispute on its own is normal: a transaction arrives late for some and
    # on time for others. Being on the losing side of one is different. It
    # says this node is seeing a different network than everyone else, which
    # is what a squeezed uplink or a drifting clock looks like from here.
    minority = 0
    for dispute in disputes.values():
        if not isinstance(dispute, dict):
            continue
        our_vote = dispute.get("our_vote")
        votes = dispute.get("votes") or {}
        if our_vote is None or not votes:
            continue
        agreeing = sum(1 for v in votes.values() if v == our_vote)
        if agreeing * 2 < len(votes):
            minority += 1
    s.add("xrpl_consensus_disputes_minority", minority,
          "Disputes where this node is voting against the majority of peers")
    publish("consensus", s)


# --------------------------------------------------------------------------
# The public validator registry: can anyone else actually see this validator
# --------------------------------------------------------------------------

def collect_registry():
    global _signing_key
    if not REGISTRY_ENABLED:
        return
    s = Section()
    key = REGISTRY_KEY or _master_key
    if not key:
        publish("registry", s)
        return

    # Ask the node for its own manifest. Two things come out of it: the
    # sequence number, which is worth graphing on its own because a manifest
    # going backwards means somebody deployed an old token, and the ephemeral
    # signing key, which the registry lookup below needs.
    # A node that is not the validator itself may still know its manifest,
    # because manifests propagate. If it does not, the section carries on
    # without the sequence number.
    try:
        details = rpc("manifest", {"public_key": key}).get("details") or {}
        _signing_key = details.get("ephemeral_key") or _signing_key
        s.add("xrpl_manifest_seq", details.get("seq"),
              "Sequence of the manifest this validator is publishing")
        s.add("xrpl_manifest_domain_set", 1 if details.get("domain") else 0,
              "1 when the manifest carries a domain")
    except Exception:
        pass

    code = 0
    try:
        req = urllib.request.Request(
            REGISTRY_URL, headers={"User-Agent": "xrpl-vantage"})
        with urllib.request.urlopen(req, timeout=REGISTRY_TIMEOUT) as resp:
            code = resp.status
            body = json.loads(resp.read().decode(), strict=False)
    except urllib.error.HTTPError as e:
        code = e.code
        body = None
    except Exception:
        body = None

    s.add("xrpl_registry_lookup_code", code,
          "HTTP status from the last registry poll, 0 when it did not answer")
    s.add("xrpl_registry_up", 1 if code == 200 else 0,
          "1 when the registry answered at all")
    if body is None:
        publish("registry", s)
        return

    # Match on the signing key as well as the master key, and not as a
    # convenience. When the registry loses the link to the master key it also
    # stops keying the record by it: master_key goes null and
    # validation_public_key becomes the signing key. Looking only by master
    # key then finds nothing, and the exporter would report "not listed" for a
    # validator that is listed and validating perfectly well. Checking both is
    # what lets xrpl_registry_listed and xrpl_registry_master_key_present say
    # different things, which is the entire point of this section.
    wanted = {k for k in (key, _signing_key) if k}
    record = None
    for v in body.get("validators") or []:
        if wanted & {v.get("validation_public_key"), v.get("master_key"),
                     v.get("signing_key")}:
            record = v
            break

    s.add("xrpl_registry_listed", 1 if record else 0,
          "1 when the registry has a record for this validator")
    if not record:
        publish("registry", s)
        return

    # This is the whole reason the section exists. A record can be present and
    # still have lost the link to the master key, which breaks every lookup
    # that goes by master key. At the time of writing it is the state of about
    # a third of the validators in the public registry, and none of their
    # operators have a way to notice.
    s.add("xrpl_registry_master_key_present",
          1 if record.get("master_key") else 0,
          "1 when the registry record still carries the master key")
    s.add("xrpl_registry_domain_present", 1 if record.get("domain") else 0,
          "1 when the registry record carries a domain")
    s.add("xrpl_registry_unl_listed", 1 if record.get("unl") else 0,
          "1 when this validator is on a published UNL")

    agreement = (record.get("agreement_30day") or {}).get("score")
    try:
        s.add("xrpl_registry_agreement_score", float(agreement),
              "Agreement score over 30 days as the registry computes it")
    except (TypeError, ValueError):
        pass
    publish("registry", s)


# --------------------------------------------------------------------------
# scheduling and serving
# --------------------------------------------------------------------------

def loop(fn, interval, name):
    while True:
        started = time.time()
        try:
            fn()
        except Exception:
            fail(name)
        time.sleep(max(1.0, interval - (time.time() - started)))


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.split("?")[0] not in ("/metrics", "/"):
            self.send_error(404)
            return
        with _lock:
            lines = []
            for section in sorted(_samples):
                lines.extend(_samples[section])
            lines.append("# HELP xrpl_collector_failed 1 when a collector's "
                         "last run raised")
            lines.append("# TYPE xrpl_collector_failed gauge")
            for section, failed in sorted(_errors.items()):
                lines.append('xrpl_collector_failed{{section="{}"}} {}'
                             .format(section, failed))
        body = ("\n".join(lines) + "\n").encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def main():
    schedule = [
        (collect_server_info, INTERVAL_FAST, "server_info"),
        (collect_peers, INTERVAL_FAST, "peers"),
        (collect_consensus, INTERVAL_FAST, "consensus"),
        (collect_validator_lists, INTERVAL_SLOW, "validators"),
        (collect_amendments, INTERVAL_SLOW, "amendments"),
        (collect_registry, INTERVAL_REGISTRY, "registry"),
    ]
    for fn, interval, name in schedule:
        threading.Thread(target=loop, args=(fn, interval, name),
                         daemon=True).start()
    ThreadingHTTPServer((LISTEN_ADDR, LISTEN_PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
