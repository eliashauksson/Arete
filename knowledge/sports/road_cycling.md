# Arete — Sport Module: Road Cycling

> Scientific basis: Hunter Allen & Andrew Coggan, *Training and Racing with a Power
> Meter* (FTP, the 7-zone power model, and the TSS/CTL/ATL/TSB framework itself);
> Joe Friel, *The Cyclist's Training Bible* (periodization); Bent Rønnestad's research
> on strength training and short-interval work for cyclists; Stephen Seiler (polarized
> intensity distribution, much of it validated on cyclists); Iñigo San Millán (Zone 2 /
> metabolic and mitochondrial work). This module sits on top of `core_training_science.md`
> and overrides it where they directly conflict. It covers road racing, time trials,
> gran fondo, and climbing events.
>
> **Key alignment:** the Coggan PMC model (TSS/CTL/ATL/TSB) that Arete already computes
> *originates in cycling*. This module therefore maps onto Arete's existing metrics more
> directly than any other sport — power-based TSS is the native load currency here.

---

## 1. Central philosophy

Cycling is a **power-output sport on a non-impact platform**. Two consequences shape
everything:

- Performance is governed by the **power an athlete can sustain relative to body mass
  (W/kg)** and to aerodynamic drag. Flat/TT performance is dominated by absolute power
  vs. drag; climbing is dominated by W/kg.
- Because pedaling is **non-impact**, cyclists tolerate far higher training volume than
  runners — the limiter is rarely tissue breakdown and more often saddle time, fueling,
  systemic fatigue, and (long-term) recovery capacity. Volume ceilings from the running
  modules do **not** transfer; cyclists can sustain much larger weekly hours/TSS.

The base-first, polarized logic of the core document still holds: a large aerobic
foundation, with a small potent dose of high intensity layered on toward the event.

## 2. Power-based training and FTP

The anchor metric is **Functional Threshold Power (FTP)** — the highest power sustainable
in a quasi-steady state for ~45–60 min, a practical proxy for the lactate/anaerobic
threshold. Nearly all prescription is expressed as **% of FTP**.

When a power meter isn't available, HR-based zones are a fallback, but power is strongly
preferred in cycling because it's instantaneous, reproducible, and immune to the lag and
drift that make HR unreliable for short efforts.

## 3. Power zones (Coggan 7-zone model)

| Zone | Name | % FTP | Role |
|---|---|---|---|
| 1 | Active Recovery | < 55% | Recovery spins, between-interval easy |
| 2 | Endurance | 56–75% | **Aerobic base** — the bread and butter; fat oxidation, mitochondrial density |
| 3 | Tempo | 76–90% | Aerobic durability, "fast endurance" |
| **SS** | Sweet Spot | ~88–94% | High-yield threshold-adjacent work (see §6) |
| 4 | Lactate Threshold | 91–105% | Raise FTP directly |
| 5 | VO2max | 106–120% | Aerobic ceiling; 3–8 min efforts |
| 6 | Anaerobic Capacity | 121–150% | Short, hard, repeatable efforts (30s–3 min) |
| 7 | Neuromuscular Power | max | Sprints, < ~15 s |

Most volume lives in **Zone 2**. Zone 3/Sweet Spot is efficient but, in excess,
recreates the grey-zone trap (core §4) — use it deliberately, not by default.

## 4. Key power metrics (for reading and prescribing load)

- **FTP** — the anchor; re-test/re-estimate every ~4–6 weeks of focused training.
- **Normalized Power (NP)** — physiological-cost-weighted average power for variable
  rides; better than average power for rides with surges/climbs.
- **Intensity Factor (IF)** — NP ÷ FTP; the ride's relative intensity (a 1-hour all-out
  ≈ 1.0).
- **TSS** — IF² × duration(hr) × 100; the native Coggan load unit Arete already uses.
- **Variability Index (VI)** — NP ÷ avg power; ~1.0 = steady (good TT pacing), high =
  surgy (road-race/crit demand). Useful for matching training to event pacing style.
- **W/kg** — the climbing/power-to-weight currency; the key metric for climbers.
- **Critical Power (CP) & W′** — CP ≈ sustainable aerobic power ceiling; W′ ≈ the finite
  "battery" of work available above CP. Useful for modeling repeated hard efforts and
  for athletes who prefer the CP framework to FTP.

## 5. FTP / threshold testing protocols

- **20-min test** — after warm-up, a maximal 20-min effort; FTP ≈ 95% of 20-min average
  power. The classic field test.
- **Ramp test** — power steps up each minute to exhaustion; FTP ≈ 75% of the best 1-min
  power. Shorter and lower-fatigue; can over/under-estimate for athletes with unusual
  anaerobic profiles.
- **Two-effort / 8-min** — two 8-min maximal efforts, FTP ≈ 90% of the average; a middle
  ground.
- Re-test under consistent conditions (trainer or same course) so FTP changes reflect
  fitness, not terrain. Modern devices/platforms also estimate FTP passively from ride
  data — acceptable as a tracking signal between formal tests.

## 6. Intensity distribution and the sweet-spot question

Two defensible models; choose by athlete and timeline:

- **Polarized** (core default): ~80% Z1–Z2, minimal Z3, ~20% Z4+. Best supported for
  well-trained athletes and for raising the ceiling.
- **Sweet Spot Training (SST)** (~88–94% FTP): high training-stress-per-time, valuable
  when **time is limited** or to build threshold durability in the base/build phases.
  The trade-off is fatigue cost and grey-zone risk if overused — periodize it as a tool,
  not a permanent home.

Practical default: **polarized for athletes with ample training time; sweet-spot-weighted
for time-crunched athletes**, with VO2max work concentrated in the build/specific phase
regardless.

## 7. Workout types

- **Endurance ride (Z2)** — long steady aerobic riding; the foundation. Cyclists can go
  long here (2–6+ hr) thanks to the non-impact platform.
- **Tempo / Sweet Spot** — 2–4 × 10–20 min at ~76–94% FTP; aerobic durability and
  threshold-adjacent stress, time-efficient.
- **Threshold (Z4)** — e.g. 2–3 × 15–20 min at ~95–105% FTP; raises FTP directly.
- **VO2max intervals (Z5)** — 3–8 min at ~106–120% FTP (e.g. 5 × 4 min); aerobic ceiling.
- **Rønnestad short intervals** — e.g. **30 s on / 15 s off** repeated in blocks; evidence
  suggests these accumulate more time near VO2max with lower perceived strain than
  classic long intervals. A high-value VO2max stimulus.
- **Anaerobic / repeated efforts (Z6)** — 30 s–3 min hard, repeated; for road-race and
  crit demands.
- **Sprints (Z7)** — short maximal neuromuscular efforts; for finishing speed.
- **Over-unders** — alternating just-below and just-above FTP (e.g. 2 min @ 95% / 1 min
  @ 105%); trains lactate clearance and surge tolerance for road racing.
- **Cadence drills** — high-cadence spin-ups and low-cadence/big-gear torque work for
  neuromuscular range and on-bike strength.

## 8. Periodization

Friel-style sequence, adapted to event:

| Phase | Focus |
|---|---|
| **Prep / Transition** | Re-establish routine, general strength, easy volume |
| **Base** | Maximize Z2 aerobic volume; build durability; tempo/sweet-spot; max-strength block in the gym; cadence work |
| **Build** | Threshold + VO2max work raised; event-specific intervals; reduce gym to maintenance |
| **Peak / Specific** | Sharpen the event-specific quality (TT steadiness, race surges, climbing repeats); race-intensity simulation |
| **Race / Taper** | Reduce volume, retain intensity; freshen for the event |

Block periodization (core §2) is popular and well-supported in cycling — e.g. a
concentrated VO2max block of several sessions across ~1–2 weeks can produce a sharper
ceiling jump than spreading the same sessions thin.

## 9. Event-specific guidance

- **Time trial / gran fondo (steady)** — train **steady threshold and sweet-spot**
  durability; target a low VI (smooth pacing); rehearse the TT position (which costs
  power but saves drag — train in it). FTP and aerodynamics dominate.
- **Road race** — **surgy, repeated-effort** demand: over-unders, anaerobic repeats,
  and the ability to recover between hard efforts (high CP *and* W′). Pacing is variable
  (high VI); train to tolerate repeated matches being burned.
- **Criterium** — repeated short sprints out of corners + sustained high power; emphasize
  anaerobic capacity, sprint repeatability, and bike handling.
- **Climbing / mountainous events** — **W/kg is king**: sustained threshold/VO2max climbs,
  and (carefully) body-composition as a lever. Long sustained-climb repeats in the
  specific phase.
- **Stage races / multi-day** — **fatigue resistance / "durability"**: the ability to
  hold power *after* large accumulated kJ. Train it with hard efforts placed late in long
  rides (e.g. threshold blocks after 2–3 hr of endurance), not just when fresh.

## 10. Volume, durability, and fueling

- **Volume tolerance is high** (non-impact) — weekly hours/TSS can substantially exceed
  the running modules' ceilings. Progress still gradually (core §5 % guidance applies to
  the *rate of change*, even if the absolute numbers are larger), with deloads.
- **Durability / fatigue resistance** is an increasingly recognized determinant: power at
  threshold after 2,000–3,000+ kJ of work predicts real-world performance better than
  fresh FTP alone. Build it with long rides that include quality efforts late.
- **Fueling** is performance-limiting on long rides — rehearse high carbohydrate intake
  rates (often 60–90+ g/hr for long events) during training so the gut adapts; bonking is
  a fueling failure, not a fitness failure.

## 11. Cadence, aerodynamics, position

- **Cadence** is individual; train a range (low-cadence torque work and high-cadence
  spin-ups) rather than enforcing a single number.
- **Aerodynamics** is the dominant resistance at racing speeds on flat ground — position
  and equipment can outweigh fitness gains, but an aero position must be *trained* because
  it can reduce sustainable power until adapted.
- **Drafting** cuts power demand sharply in a group/race; pure power numbers from solo
  training don't translate 1:1 to bunch racing tactics — include some group/variable-pace
  riding for race-specificity.

## 12. Strength & conditioning for cyclists

Integral even for single-sport cyclists (core §8), with two cycling-specific reasons
beyond economy:

- **Heavy strength training improves cycling performance** — Rønnestad's body of work
  shows heavy lower-body strength (e.g. squats, leg press, ~4–10 RM) improves sustained
  power, sprint power, and time-trial performance, and delays fatigue, **without
  meaningful mass gain** at controlled volumes. One of the best-supported off-bike
  interventions for cyclists.
- **Bone health** — cycling is **non-weight-bearing**, so cyclists are prone to **low
  bone mineral density**. Resistance training and some impact/plyometric exposure are a
  genuine health priority, not just a performance add-on — flag this for cyclists who do
  little else weight-bearing.
- **Periodization** (core §8): general strength → heavy max-strength block in base →
  maintenance (≈1×/week) through build and into the season; don't drop it entirely, as
  the gains fade without maintenance. Also include trunk/hip stability for position and
  power transfer.

## 13. Tapering (cycling specifics)

- Typically ~7–14 days depending on event length; cut volume ~30–50%, **keep intensity**
  with short threshold/VO2max touches and openers (a few brief hard efforts the day
  before) to stay sharp.
- Cyclists generally taper well retaining frequency and some intensity; the non-impact
  platform means they can keep riding easy without the tissue-recovery concerns runners
  have.

## 14. Quick session library (for plan generation)

- **Endurance ride (Z2)** — long steady aerobic; foundation; 1.5–6+ hr.
- **Sweet Spot** — 2–4 × 10–20 min @ ~88–94% FTP; time-efficient threshold-adjacent.
- **Threshold (Z4)** — 2–3 × 15–20 min @ ~95–105% FTP; raises FTP.
- **VO2max** — 5 × 4 min @ ~110–120% FTP; aerobic ceiling.
- **Rønnestad 30/15s** — blocks of 30 s on / 15 s off; high time-at-VO2max.
- **Over-unders** — alternating ~95% / ~105% FTP; surge & clearance tolerance.
- **Anaerobic repeats** — 30 s–3 min hard, repeated; race-specific.
- **Sprints** — short maximal neuromuscular efforts.
- **Durability ride** — long endurance with threshold blocks placed late (after big kJ).
- **Strength session** — heavy lower-body (base) → maintenance (in-season); + bone/trunk.

## 15. Override notes vs. core document

- **Power-based TSS is the native load currency** — this module aligns directly with
  Arete's existing Coggan PMC; no vert correction is needed (unlike trail), because power
  already captures gradient cost intrinsically.
- **Volume ceilings are much higher** than the running modules — apply core §5's *rate-of-
  change* guidance, not the running modules' absolute hours.
- **FTP re-testing** drives zone re-derivation every ~4–6 weeks; treat it like trail's
  AeT re-tests or road's VDOT updates.
- **Bone-density strength/impact work** is a health flag specific to this non-weight-
  bearing sport — surface it even for performance-focused athletes.
- For **stage races / long events**, prioritize **durability** (power after accumulated
  kJ) over fresh FTP in the specific phase.
