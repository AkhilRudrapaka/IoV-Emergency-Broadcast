# VeReMi NextGen: generator and label-semantics investigation

**Date:** 18 November 2026. **Read-only:** no source, dataset, label or processed table was changed. No training was started.

**Source inspected:** <https://github.com/VeReMi-dataset/VeReMi-NextGen>, shallow clone at commit `acda994` (2026-08-09). The attack generator `Generator/attackGenerator/attackGenerator.py` last changed on **2026-04-30** (`3e7a544` "Comments adjusted"; before that `ddc874b`, 2026-04-30, and `e3630d0`, 2025-12-21, per the GitHub commits API). That is before the dataset's Zenodo release on 2026-06-08.

**Was this the code that produced the dataset?** The labelling rules read from this code reproduce the published labels exactly (§3). That is strong evidence, but not proof.

All line numbers below refer to `Generator/attackGenerator/attackGenerator.py` at that commit, unless another file is named.

**Bottom line**

- **Where labels come from.** Labels are set by the attack generator, separately for **each receiver's record** of a message.
- **Most attacks are unaffected.** The generator keeps some per-sender attack state in global variables that persist across receiver files, and it processes those files in file-system order, not in time order. For 13 of the 15 attacks this does not matter: the manipulation is stateless or cached per message.
- **reversedHeading and zeroSpeedReport.** Their labels follow the documented rule for all but 14 and 13 receptions. Nearly every genuine label on a modified message is the documented "stationary vehicle" exemption.
- **suddenStop.** Labels follow its rule 100 %, but whether a reception is manipulated depends on receiver-file processing order. So one broadcast can be stopped at one receiver and normal at another.
- **suddenConstantSpeed.** Same processing-order effect. In addition, its code uses a one-sided speed test where the documentation specifies an absolute difference. As a result, 2,904 receptions with a frozen speed more than 1 m/s *above* the true speed are labelled genuine.
- **Recommendation.**
  - Receiver-level classification as the main task.
  - 14 archives usable for supervised training.
  - suddenConstantSpeed in a separate evaluation-only track.
  - Canonical one-row-per-transmission tables only for the 13 archives whose receptions agree.

## 1. Generator architecture (Investigation A)

**Pipeline order** (`Documentation/Getting Started/README.md` lines 51–108, 167–228):
1. **MOSAIC + SUMO + OMNeT++ simulation.** The CAM application writes **one JSON file per vehicle**, holding the CAMs that vehicle received (lines 84–86).
2. **Train/Validation split** of the `_trainval` run by `sendTime`: `split_into_train_val.py`, function `split_json_by_timestamp`, lines 35–36, cut-off 12,600 s. The `_test` run, a different area, is the Test set as a whole (lines 53–55, 107–108).
3. **Attack generation:** `attackGenerator.py <input_folder> <misbehavior> <sumoConf>` (lines 167–190), run on one folder at a time.
4. **Enrichment:** `enrichMsgs.py` adds `sender.distance_to_road_edge` (lines 197–228).

**Inside `attackGenerator.py`:**
- **`__main__`, lines 807–931:**
  - Loads every receiver file of the folder into `df_all` (817–821).
  - De-duplicates it by `messageID` (822). This is one row per transmission, used only by dataReplay.
  - Sets `attacker = 0` (824).
  - Draws the attackers as `random.sample(...)` of **20 % of the sender IDs** (869–870). There is no `random.seed` call anywhere in the file, so a run cannot be reproduced.
  - Builds the per-attacker parameters (`set_up_misbehavior_config`, 711–804).
  - Then processes the receiver files **one by one** in `input_folder.glob('*.json')` order (922–926). That is file-system order, not time order.
- **`process_single_file(json_file)`, lines 583–708:**
  - Loads **one receiver's** records (591–598) and sets `attacker = 0` (599).
  - Sorts them by `rcvTime` (642).
  - Applies the chosen manipulation function **row by row to every record whose sender is an attacker** (684–685).
  - Appends DoS and Sybil extra rows (696–698), rebuilds the nested JSON (`reconstruct_nested`, 85–115) and writes the receiver's file (706–708).
- **Global state:** `misbehavior_config`, `messages_lookup` and `sender_lookup` are created once (810–812). They are **never reset between receiver files**.

**Answers to A:**
- **Granularity.** Attacks operate **per received-message record**, inside each receiver's file. They are parameterised **per sender** (`misbehavior_config[sender_id]`). Some functions make a received record agree with earlier receivers through a cache keyed by `messageID`; others don't.
- **Label assignment.** It happens inside the same manipulation function, **during the modification**. Every record starts at 0; a function sets 1 when its condition holds. Conditions are evaluated on the **original** values: copies are taken before modification, for example `correct_msg = msg.copy()` (268, 349) and `original_acl` (361, 370).

## 2. Ground truth (Investigation D)

- **Not produced by any code in the repository.** A search for `groundTruth`, `ground_truth` and `GroundTruth` finds only *readers*: `MBD_systems/main.py:166` and `parameter_optimization/Bin_generator/convert_to_bin.py:13-16`. Its origin is therefore **not documented in code** (uncertainty U1).
- **Empirical check** (Block B pipeline, all splits): each ground-truth file holds **one record per transmitted message**, keyed by (`sender_id`, `messageID`).
  - Keys are unique.
  - Values equal the unmodified baseline message, including the noisy reported position and the `pos_noise` values.
  - All 19,186 / 7,023 / 18,892 transmissions are covered.
  - So ground truth describes the **transmitted, unmanipulated message**, not a received observation and not the physical true state.
  - The `receiver` block in the Train/Validation ground-truth files is the one reception that survived de-duplication. It is not meaningful per transmission.
- **Identity.** The generator itself treats `messageID` as the transmission identity: it de-duplicates by it (822) and keys its caches by it (208, 247, 404, 520).
  - In the baseline traffic it is unique per transmission; (`sender_id`, `messageID`) is unique in every ground-truth file.
  - **Exception, dosAttack:** copies get `messageID + 2,000,000 + i` (382–392). Two consecutive original IDs of a sender can therefore produce the same copy ID (86 / 1 / 38 receptions observed). Copies whose ID collides with an existing message are silently dropped (697).
  - (`sender_id`, `messageID`, `sendTime`) is unique per reception.
- **Canonical transmitted-message table:** safe only where every reception of a transmission is manipulated identically (§5).

## 3. The four problematic attacks (Investigation B)

The rules below were tested on all receptions of all three splits whose transmission is in ground truth, using the original values from ground truth (read-only check, `verify_label_rules.py`).

### 3.1 `zeroSpeedReport`: `zero_speed_report(msg)`, lines 266–276

```python
correct_msg = msg.copy()
msg['sender_spd'] = 0
if correct_msg['sender_spd'] > 1 and msg['sender_id'] in sender_lookup and get_distance(
        sender_lookup[msg['sender_id']]['sender_pos'], msg['sender_pos']) > 1.0:
    msg['attacker'] = 1
elif correct_msg['sender_spd'] > 1 and msg['sender_id'] not in sender_lookup:
    msg['attacker'] = 1
sender_lookup[msg['sender_id']] = correct_msg.copy()
```

- **Input:** one received record (a `pd.Series` row of the receiver's DataFrame), modified in place after a copy.
- **Fields modified:** `sender_spd` → 0, for every attacker record.
- **Label:** 1 iff original speed > 1 m/s **and** the sender moved > 1 m since "its last message". The documentation (`Documentation/Post-Processing/Attack Generator/README.md` lines 85–89) says the 0 case "prevents false positives when a vehicle legitimately stops". The genuine label on stationary vehicles is **intentional**.
- **Why receptions differ:** "last message" is `sender_lookup[sender_id]`. That is a global variable updated by *every* processed record of any receiver file, in file-system order. The first record of a sender in a newly processed file is therefore compared with whatever record of that sender was processed last, possibly **the same broadcast** at another receiver (distance 0, label 0). This is a **generator defect**: the code departs from the documented "since last message" meaning.
- **Measured:** 21,258 attacker receptions.
  - 21,245 match the documented rule, applied chronologically per sender.
  - **13 do not.** All 13 are labelled 0 although the rule says 1, which matches the defect.
  - Of the 1,744 genuine-labelled modified receptions, 1,732 have original speed ≤ 1 m/s (intended exemption).
  - Block B counted 20 receptions whose label differs from their transmission's first reception.
- **Verdict:** labels are reliable, with ≤ 0.06 % defect noise.

### 3.2 `reversedHeading`: `reversed_heading(msg)`, lines 347–357

The same structure as zeroSpeedReport: `msg['sender_hed'] = (msg['sender_hed'] + 180) % 360` (350), then the same speed > 1 m/s **and** moved > 1 m condition through the global `sender_lookup` (351–356). The documentation (lines 141–143) says label 0 applies "if vehicle is stationary (heading doesn't matter when not moving)", which is intentional.

- **Measured:** 19,470 attacker receptions.
  - 19,456 match the documented rule; **14 do not**, the same defect mechanism.
  - Of the 1,597 genuine-labelled receptions with a reversed heading, 1,587 have original speed ≤ 1 m/s.
  - The earlier example `veh_2004`/7727, labelled 1 at three receivers and 0 at one with identical content, is this defect.
- **Verdict:** labels are reliable, with ≤ 0.07 % defect noise.

### 3.3 `suddenStop`: `sudden_stop(msg)`, lines 279–324; configuration lines 776–780 (trigger probability 0.05)

- **Frozen branch** (281–300): if the sender already has a stop (`misbehavior_config[sender_id]["msg"]`, `stop_time`) and `sendTime > stop_time`, the record is **replaced by a copy of the saved stop message**: position and heading frozen, speed and acceleration 0. Its own receiver fields and timestamps are kept. Label 1 iff the original speed > 1 m/s **or** the distance to the frozen position ≥ 20 m (298–299).
- **Trigger branch** (302–322): if no stop exists yet, then with probability 0.05 per **record**, the current record becomes the stop message (speed and acceleration 0). `stop_time = sendTime`. Label 1 iff the original speed > 1 m/s **and** acceleration ≥ 0 (304, 311–312).
- **Documentation** (lines 189–202) states the same two conditions.
- **Measured:** labels match the code rules for **100 %** of the 10,001 modified receptions (frozen: 9,435 labelled 1 and 368 labelled 0; trigger: 116 and 82).
- **Why one broadcast differs between receivers:** the stop state is global per sender and is set by the **first trigger in processing order**.
  - Files processed before the trigger keep the sender's records unmodified, even for times after the eventual `stop_time`.
  - Files processed after it freeze every record with `sendTime > stop_time`.
  - The trigger transmission itself is modified only in the file where it fired.
- **Result:** 759 receptions differ in content and 679 in label from the first reception of their transmission. Example: `veh_1451`/371 is stopped (speed 0, label 1) at one receiver and normal (11.6 m/s, label 0) at another.
- **Defect, intentional or not?** This is a **generator defect** as a model of a broadcast, since every receiver hears the same frame. Within one receiver's stream the attack timeline is self-consistent: normal, then frozen from some point onward. Every reception's label is consistent with its own content.

### 3.4 `suddenConstantSpeed`: `sudden_stop_speed(msg)`, lines 327–344; configuration lines 781–785 (trigger probability 0.05)

```python
if saved_speed is not None and speed_freeze_time < msg['sendTime']:
    attacker = msg['sender_spd'] - misbehavior_config[msg['sender_id']]["saved_speed"] > 1   # line 332
    msg['sender_spd'] = misbehavior_config[msg['sender_id']]["saved_speed"]
    if attacker: msg['attacker'] = 1
```

- **Fields modified:** `sender_spd` → the frozen speed, for every record after the freeze time.
- **Label:** the code tests `actual − frozen > 1` (**one-sided**). The documentation says "Only if |current_speed − frozen_speed| > 1 m/s" (lines 101–103).
- **Measured:** the one-sided code rule reproduces **100 %** of the 10,214 modified receptions (6,550 labelled 0 and 3,664 labelled 1). The documented two-sided rule would label **2,904 more receptions as attacks**: frozen speed more than 1 m/s *above* the true speed. That is 28 % of the modified receptions, with deviations up to 52 m/s labelled genuine.
- **Assessment:** this is a **generator defect against its own documentation**. On top of it is the same processing-order effect as suddenStop: 889 receptions differ in content and 331 in label between receivers.
- **Verdict:** labels are **not reliable** for supervised learning as published.

## 4. The threshold attacks (Investigation C)

| Attack | Function | Modification | Label rule (code = documentation) | Measured |
|---|---|---|---|---|
| `feignedBraking` | `feigned_braking`, 360–366; factor k ~ U(2,4) at 786–788 | if original acl > 0: `acl *= -k` | 1 iff original acl > 0.25 m/s² (364); documentation lines 115–117 | Rule reproduces **100 %** of 18,841 attacker receptions. Modified-but-genuine cases have 0 < acl ≤ 0.25, so a deviation ≤ 0.25·(1+k) ≤ 1.25 (observed max 1.16) |
| `accelerationMultiplication` | `acl_multiplication`, 369–374; factor m ~ U(2,4) at 789–791 | `acl *= m` | 1 iff abs(original acl) > 0.5 m/s² (372); documentation lines 127–129 | Rule reproduces **100 %** of 20,690 attacker receptions. Modified-but-genuine cases have a deviation ≤ 0.5·(m−1) ≤ 1.5 (observed max 1.47) |

Both are stateless, deterministic per message, and consistent across receivers. The small modified-but-genuine
deviations are **intentionally** labelled 0: the documentation (line 253) says conditional labelling "prevents false
positives when the manipulation has no practical effect". Labels mean *significant* manipulation, not *any*
manipulation.

## 5. Consistency of every attack across receivers

| Attack | Mechanism (lines) | Same broadcast identical at all receivers? |
|---|---|---|
| constantPositionOffset, constantSpeedOffset, timeDelayAttack | per-sender constant (191–202, 238–241) | Yes |
| positionMirroring | deterministic from the message and the SUMO map (228–235) | Yes |
| randomPositionOffset, randomSpeedOffset | first receiver draws; others reuse `messages_lookup[messageID]` (205–225, 244–263) | Yes |
| feignedBraking, accelerationMultiplication | stateless (360–374) | Yes |
| dosAttack | original labelled 1 unchanged; deterministic copies per receiver file (377–397) | Yes (only the copy-ID collisions, §2) |
| trafficCongestionSybil | phantoms cached by `messageID` (400–461) | Yes |
| dataReplay | applied once per transmission on `df_all` (464–514), copied into each file by `messageID` (517–534) | Yes |
| zeroSpeedReport, reversedHeading | content stateless; label uses the global `sender_lookup` | Content yes; label differs at ≤ 0.07 % of receptions |
| suddenStop, suddenConstantSpeed | global stop/freeze state set by processing order | **No** |

## 6. Related findings that affect features

- **`pos_noise` is the realised error, not a confidence.** `get_vehicle_offset` computes the true position as `reported − noise` (179–188, line 184). A real receiver cannot know this value, which confirms its exclusion.
- **`distance_to_road_edge` is computed by `enrichMsgs.py`** (`worker_process_batch`, 158–163) from the **reported, possibly manipulated** `sender_pos` against the SUMO road network, after the attacks. The documentation (`Post-Processing/Data Enrichment/README.md` line 3) calls it "essential for the Position Plausibility Check". So it is **computable by a receiver that has the same road map**, which is a legitimate but explicit assumption. This corrects the Block B reasoning: it is not ground-truth derived. It may be used in a clearly labelled "receiver has a lane-level map" variant.
- **`timeDelayAttack` shifts both `sendTime` and `rcvTime`** by 2–4 s (199–200). The `delay_ms` feature (rcvTime − sendTime) therefore carries no signal for this attack by construction; detection must rely on stale content.
- **Attackers are re-drawn on every generator run** (869–870, unseeded). The documented order splits before attacking, and the generator takes one folder at a time. That implies separate runs for Train, Validation and Test, which is consistent with about 20 % attackers in each split, but it was not observed directly. If so, a vehicle's attacker status is independent across splits, and vehicle identity is not a stable label.

## 7. Label semantics, by attack

| Meaning of `attacker = 1` | Attacks |
|---|---|
| Every message of an attacker vehicle (content manipulated) | constantPositionOffset, randomPositionOffset, positionMirroring, constantSpeedOffset, randomSpeedOffset, timeDelayAttack |
| Every message of an attacker vehicle, including unmodified originals | dosAttack (originals and copies) |
| Injected or replaced message only | trafficCongestionSybil (phantoms), dataReplay (replayed messages) |
| Manipulation with a practical effect (conditional) | feignedBraking (acl > 0.25), accelerationMultiplication (abs(acl) > 0.5), zeroSpeedReport and reversedHeading (moving), suddenStop (moving or ≥ 20 m away) |
| Conditional with a defective condition | suddenConstantSpeed (one-sided) |

`attacker = 0` therefore means "not a significant manipulation", **not** "sent by an honest vehicle".

## 8. Recommendations (Investigation E)

**Learning task.** Use **(1) received-message-level classification** as the primary task.
- It is the level at which the generator assigns labels (`process_single_file`, 684).
- It is what an on-board detector actually classifies.
- It is well defined for all 15 archives: every reception carries the label the generator assigned to that record. Apart from the 27 defect receptions (§3.1–3.2) and suddenConstantSpeed's one-sided rule (§3.4), those labels follow the documented rule applied to the reception's own content.

Use **(2) canonical transmitted-message classification** only as a secondary analysis. It shows how much repeated receptions inflate the numbers, and it is restricted to archives whose receptions agree. Use **(3) separate tracks** for the attacks that need them.

**Use of the 15 attacks in supervised training:**

| Track | Attacks | Use |
|---|---|---|
| A: exact labels | constantPositionOffset, randomPositionOffset, positionMirroring, constantSpeedOffset, randomSpeedOffset, timeDelayAttack, dosAttack, trafficCongestionSybil, dataReplay, feignedBraking, accelerationMultiplication (11) | Train, validate and test; canonical tables safe |
| B: documented rule with ≤ 0.07 % defect noise | zeroSpeedReport, reversedHeading (2) | Train, validate and test with the official labels. In canonical tables, flag the transmissions whose receptions disagree (20 and 19 receptions) |
| C: labels follow the code; content differs between receivers | suddenStop (1) | Receiver-level train/validate/test only. Never in canonical tables. Report separately, with the processing-order caveat |
| D: defective labels | suddenConstantSpeed (1) | **Exclude from training.** Evaluation-only track with the official labels. Any documented-rule relabelling would be a *derived* label, kept alongside the official one and decided by the team |

This gives **14 archives** for supervised training (tracks A–C).

**Experiment design:**
1. **Official splits only.** Fit on Train, select models and thresholds on Validation, and evaluate on Test **once**. Test is a different area; Train and Validation are split by time. Do not re-split.
2. **Per-attack evaluation** for every archive, plus a pooled multi-attack model. In the pooled model, the same honest base messages appear in up to 15 archives in the same split. Either de-duplicate identical honest receptions across archives (`sender_id`, `messageID`, `sendTime`, `receiver`) or report per-attack models alongside.
3. **Metrics** per attack: precision, recall, F1, FPR and PR-AUC on received messages. Also report the canonical-transmission version for tracks A–B.
4. Report tracks C and D **separately**, never averaged into a headline number.
5. **Feature variants:**
   - main: no map-based feature
   - optional: "with road-edge distance (receiver has a map)" as a clearly labelled variant
   - `pos_noise`, `driversProfile`, identities and absolute time/position stay excluded
6. A clearly scoped **cross-scenario check** (for example the urban subset) only if it is acquired later. This subset is highway, low density, simulated.

## 9. Remaining uncertainties

- **U1:** the ground-truth files are not produced by any code in the repository. Their meaning (unmanipulated transmitted message) is established empirically, not from source. The `receiver` block in the Train/Validation ground truth is unexplained.
- **U2:** the dataset may have been generated with code older than the inspected version. Mitigation: the file last changed on 2026-04-30, before release, and the code's rules reproduce the labels of all six investigated attacks (100 % for four, ≥ 99.9 % for the two with the documented defect).
- **U3:** the exact file-processing order on the authors' machine is unknown. The cross-receiver differences are *consistent with* the processing-order mechanism, but which receiver triggered each stop or freeze cannot be reconstructed.
- **U4:** the generator is unseeded (no `random.seed`), so the published files cannot be regenerated identically. They are the only reference.
- **U5:** inconsistent tool versions between the website (MOSAIC 25.0, SUMO 1.22.0) and the repository badges (MOSAIC 25.2, SUMO 1.25.0) are unresolved. They do not affect the attack logic.

## 10. Evidence trail

- **Repository:** a shallow clone at commit `acda994` was inspected in scratch. It was 16 GB because it includes the simulation scenarios, and it was deleted on 18 November once this report was complete. To re-inspect the same code: `git init veremi && cd veremi && git remote add origin https://github.com/VeReMi-dataset/VeReMi-NextGen.git && git fetch --depth 1 origin acda994bae9966df6ae2f292a2945d8d91e249ce && git checkout FETCH_HEAD`.
- **Files read:**
  - `Generator/attackGenerator/attackGenerator.py` (all 931 lines)
  - `Generator/enrichMsgsWithFutherInfo/enrichMsgs.py` (lines 138–177 and the function list)
  - `Generator/parameter_optimization/Splitting/split_into_train_val.py`
  - `Documentation/Post-Processing/Attack Generator/README.md`
  - `Documentation/Getting Started/README.md` (lines 51–110 and the section headings)
- **Commit history:** GitHub commits API for `Generator/attackGenerator/attackGenerator.py`.
- **Rule checks against the data:** `…\scratchpad\veremi_tools\verify_label_rules.py`, read-only over the extracted archives and ground-truth files.
