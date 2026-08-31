# Rules that were wrong, and what replaced them

Every rule in this repository that carries a long comment is here because it
woke somebody up for nothing first. The rewrites are more useful than the
rules, so they are written out properly rather than left as a one-line note.

There is one pattern underneath all of them. Alert on a resource running out
or on something failing. Never alert on a state the system passes through
normally, however alarming the state is called.

---

## Swap occupancy meant nothing

**Fired on:** a stock node with 27% of swap in use.

**What was actually happening:** nothing.

```
memory      62 GB total, 15 in use, 47 AVAILABLE
swap        7 GB total, 2 in use
paging      si=0  so=0  over five seconds of watching
node        RSS 13.8 GB, 782 MB in swap, up for 268 hours
swappiness  10
```

Over eleven days of uptime, pages that were touched once at startup get
evicted and never come back. The kernel is doing exactly what it should. The
rule was measuring occupancy, which on a long-lived process only ever goes up,
so the alert was a matter of time and meant nothing when it arrived.

**Now:** occupancy only counts alongside real shortage. More than half of swap
in use *and* less than a fifth of memory available. Active paging is a
separate rule, `SwapThrashing`, on `rate(node_vmstat_pswpin)`, and that is the
one that matters.

---

## A monthly RAID check read as three simultaneous disk failures

**Fired on:** three criticals at once, on md0, md1 and md2 of a healthy host.

Three arrays do not fail together. The check took a minute:

```
md0  active raid1  [2/2] [UU]  clean
md1  active raid1  [2/2] [UU]  clean, resyncing (DELAYED)
md2  active raid1  [2/2] [UU]  active, checking  5.6%
```

No failed disks, both mirrors complete in every array. Debian and Ubuntu run
an integrity check monthly through `checkarray`; the array being checked
reports `checking` and its neighbours queue up as `resyncing`.

The rule was `node_md_state{state="active"} != 1`. That metric is a set of
boolean flags, one per state, and during a check the `active` flag drops to
zero while `check` goes up. Three false criticals a month, forever.

**Now:** compare active disks against required disks.

```promql
sum by (instance, device) (node_md_disks{state="active"})
  < max by (instance, device) (node_md_disks_required)
```

During a check both disks stay active, so it says nothing. When one drops out
the count falls and it fires. `RaidDegraded`, on `state="failed"`, catches the
other case and stays as it was.

---

## A five-hour clock jump that every offset metric reported as zero

**Fired on:** `ClockNotSynchronised`, correctly. This entry is here for what
did *not* fire.

A hypervisor froze a guest for five and a half hours. The guest clock came
back that far behind:

```
06:45:07  Can't synchronise: no majority
06:47:04  System clock wrong by 19787.800190 seconds
```

The time daemon could see the gap perfectly well. It was not allowed to step
the clock any more, because the packaged config permits stepping only during
the first three updates after start and the process had been up since July. So
it began slewing at the maximum 8.3%, which for 19,788 seconds works out to
2.7 days of wrong time.

What made this hard was that everything looked healthy:

```
chronyc sources             offsets in microseconds, all eight sources
node_timex_offset_seconds   0
node_timex_sync_status      0     <- the only honest signal
```

The microsecond offsets were not a lie. The daemon knew about the gap and was
accounting for it internally, so the measured offsets to each server really
were small. The kernel had nothing to complain about either, because the
correction was being applied smoothly. One flag was left telling the truth.

The machine in question ran the whole monitoring stack, so for five and a half
hours every metric it collected was written into the past.

**Lesson:** `ClockDrift` on `node_timex_offset_seconds` cannot catch a large
jump and never will. Do not try to fix it with a different threshold. Keep
`ClockNotSynchronised` at critical and leave its `for` short.

**Also worth doing, outside the alerting:** set `makestep 1 -1` so the daemon
is allowed to step at any time, not only at boot. The packaged default is fine
on bare metal and wrong on anything a hypervisor can pause.

---

## A data gap turned ordinary traffic into a tenfold spike

**Fired on:** two nodes, minutes after the clock above was corrected.

`EgressSpike` compares the last half hour against the last six hours. The
correction jumped the clock five and a half hours forward and left a hole of
exactly that size in the six-hour window.

The hole destroys the denominator. `rate()` divides the counter delta by the
full window length, so a window holding data for a fifth of its span reports a
fifth of the real rate:

```
actual egress             6.07 MB/s   (three-day norm 6.6-8.1 MB/s)
rate[6h] across the hole  0.59 MB/s
6.07 > 5 x 0.59           fires, on a node doing nothing unusual
```

**Now:** a third clause checks that the baseline exists before trusting it.

```promql
count_over_time(metric[6h]) / count_over_time(metric[30m]) > 8
```

At complete coverage that ratio is exactly 12, six hours over thirty minutes,
and it does not depend on the scrape interval, which is why the guard is a
ratio rather than a sample count. During the incident it read 2.25.

**The other half of this, which has no fix:** `TrafficQuotaProjection` uses the
same six-hour window and a hole hurts it in the opposite direction. A deflated
rate deflates the projection, so the rule goes quiet exactly when it should
not. A guard would not help, because a guard also produces no alert. If that
rule falls suspiciously silent after a time problem, check `count_over_time`
over the same window by hand.

---

## Things we chose not to alert on

**Peer version spread.** `xrpl_peer_versions` is genuinely useful and belongs
on a dashboard, but "which version should I be running" is a judgement call
about a specific fix, not a threshold. The alert that does matter is
`XrplAmendmentBlockedSoon`, which fires on something unambiguous.

**Disk prediction over long windows.** `DiskWillFillSoon` looks 24 hours ahead
and no further. A node database grows as a sawtooth: it fills until the
rotation interval, a second backend appears alongside the first, and the old
one is only dropped at the rotation after that. Predicting from the falling
edge over a wider window confidently announces that a healthy disk dies
tomorrow.

**Consensus minority, provisionally.** The rule is in the repository but its
threshold is the weakest number here. The baseline is twelve samples over one
minute on one healthy validator: 119 disputes, 10 of them in the minority, a
ratio of 0.084 that swings between 0.31 and 0 between rounds. The 0.4
threshold has margin over that but has never been checked against a real
incident. Watch it for a week before letting it page anyone.
