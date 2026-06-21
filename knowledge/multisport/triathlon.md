# Arete — Multisport Module: Triathlon

> Scientific basis: Joe Friel, *The Triathlete's Training Bible* (the canonical text);
> Friel & Vance (eds.), *Triathlon Science*; Matt Dixon, *The Well-Built Triathlete*
> (recovery- and durability-centric); Jim Vance, *Triathlon 2.0* (data-driven planning);
> plus the concurrent-training / interference-effect literature. This module sits on top
> of `core_training_science.md`.
>
> **Precedence (core §12):** when an athlete races triathlon, load THIS module rather
> than the three single-sport files independently. This module governs how swim, bike,
> and run **combine**. For within-discipline technique and session detail it defers to —
> and the generator may also load — `swimming.md`, `road_cycling.md`, and
> `road_running.md`; but where combined-load, sequencing, or weighting questions arise,
> **this module wins**.

---

## 1. Central challenge — concurrent training of three sports

Triathlon is not "swim training + bike training + run training." Its defining problem is
**managing the combined load of three disciplines** against one recovery budget and a
finite weekly time allowance, while respecting the **interference effect** (concurrent
high volumes of different modalities, and concurrent strength + endurance, can blunt
adaptation in each). Every planning decision flows from that constraint.

Two corollaries:
- **Recovery management is paramount.** Triathletes carry the highest overtraining and
  overuse risk of any module here because fatigue accumulates across three sports. The
  plan must protect recovery aggressively (Dixon's central thesis: recovery is the
  limiter, not work capacity).
- **Time allocation is a real optimization**, not an afterthought. Hours spent in one
  discipline are unavailable to the others; the plan distributes a scarce budget.

## 2. Combined load management — three currencies, one body

Each discipline has its own native load currency (per the single-sport modules):

- **Swim** → CSS pace per 100 m (`swimming.md`)
- **Bike** → power / FTP-based TSS (`road_cycling.md`)
- **Run** → pace/VDOT and HR (`road_running.md`)

The generator should:
- **Track systemic (cardiovascular) load across all three combined** — this is what the
  recovery budget actually responds to. A normalized cross-sport load (e.g. per-sport TSS
  summed into a combined PMC) is the right systemic view, since TSS is designed to be
  modality-comparable.
- **Track local (musculoskeletal) load per discipline separately** — because the tissues
  differ. Run impact load and bike-specific muscular load and shoulder load don't
  substitute for one another (core §12).
- **Exploit low-overlap recovery:** swimming is non-impact (`swimming.md` §10) and can
  serve as recovery-supporting aerobic volume on days the legs need to unload from
  running/cycling. Bike and run share more leg overlap and should be sequenced with care
  (§8).

## 3. Discipline weighting — the limiter framework

Friel's "limiter" logic: **train each discipline in proportion to (its importance to the
race result) × (how weak the athlete is in it)** — not equally.

- **Bike** usually occupies the **largest share of race time** (especially long course)
  and is where time is most efficiently gained — often the highest training priority for
  results.
- **Run** typically **determines the finish** (run-off-the-bike fade decides places);
  the run leg's quality, performed fatigued, is decisive.
- **Swim** is the **smallest share of total race time** for most age-groupers but has the
  **highest technique barrier** and the longest skill-decay if neglected — so it needs
  *frequency* even when it doesn't merit the most *hours* (see §7).

Identify the athlete's limiter relative to their race and weight the plan toward it,
while maintaining the other two.

## 4. Race-format specificity

Format reshapes volume, intensity, and emphasis substantially:

| Format | Approx. distances | Emphasis |
|---|---|---|
| **Sprint** | 0.75 km / 20 km / 5 km | Higher intensity, threshold/VO2max, fast transitions; smaller volume |
| **Olympic** | 1.5 km / 40 km / 10 km | Threshold-centric; balance of intensity and aerobic volume |
| **70.3 (Half)** | 1.9 km / 90 km / 21.1 km | Aerobic durability, sustained tempo/threshold, fueling rehearsal |
| **Ironman (Full)** | 3.8 km / 180 km / 42.2 km | Aerobic dominance, very high volume, durability & fueling are *the* determinants; intensity is modest |

- **Short course (sprint/Olympic)** — intensity-led; tolerates more VO2max/threshold work;
  draft-legal racing (where applicable) demands surge tolerance and pack skills on the
  bike.
- **Long course (70.3/Ironman)** — volume- and durability-led; the specific phase is about
  holding sustainable power/pace for hours and **fueling without GI failure**; the long
  brick is the cornerstone session.

## 5. Brick workouts — the signature session

A **brick** trains discipline transitions back-to-back, most importantly **bike → run**.
Running off the bike feels distinctly different (the "jelly legs" of overlapping muscle
recruitment), and adapting to it is a trainable, specific skill that pool/track/road
training alone doesn't build.

- **Bike→run brick** — the priority; a bike session immediately followed by a run, from
  short (transition-rehearsal) to long (race-simulation for long course).
- **Swim→bike brick** — less common but useful for race-day sequencing and open-water-to-
  bike transition.
- Place key bricks in the **build/specific phase**; long-course athletes build toward a
  long brick that rehearses race fueling and pacing across two disciplines.

## 6. Frequency principle

Per `swimming.md`, **feel for the water decays fast** — so swim *frequency* (e.g. 2–4×/
week, even if some are short technique swims) matters more than total swim hours for most
triathletes. More broadly, **touching each discipline regularly** maintains skill and
neuromuscular feel better than concentrating each into a single weekly block. This argues
for a higher-frequency, shorter-session weekly structure than a single-sport athlete would
use.

## 7. Interference effect and session sequencing

Concurrent training has real interaction effects the plan must sequence around:

- **Don't bury a key session behind a fatiguing one** in a way that compromises its
  quality. If a hard run is the day's priority, don't precede it with a hard bike (outside
  a deliberate brick).
- **Separate hard same-tissue sessions** — hard bike and hard run both load the legs;
  space them or alternate hard/easy across disciplines so each leg-intensive session lands
  on relatively fresh legs.
- **Strength + endurance interference** — heavy strength and high-intensity endurance
  compete; separate them by several hours where possible, and place strength so it doesn't
  blunt the week's key endurance session.
- **Use swimming as the unloading modality** — its non-impact nature lets it fill aerobic
  volume on leg-recovery days.
- **Hard days hard, easy days easy** still applies across the *combined* week, not within
  each sport in isolation — a "polarized" combined load.

## 8. Periodization across three disciplines

Apply the core phase structure to the *combined* plan, with discipline emphasis shifting
through the phases:

| Phase | Combined focus |
|---|---|
| **Prep/Base** | Aerobic volume across all three; heavy swim technique investment; max-strength block; raise each discipline's threshold (CSS/FTP/threshold pace); establish frequency |
| **Build** | Discipline-specific intensity (threshold → VO2max as format demands); introduce bricks; reduce strength to maintenance; bias toward the limiter |
| **Specific/Peak** | Race-specific bricks, race-pace work, open-water and pacing/fueling rehearsal; format-specific (durability for long course, sharpness for short) |
| **Taper** | Multi-discipline taper (§11) |

Block periodization can be applied per-discipline (e.g. a swim-focused block) but always
under the combined-load ceiling — concentrating one sport means easing the others, not
adding on top.

## 9. Discipline notes in the triathlon context

- **Swim** — open-water skills (sighting, drafting, wetsuit; `swimming.md` §9) are
  race-specific; pool fitness alone is insufficient. Swim is also where the smallest
  fitness return per hour lives, reinforcing the frequency-over-volume approach.
- **Bike** — the engine of the race; aero position must be *trained* (it costs power until
  adapted; `road_cycling.md` §11). For long course, **durability** (power late in long
  rides) and fueling are decisive. Draft-legal short course needs pack/surge skills.
- **Run** — the run is performed **fatigued off the bike**; train it that way via bricks.
  Run volume is the most injury-prone of the three (impact), so it's often the discipline
  whose volume is most constrained by durability — quality and brick-specificity can
  matter more than raw run mileage.

## 10. Fueling, pacing, and transitions

- **Fueling** is a race-deciding, trainable system, especially long course — rehearse
  carbohydrate intake rates across the bike and run during long bricks so the gut adapts;
  most long-course "blow-ups" are fueling/pacing failures, not fitness failures.
- **Pacing discipline** — going too hard on the bike wrecks the run; the specific phase
  should rehearse *negative-effort* discipline (controlled bike → strong run).
- **Transitions (T1/T2)** — small but free time; rehearse them, particularly for short
  course where they're a meaningful fraction of the result.

## 11. Tapering

A triathlon taper must **taper all three disciplines**, but they don't taper identically:
swimming tolerates (and benefits from) a fuller volume cut with retained speed
(`swimming.md` §13); bike and run follow the core volume-down/intensity-retained pattern.
Typical overall taper is ~10–21 days scaled to format (longer for Ironman). Keep
frequency and short race-pace touches in each discipline so feel is retained across all
three.

## 12. Recovery and overtraining risk (highest of any module)

Because load stacks across three sports, this module flags recovery most strongly:

- Protect genuine recovery days/weeks; resist the temptation to "just add" a session in a
  neglected discipline on top of a full week.
- Watch combined negative TSB plus performance decline across *any* discipline as an
  overtraining signal (core §6).
- HRV/resting-HR override signals (core §6) are especially valuable here for catching
  combined overload before it becomes non-functional overreaching.

## 13. Strength & conditioning (shared, time-constrained)

S&C remains integral (core §8) but is **shared across the three sports under a tight time
budget**, so prioritize the highest-transfer, most-protective work:

- **Shoulder stability** (swim injury prevention; `swimming.md` §12) +
- **Lower-body max strength** (transfers to bike power and run economy; Rønnestad-style,
  no mass gain; `road_cycling.md` §12 / `road_running.md` §9) +
- **Trunk/hip stability and single-leg control** (run durability, position, power transfer).
- **Periodization**: max-strength block in base → maintenance (~1×/week) in build/peak.
- With limited time, **one to two well-chosen full-body strength sessions** covering
  shoulder + posterior chain + legs + core beat sport-by-sport isolation.

## 14. Example combined microcycle (illustrative, build phase, Olympic/70.3)

A template the generator can adapt — not prescriptive:

- **Mon** — Swim technique/aerobic (easy legs); optional strength (maintenance)
- **Tue** — Hard bike (threshold/VO2max); short easy run off bike (mini-brick)
- **Wed** — Swim threshold (CSS set); easy aerobic run
- **Thu** — Hard run (key run session, fresh-ish legs); easy spin
- **Fri** — Swim aerobic + technique; rest or mobility (recovery emphasis)
- **Sat** — Long bike → run **brick** (the week's cornerstone)
- **Sun** — Long run *or* long easy ride (alternate weekly); swim optional easy

Note the structure: hard bike and hard run are separated (Tue/Thu) so each lands on
relatively fresh legs; swimming fills aerobic volume on leg-recovery days; the brick is
the weekend centerpiece; recovery is actively protected (Fri).

## 15. Override notes vs. core and single-sport modules

- **This module governs combined load, sequencing, weighting, and taper integration;**
  the single-sport modules govern within-discipline technique and session design.
- **Track systemic load combined, local load per discipline** (core §12) — never naively
  sum as if one sport.
- **Frequency over volume** for swim (and for skill maintenance generally).
- **Sequence around the interference effect** — separate same-tissue hard sessions;
  separate heavy strength from key endurance.
- **Recovery is the binding constraint** — when in doubt, this module errs toward
  unloading more than a single-sport plan would.
- **Brick specificity** (bike→run) is unique to this module and is a first-class key
  session, especially for long course.
