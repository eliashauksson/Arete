# Arete — Core Training Science (Sport-Agnostic)

## 0. Purpose and usage

This is the baseline every Arete plan is built on, regardless of sport. It is **always
injected** into plan generation.

- If a sport-specific module exists for the athlete's discipline, it is injected on top
  of this document. Where the two directly conflict, **the sport module wins** (sport
  evidence is more precise than general endurance principle).
- If no sport-specific module exists, generate from this document plus general knowledge
  of the sport's demands. This is the intended fallback — no special handling needed.
- For multi-sport athletes without a combo-specific module, see §12.

Everything below is written as guidance for the planning model. It should be reasoned
with, not pattern-matched — an 18-week plan for a deconditioned 50-year-old and for a
sub-elite 25-year-old with the same goal race should look meaningfully different.

---

## 1. Foundational principles

Apply in this priority order when they conflict:

1. **Individualization** — training history, current fitness, age, recovery capacity,
   injury history, and non-training life stress set the ceiling on absorbable load. This
   is the first filter on every other decision below.
2. **Progressive overload** — load rises gradually; the body adapts to stress slightly
   above current capacity, not far above it.
3. **Specificity** — as the event nears, training converges on the energy systems,
   movement patterns, durations, and terrain the event actually demands.
4. **Continuity** — consistent, uninterrupted training beats sporadic hard blocks.
   Avoid plans so aggressive they cause breakdowns; a missed week costs more than a
   slightly easier week gains.
5. **Reversibility** — fitness decays roughly as gained, somewhat faster for anaerobic
   qualities than aerobic base. Reintroduce load conservatively after any gap.
6. **Recovery is where adaptation happens** — a plan with no easy days or deloads isn't
   a stronger plan, it's a higher-injury-risk one.

## 2. Periodization

Always structure time **backward from the event date**.

- **Macrocycle** — the full plan.
- **Mesocycle** — typically 3–4 weeks, ending in a lighter deload week.
- **Microcycle** — typically one week, the repeating unit.

Phase progression and rough proportions for an 18–24 week plan (compress proportionally
for shorter timelines; extend the base for longer ones):

| Phase | Share of plan | Primary goal |
|---|---|---|
| Base | 40–50% | Aerobic capacity, movement economy, durability, work capacity |
| Build | 25–35% | Raise threshold, introduce event-specific intensity |
| Peak / Specific | 10–15% | Event-pace and event-demand specificity, sharpening |
| Taper | 5–15% (event-dependent) | Shed fatigue, retain fitness |

**Linear vs. block periodization.** Default to linear (gradual phase blending) for
newer athletes and longer timelines. Prefer **block periodization** — concentrating on
one quality for 1–3 weeks at a time — for experienced athletes, compressed timelines
(<12 weeks), or when a single limiter dominates (e.g. weak muscular endurance, weak
threshold). Block work produces sharper adaptation but tolerates less simultaneous
stress, so it suits athletes who already have a base.

## 3. Energy systems and thresholds

Two thresholds anchor everything:

- **Aerobic threshold (AeT / LT1)** — the upper boundary of "easy." Below it, metabolism
  is almost purely aerobic, fat oxidation dominates, lactate stays near baseline (~2
  mmol/L), and sessions are highly recoverable. The large majority of volume sits here.
- **Anaerobic threshold (AnT / LT2 / MLSS)** — the highest intensity sustainable in a
  quasi-steady state. Above it, lactate accumulates faster than it clears; efforts are
  short-lived and expensive to recover from.

When lab testing isn't available, both can be estimated from **field tests** (see sport
modules for protocols) or device-derived thresholds. A useful AeT proxy: the highest
intensity at which an athlete can sustain nasal breathing / hold a conversation, and at
which HR drifts less than ~5% over a sustained steady effort.

## 4. Intensity distribution

Distribution should be **polarized**, not pyramidal and never "grey": most volume easy,
a small deliberate dose hard, minimal time in the moderate zone between AeT and AnT.
The grey zone feels productive but yields disproportionate fatigue per unit of
adaptation. Rough targets by phase:

| Phase | Easy (<AeT) | Moderate (AeT–AnT) | Hard (>AnT) |
|---|---|---|---|
| Base | ~85–90% | ~5–10% | ~5% |
| Build | ~75–80% | ~5–10% | ~15–20% |
| Peak | ~70–75% | ~5–10% | ~20–25% |

**The single most common amateur error — and the easiest trap for an AI planner — is
too much grey-zone moderate work.** Moderate-paced long sessions look reasonable in
isolation, so the planner must actively defend the easy/hard split rather than drifting
toward comfortable-hard everywhere.

## 5. Quantifying load (ties into Arete's existing metrics)

Arete computes TSS/CTL/ATL/TSB (Coggan model). Guardrails for using them in planning:

- **CTL (chronic load)** ≈ fitness. Should rise gradually and smoothly, never in steps.
- **ATL (acute load)** ≈ recent fatigue.
- **TSB (≈ CTL − ATL)** ≈ freshness. Deeply negative before a key race is a red flag;
  near zero or slightly positive is the race-day target.
- **Weekly progression** — default ceiling of ~8–10% week-over-week increase in weekly
  load. A guideline, not a law; tolerance varies by athlete.
- **Deload cadence** — every 3rd or 4th week, cut volume 40–60% while retaining some
  intensity, letting CTL consolidate instead of just stacking ATL.
- **ACWR (acute:chronic workload ratio)** — ~7-day load over ~28-day load. Keep roughly
  0.8–1.3. Above ~1.5 correlates with materially elevated injury risk and should
  auto-flag a plan adjustment.
- **Caveat for vertical/eccentric sports** — flat-pace TSS undercounts the real cost of
  climbing and descending. Where the sport module provides a vert-aware adjustment, use
  it; otherwise treat raw TSS as an underestimate for hilly work.

## 6. Recovery, adaptation, and monitoring

Adaptation follows **stress → fatigue → recovery → supercompensation**. Training again
before recovery completes (outside a deliberate overload block) blunts adaptation.

Distinguish **functional overreaching** (planned, short, followed by recovery → fitness
rebound) from **non-functional overreaching / overtraining** (unplanned, prolonged,
with performance decline, mood disturbance, poor sleep, elevated illness). Persistent
negative TSB *plus* declining performance markers means insert recovery, don't push
through.

When physiological data is available (resting HR, HRV, sleep — see Garmin roadmap),
treat it as **override signal**: the written plan proposes a session, but elevated
resting HR or suppressed HRV on the day is grounds to substitute something easier,
independent of the plan.

## 7. Tapering

Scale to event demand:

| Event duration | Taper length | Volume reduction |
|---|---|---|
| Short (<2 hr) | 4–7 days | ~30–40% |
| Marathon-ish | 10–14 days | ~40–50% |
| Ultra | 14–21 days | ~50–60% |

**Cut volume, keep intensity (in smaller doses).** Some race-pace work through the taper
prevents the staleness of going fully easy for two-plus weeks. Frequency stays roughly
constant; it's session length and total volume that drop.

## 8. Strength and conditioning (general principles)

S&C is part of every plan, not an optional add-on, even for single-sport endurance
athletes. It improves economy, durability, force production, and injury resistance.
Periodize it **inversely to specificity**:

| Phase | Frequency | Emphasis |
|---|---|---|
| Base | 2–3×/week | Movement quality, general strength, anatomical adaptation |
| Build | 1–2×/week | Max strength → sport-specific loading, power/plyometrics |
| Peak/Taper | 0–1×/week | Maintenance only; deprioritized for recovery and specificity |

General progression of a strength block: **anatomical adaptation (higher rep, moderate
load) → max strength (heavy, low rep, long rest) → power/conversion (plyometrics, fast
or sport-specific loading) → maintenance.** Heavy resistance training and plyometrics
each have strong evidence for improving endurance running economy without adding bulk
when volume is controlled. Sport modules specify the exact emphasis (e.g. eccentric and
single-leg work for trail descending vs. reactive plyometrics for road economy).

## 9. Injury prevention and load management

- Beyond ACWR (§5), avoid **monotony** — a week where every session is similar
  intensity/duration carries more strain and injury risk than a varied week of equal
  total load. Vary session type day to day within a phase.
- Distinguish **fatigue** (normal, plan continues) from **pain** (abnormal — flag,
  suggest modification or rest, never "push through").
- Front-load durability: tissue (tendon, bone, connective) adapts slower than
  cardiovascular fitness, so early base-phase load should be gated by tissue readiness,
  not by how fit the heart and lungs feel.

## 10. Individualization factors to weight

- **Experience** — newer athletes need slower volume progression and more frequent
  deloads at the same numeric load.
- **Age** — recovery generally lengthens with age; consider longer deload cadence and
  slightly lower peak intensity-volume for masters athletes at equal fitness.
- **Life stress** — non-training stress draws on the same recovery pool. Where reported,
  treat it as a modifier on appropriate weekly load.
- **Sex / menstrual cycle** — where the athlete provides this and opts in, cycle phase
  can modestly inform load placement; keep this opt-in and non-presumptuous.

## 11. Goal-setting and event analysis

Before structuring a plan, characterize the event: duration, terrain, total
elevation gain/loss, surface, climate, altitude, expected intensity profile, mandatory
gear/fueling constraints, and the athlete's specific goal (finish vs. time vs. place).
The plan's specificity phase should rehearse the event's actual demands — the more
unusual the event, the more the late-phase sessions should mimic it.

## 12. Integrating multiple sports

When an athlete trains more than one discipline and no combo module exists:

- **Don't naively sum TSS across modalities.** Track *systemic* (cardiovascular) load
  and *local* (musculoskeletal) load somewhat separately — different sports stress
  different tissues.
- Apply the core periodization and intensity-distribution principles across the combined
  plan, while preserving each sport's own technique and specificity needs.
- **Flag high local-overlap combinations** (e.g. running + heavy hiking, both loading
  the same eccentric/impact tissues) for more conservative combined volume than the
  individual modules imply.
- Where disciplines have low overlap (e.g. swimming + running), one can serve as
  recovery-supporting aerobic volume for the other.

---

## Instructions to the planning model (summary)

1. Treat this as the default baseline for every plan.
2. Apply any sport-specific module on top, and prefer it where it directly conflicts.
3. With no sport module, generate from this plus general sport knowledge; if asked, note
   briefly and non-defensively that the plan rests on general endurance principles.
4. For multi-sport without a combo module, follow §12.
5. Reason about the individual in front of you. Defend the polarized easy/hard split.
   Respect continuity over heroics. When in doubt, err toward the more recoverable plan.
