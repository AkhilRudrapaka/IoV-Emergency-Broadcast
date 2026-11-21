# Preprocessing Report: VeReMi NextGen InTAS_highway_2 (final, v2)

**Date:** 18 November 2026.
**Status: OK.** The pipeline summary and `DATASET_TRACKS_MANIFEST.json` both say `OK`, with an empty failure list.
No model was trained.

This replaces the provisional v1 report, whose `FAILED` status came from the label-semantics question. That question was
resolved in `VEREMI_GENERATOR_LABEL_INVESTIGATION.md` and settled by the approved decisions below.

## 1. Approved decisions and how they are implemented

| Decision | Implementation |
|---|---|
| Primary track = 14 attacks | `veremi/preprocess.py` → `POLICY` / `PRIMARY` (11 consistent attacks + zeroSpeedReport, reversedHeading, suddenStop) → `processed/v2/primary/` |
| suddenConstantSpeed kept separate | `EVAL_ONLY` → `processed/v2/eval_only/`. `load()` returns it only when `track="eval_only"` is passed |
| Baseline kept separate and unlabelled | `processed/v2/unlabelled_baseline/` has no `y` array, and `load()` refuses it |
| Official labels unchanged; nothing relabelled or removed | `y` = each reception's own `attacker` field. Rows and class counts equal the acquisition manifest for all 48 archive-splits; 0 rejected |
| Per-attack provenance | Every row carries `attack`; every table carries `track` and `split`. Files are one per archive and split |
| Four caveat attacks reported separately | `report_separately` is set for zeroSpeedReport, reversedHeading, suddenStop and suddenConstantSpeed, with the caveat text in the tracks manifest |
| Diagnostic label for suddenConstantSpeed | `y_diag_documented_rule`, only in eval-only tables, never in `X` (§4) |

## 2. Final record counts

One row is one received message.

| Track | Split | Rows | Genuine (y=0) | Attacker (y=1) |
|---|---|---|---|---|
| **primary** (14 archives) | Train | 581,396 | 441,911 | 139,485 |
| | Validation | 276,551 | 210,930 | 65,621 |
| | Test | 675,720 | 521,887 | 153,833 |
| | **Total** | **1,533,667** | **1,174,728** | **358,939** |
| **eval_only** (suddenConstantSpeed) | Train / Validation / Test | 37,701 / 17,977 / 44,259 | 36,173 / 17,412 / 42,688 | 1,528 / 565 / 1,571 |
| **unlabelled_baseline** | Train / Validation / Test | 37,701 / 17,977 / 44,259 | — | — |

**Reconciliation:** primary + eval_only = 1,633,604 labelled rows, which is the acquisition manifest total. The baseline holds 99,937 rows. No record was rejected or removed. Per-archive rows and labels per split are in `DATASET_TRACKS_MANIFEST.json`, each file with its MD5.

## 3. Label verification against the documented generator rules

Every reception is checked against its archive's documented labelling rule (`documented_label()`). The rules come from
`Generator/attackGenerator/attackGenerator.py`, commit `acda994`. Original values come from the ground-truth file of
the same split, and are used **only for this check**. A reception counts as "modified" when its content differs from
its ground-truth message.

Columns: "Modified receptions" = receptions whose content differs from ground truth; "Rule: match / mismatch / not
decidable" covers all receptions; "Label / content differ" counts cases where one transmission differs between receivers.

| Archive | Track | Modified receptions | Rule: match / mismatch / not decidable | Label / content differ | Canonical rows T / V / Te |
|---|---|---|---|---|---|
| accelerationMultiplication | primary | 19,446 | 99,937 / 0 / 0 | 0 / 0 | 19,186 / 7,023 / 18,892 |
| constantPositionOffset | primary | 19,788 | 99,937 / 0 / 0 | 0 / 0 | 19,186 / 7,023 / 18,892 |
| constantSpeedOffset | primary | 20,428 | 99,937 / 0 / 0 | 0 / 0 | 19,186 / 7,023 / 18,892 |
| dataReplay | primary | 18,496 | 99,937 / 0 / 0 | 0 / 0 | 19,186 / 7,023 / 18,892 |
| dosAttack | primary | 42,192 | 42,192 / 0 / 99,937 ¹ | 0 / 0 | 27,625 / 10,153 / 26,286 |
| feignedBraking | primary | 10,064 | 99,937 / 0 / 0 | 0 / 0 | 19,186 / 7,023 / 18,892 |
| positionMirroring | primary | 21,547 | 99,937 / 0 / 0 | 0 / 0 | 19,186 / 7,023 / 18,892 |
| randomPositionOffset | primary | 19,278 | 99,937 / 0 / 0 | 0 / 0 | 19,186 / 7,023 / 18,892 |
| randomSpeedOffset | primary | 19,078 | 99,937 / 0 / 0 | 0 / 0 | 19,186 / 7,023 / 18,892 |
| **reversedHeading** | primary | 19,470 | 99,923 / **14** ² / 0 | **19** / 0 | 19,186 / 7,023 / 18,892 |
| **suddenStop** | primary | 10,001 | 99,937 / 0 / 0 | **679 / 759** ³ | 19,186 / 7,023 / 18,892 |
| timeDelayAttack | primary | 19,857 | 99,937 / 0 / 0 | 0 / 0 | 19,186 / 7,023 / 18,892 |
| trafficCongestionSybil | primary | 92,357 | 192,294 / 0 / 0 | 0 / 0 | 37,739 / 13,835 / 35,687 |
| **zeroSpeedReport** | primary | 20,035 | 99,924 / **13** ² / 0 | **20** / 0 | 19,186 / 7,023 / 18,892 |
| **suddenConstantSpeed** | eval_only | 10,214 | 99,937 / 0 / 0 ⁴ | **331 / 889** ³ | 19,186 / 7,023 / 18,892 |

1. **dosAttack:** an unmodified message is labelled 1 if its sender is a flooding attacker and 0 otherwise. The attacker set is not recorded, so the rule cannot decide those receptions. All 42,192 modified receptions (flood copies) match, and the acquisition audit found 0 dosAttack senders with mixed labels.
2. **zeroSpeedReport and reversedHeading:** this is the known `sender_lookup` defect (generator lines 270–275 and 351–356).
   - The pipeline tolerates at most 0.1 % of the archive's modified receptions, the bound stated in the investigation: 20 and 19 allowed. It also requires every mismatch to be "official 0 where the documented rule says 1", the only direction the defect can explain.
   - Both conditions hold. The tolerance is judged per archive, as the investigation measured it. A per-split check would have failed reversedHeading/Test (10 of about 8,600). I did not loosen the bound to pass it; I aligned the check with how the bound was defined.
3. **suddenStop and suddenConstantSpeed:** the stop/freeze state is set in receiver-file processing order, so one broadcast can differ between receivers. The policy allows this difference only for these attacks. Each reception's label still matches the code rule for its own content.
4. **suddenConstantSpeed:** checked against the **code's** one-sided rule (line 332), which the official label follows exactly.

For every other archive the policy allows no mismatch and no cross-receiver difference, and none occurred.

## 4. suddenConstantSpeed diagnostic label

- **Column:** `y_diag_documented_rule` (int8), in `eval_only/suddenConstantSpeed__<split>.npz` only. It is not in `X`, not in any primary table, and not returned by `load(track="primary")`.
- **Rule:** the documented rule, `|actual speed − frozen speed| > 1 m/s` (`Documentation/Post-Processing/Attack Generator/README.md`, lines 101–103).
- **Derivation** (`diagnostic_label()`):
  - A reception is frozen exactly when its reported speed differs from the ground-truth speed of the same message. This attack modifies nothing else, and every reception of this archive has a ground-truth message.
  - The frozen value is the reported speed. The actual speed is the ground-truth speed, the same value the generator compares.
  - Unmodified receptions get 0.
  - No hidden generator state (freeze time, processing order) needs to be reconstructed, so the derivation is reliable.

| Split | Official 1, diagnostic 1 | Official 0, diagnostic 1 | Official 0, diagnostic 0 | Official 1, diagnostic 0 |
|---|---|---|---|---|
| Train | 1,528 | 1,309 | 34,864 | 0 |
| Validation | 565 | 683 | 16,729 | 0 |
| Test | 1,571 | 912 | 41,776 | 0 |

The diagnostic label adds exactly the 2,904 receptions the investigation identified: frozen speed more than 1 m/s *above* the actual speed. It never removes an official attack label.

**Limitations of the diagnostic label:**
- It is derived from ground truth, so it may be used for diagnostic evaluation only.
- It does not undo the processing-order effect: receptions that were never frozen stay 0.
- It reflects the documented intent, not the published label.

## 5. Message identity and receiver-level handling

- **Row:** one receiver-level observation. Each receiver's history starts empty in each split and is processed in `rcvTime` order.
- **Transmission key:** (`sender_id`, `messageID`, `sendTime`). It is unique per reception at a receiver in every archive (the policy check fails on any repeat). `messageID` alone repeats in dosAttack (flood-copy ID collisions, generator lines 382–392 and 697) and in trafficCongestionSybil.
- **`is_first_reception`** marks one canonical row per transmission. Canonical rows are valid as one row per broadcast only where all receptions agree: every archive except suddenStop and suddenConstantSpeed. For reversedHeading and zeroSpeedReport, 19 and 20 receptions disagree in label with their transmission's first reception; the summary records them.
- **Splits:** 0 shared transmissions **and** 0 shared underlying messages (`sender_id`, `messageID`) between Train, Validation and Test, checked over all three tracks.

## 6. Repeated genuine messages across attack archives

- **Why they exist:** every archive is built from the same base traffic, so in a given split an honest vehicle's reception appears unchanged in up to 14 primary archives. (Attackers are re-drawn per generator run, so which vehicles stay honest differs between archives.)
- **The flag:** `dup_of_earlier_primary_archive` is True when the same (`receiver`, `sender_id`, `messageID`, `sendTime`) was already seen with **identical content and label** in an earlier primary archive of the same split. Archives are processed in alphabetical order, which is stable. Nothing is deleted.

| Split | Primary rows | Flagged duplicates | Not flagged |
|---|---|---|---|
| Train | 581,396 | 329,904 | 251,492 |
| Validation | 276,551 | 148,856 | 127,695 |
| Test | 675,720 | 392,178 | 283,542 |

- **Use:**
  - Per-attack evaluation keeps every row of its archive.
  - A pooled model can be trained or evaluated without the flagged rows, so honest traffic is not counted up to 14 times.
  - The first archive alphabetically (accelerationMultiplication) carries the unflagged copies. That choice is arbitrary but documented.
- **Leakage:** duplicates exist only *within* a split; across splits the overlap is 0. Repeated messages cannot leak between Train and Test.

## 7. Features (`veremi/feature_schema.json`, version 2, MD5 `64731b0fca7173087dbbbd262312ac36`)

The 24 features are unchanged from v1. Each is computable by the receiving vehicle when the message arrives, from three
sources:
- the message itself
- the receiver's own state
- earlier messages the same receiver got from the same pseudonym

| # | Feature | Calculation | Missing |
|---|---|---|---|
| 0–1 | `spd`, `acl` | reported speed and acceleration | never |
| 2 | `dist_tx_rx_m` | distance, reported sender position to receiver's own position | never |
| 3 | `abs_rel_speed` | abs(reported speed − receiver speed) | never |
| 4 | `heading_diff_rx_deg` | angle between sender and receiver headings | never |
| 5 | `delay_ms` | rcvTime − sendTime | never |
| 6–8 | `has_prev`, `n_prev`, `rate_1s` | history presence, count, messages in the last 1 s | never |
| 9–10 | `dt_send_s`, `dt_rcv_s` | time since the previous message of this pseudonym | NaN without history |
| 11–13 | `dpos_m`, `implied_speed`, `speed_residual` | position change, implied speed, abs(implied − mean reported speed) | NaN without history (12–13 also if dt ≤ 0) |
| 14–16 | `dspd`, `implied_acl`, `acl_residual` | speed change, implied acceleration, abs(implied − mean reported acceleration) | as above |
| 17–18 | `dhed_deg`, `yaw_rate_dps` | heading change and rate | NaN without history |
| 19 | `bearing_residual_deg` | direction of travel vs heading (north = 0, clockwise) | NaN without history or if dpos < 1 m |
| 20 | `pos_pred_error_m` | distance from the dead-reckoned position | NaN without history |
| 21–23 | `speed_residual_mean5`, `pos_pred_error_max5`, `dt_send_min5` | over the last 5 messages of the pseudonym | NaN if none defined |

The full source, calculation, type and missing-value rule of each feature are in the schema file.

**Schema corrections in version 2:**
- **`*_noise` exclusion reason.** These are the *realised* sensor error, not a transmitted confidence: the generator recovers the true position as `reported − pos_noise` (`attackGenerator.py:179-188`). A receiver cannot know them.
- **`distance_to_road_edge`.** It is computed after the attacks from the *reported* position and the SUMO road map (`enrichMsgs.py:158-163`). It is therefore available only to a receiver with the same map. It is kept as `road_edge_dist` metadata for an explicitly labelled map-based variant, never in `X`.
- **New note:** timeDelayAttack shifts `sendTime` and `rcvTime` together (`attackGenerator.py:199-200`), so `delay_ms` carries no signal for it by construction.

**Still excluded:**

| Field | Reason |
|---|---|
| `attacker` and the diagnostic label | The targets |
| Ground-truth files | Verification only |
| `sender_id`, receiver ID, `sender_alias` value, `messageID` | Identities; the alias is used only to group a receiver's history |
| Absolute times, positions and headings | Identify the split, area and road orientation |
| `driversProfile` | Not observable by a receiver; a selection shortcut |

## 8. Leakage and integrity checks

| Check | Result |
|---|---|
| Official labels unchanged | Pass: class counts equal the acquisition manifest for all 48 archive-splits |
| No unexplained deletion | Pass: rows + rejected (0) = records, everywhere |
| Primary = exactly the 14 approved attacks; suddenConstantSpeed separate | Pass (integration test) |
| Splits separate | Pass: 0 shared transmissions and 0 shared messages for all split pairs |
| No ground-truth or label information in `X` | Pass: features never read ground truth; the diagnostic label is stored outside `X` (test) |
| Transforms fitted on Train only | Pass: none are fitted |
| Causal features (no future information) | Pass (test) |
| Each archive's labels follow its documented rule | Pass, within the documented defect tolerances (§3) |
| Baseline never usable as labelled data | Pass: no `y`; `load()` refuses it (test) |

## 9. Tests

- **`python -m pytest veremi -q`: 20 passed.**
  - 7 acquisition safety checks.
  - 12 preprocessing unit tests: labels, string-typed baseline records, both ground-truth schemas, each documented label rule, the suddenStop branches, the one-sided rule against the diagnostic label, the policy tolerances and their direction, causality, kinematics, canonical and duplicate flags, track separation, and feature exclusions.
  - 1 integration test on the real v2 output, which now requires status `OK`.
- **`python -m pytest validation -q`: 105 passed.** The existing project suite is unaffected.

## 10. Time, memory and reproduction

- **Run:** 76.8 s for all 16 archives, peak 354.5 MB resident. Only one archive-split is held at a time, plus one ground-truth split and the per-split duplicate index.
- **Output:** 113.8 MB of compressed `.npz` in `<data>/processed/v2/` (`<data>` = `<repo>/../../data/veremi_nextgen/InTAS_highway_2`, the dataset folder outside the repository):
  - `primary/` (42 files, 100.4 MB)
  - `eval_only/` (3 files, 6.8 MB)
  - `unlabelled_baseline/` (3 files, 6.6 MB)
  - `preprocess_summary.json`

From the repo root (Git Bash), with `D="../../data/veremi_nextgen/InTAS_highway_2"` (that is, `<data>`):

```bash
python -m pytest veremi -q -p no:cacheprovider
python -I veremi/preprocess.py --data-dir "$D" --out "$D/processed/v2" --schema veremi/feature_schema.json \
    --manifest DATASET_MANIFEST_InTAS_highway_2.json --tracks-manifest DATASET_TRACKS_MANIFEST.json --overwrite
python -m pytest validation -q -p no:cacheprovider
```

Loading for later blocks: `load(out, "Train")` returns the primary track, and `load(out, "Test", track="eval_only")`
returns suddenConstantSpeed. Each returned dict holds `X`, `y`, `attack`, the metadata, `feature_names`, `track` and
`split`.

## 11. Files

| File | Change |
|---|---|
| `veremi/preprocess.py` | Rewritten: tracks, documented-rule policy and verification, diagnostic label, duplicate flag, track manifest, `load(track=…)` |
| `veremi/features.py` | Exclusion reasons corrected from the generator code; schema version 2 with notes. No feature changed |
| `veremi/test_preprocess.py` | Rewritten: 12 unit tests + the approved-status integration test |
| `veremi/feature_schema.json` | Regenerated (version 2) |
| `DATASET_TRACKS_MANIFEST.json` | New: primary, eval-only and baseline tracks, with files, MD5s, counts, label policy, caveats and duplicate policy |
| `PREPROCESSING_REPORT.md` | This report |

Nothing outside `veremi/` and these reports was changed. Nothing was committed.

## 12. Unresolved limitations

- **Generator defects that stay in the official labels:**
  - 14 (reversedHeading) and 13 (zeroSpeedReport) receptions miss the documented rule.
  - suddenStop broadcasts can differ between receivers.
  - Report all three per attack.
- **Canonical one-row-per-broadcast tables** are not meaningful for suddenStop and suddenConstantSpeed.
- **Unmodified dosAttack messages** cannot be rule-checked individually, because the attacker set is not recorded. They rest on the acquisition finding of 0 mixed-label senders.
- **Ground-truth files:** their origin is not in the repository's code; their meaning was established empirically.
- **Pseudonyms** never change within a sender in this subset.
- **Data scope:** a low-density highway scenario, simulated only.
- **Old provisional outputs:** `processed/v1/` (the FAILED tables) was deleted on 18 November, after v2 was verified against its manifest MD5s (48/48) and no code or configuration referenced v1.
