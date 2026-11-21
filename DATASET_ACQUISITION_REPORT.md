# Dataset Acquisition Report: VeReMi NextGen, subset InTAS_highway_2

**Date:** 18 November 2026. **Status: OK.** All 19 official files were downloaded and match the official size and
MD5. Extraction was safe and complete. No file is corrupted or malformed. No ML training was started, and no existing
application module was changed.

| Item | Value |
|---|---|
| Source | Zenodo record 19665762, DOI 10.5281/zenodo.19665762, *VeReMi NextGen: A Dataset for Evaluating Misbehavior Detection Systems in VANETs* (Hermann, Remmers, Eisermann, Erb, Kargl), published 2026-06-08, licence CC-BY 4.0 |
| Subset | `InTAS_highway_2`: Ingolstadt highway scenario, 2 AM, low density. Simulated data (MOSAIC/SUMO/OMNeT++), not real-world recordings |
| Downloaded | 19 files, **380,632,840 bytes (380.6 MB)**, 1.05 % of the 36.19 GB record; nothing from other scenarios |
| Extracted | 17,760 JSON files, **1,746,722,901 bytes (1.75 GB)** |
| Data location | `../../data/veremi_nextgen/InTAS_highway_2/` relative to the repo root (written `<data>` below), outside the source-code folder, so git cannot pick it up |
| Manifest | `DATASET_MANIFEST_InTAS_highway_2.json`: source, files, official vs actual size and MD5, verification status, extraction and inspection results, environment |
| Script | `veremi/acquire.py` (new). It is idempotent: an existing file is re-verified, never overwritten. Check: `veremi/test_acquire.py` |

**Scope note.** The Day-1 audit (§4) recommended starting with 6 attacks, about 175 MB. You selected the subset
`InTAS_highway_2`, and the tasks ask for genuine/attacker counts and all attack categories. The archive named exactly
`InTAS_highway_2.zip` is the no-attack baseline, so I downloaded all 19 files of the scenario.

## 1. Official download location and archive names (Verified)

- **Listing:** <https://zenodo.org/api/records/19665762> → `files[]`. The script selects the files whose name is `InTAS_highway_2.zip` or starts with `InTAS_highway_2_`.
- **Download URL pattern:** `https://zenodo.org/api/records/19665762/files/<name>/content`.
- **Official checksums:** each file carries an MD5 in the record (`checksum: "md5:..."`). All 19 MD5s matched; they are listed in the manifest.

| Files | Count | Official size |
|---|---|---|
| `InTAS_highway_2.zip`, the baseline without attacks | 1 | 19,335,264 B |
| `InTAS_highway_2_<attack>.zip`, one per attack | 15 | 19,494,560 – 36,082,689 B |
| `InTAS_highway_2_Train_groundTruth.json`, `_Validation_groundTruth.json`, `_Test_ground_truth.json` | 3 | 18,381,874 / 6,713,056 / 9,838,094 B |

## 2. Disk space (Verified)

- **Before download:** 189 GB free on C: (`df -h /c`); the script measured 202 GB free at its start.
- **Required:** the script refuses to start below 20× the subset size (7.6 GB), which covers the archives plus extracted JSON with a large margin.
- **Used:** 364 MB of archives and 1.7 GB extracted.

## 3. Download and verification (Verified)

- **Method:** each file is written to `<name>.part` and checked against the official size and MD5, then renamed. A mismatch would have been kept as `<name>.BAD` and reported as a failure. A file already present would be re-verified and never replaced.
- **Result:**
  - 19/19 files verified.
  - No `.part` or `.BAD` files remain.
  - No retries were needed.
  - Total time for the run, including extraction and inspection: 1,280 s.

## 4. Safe extraction (Verified)

- **Layout:**
  - Each archive contains `<name>/Train/<name>.zip`, `<name>/Validation/<name>.zip` and `<name>/Test/<name>.zip`.
  - Each inner zip contains `<scenario>_<attack>/veh_<id>.json`, one file per receiving vehicle.
- **Checks:**
  - Every outer and inner archive passed the CRC test (`testzip`).
  - Every member name was checked against zip-slip: no absolute paths, drive letters, `..` or symlinks.
  - Inner zips were opened in memory and only their JSON files were written.
  - An existing target would be skipped only if its CRC and size matched; otherwise extraction stops.
- **Result:** 17,760 JSON files written, 0 skipped, 0 errors.
- **Destination:** `extracted/<archive stem>/<Train|Validation|Test>/<inner folder>/veh_<id>.json`.

## 5. File structure and split organisation (Verified)

- **One file per receiving vehicle,** each a JSON array of the CAMs that vehicle received. Every archive has 482 receivers in Train, 152 in Validation and 476 in Test.
- **Train and Validation** come from the same area and are split by time:
  - Train: `sendTime` from 3,601.3 to 12,599.4 s (9,000 s).
  - Validation: 12,600.3 to 14,399.5 s (1,800 s).
- **Test** comes from a different area. Its sender positions lie at y ≈ 449.7–451.7 km, while Train and Validation lie at ≈ 451.7–454.2 km. Test covers 7,201.1 to 14,399.4 s (7,200 s).

All three durations match the dataset documentation.

## 6. Records, files and labels by split (Verified)

All 16 archives together:

| Split | Files | Records | Genuine (`attacker`=0) | Attack (`attacker`=1) | Unlabelled (baseline) |
|---|---|---|---|---|---|
| Train | 7,712 | 656,798 | 478,084 | 141,013 | 37,701 |
| Validation | 2,432 | 312,505 | 228,342 | 66,186 | 17,977 |
| Test | 7,616 | 764,238 | 564,575 | 155,404 | 44,259 |
| **Total** | **17,760** | **1,733,541** | **1,271,001** | **362,603** | **99,937** |

Of the 1,633,604 labelled messages, 22.2 % carry the attack label. "Genuine" means `attacker = 0`. That covers honest
senders and also attacker messages whose deviation is below the dataset's significance threshold (see §8).

## 7. Attack categories and per-archive counts (Verified)

There are 15 attack archives plus the baseline, and all 15 attack types listed in the documentation are present.
T / V / Te below means Train / Validation / Test.

| Archive (attack) | Records T / V / Te | Attack-labelled T / V / Te | Attack share (all splits) | Attacker senders T / V / Te | Senders with both labels |
|---|---|---|---|---|---|
| `baseline (no attack)` | 37,701 / 17,977 / 44,259 | none (no label field) | unlabelled | — | — |
| `accelerationMultiplication` | 37,701 / 17,977 / 44,259 | 4,311 / 2,494 / 4,107 | 10.9 % | 96 / 30 / 93 | 215 |
| `constantPositionOffset` | 37,701 / 17,977 / 44,259 | 7,831 / 3,247 / 8,710 | 19.8 % | 96 / 30 / 95 | 0 |
| `constantSpeedOffset` | 37,701 / 17,977 / 44,259 | 7,530 / 3,998 / 8,900 | 20.4 % | 96 / 30 / 95 | 0 |
| `dataReplay` | 37,701 / 17,977 / 44,259 | 6,541 / 3,212 / 8,743 | 18.5 % | 96 / 30 / 95 | 120 |
| `dosAttack` | 55,290 / 26,121 / 60,718 | 25,721 / 11,959 / 24,652 | 43.9 % | 96 / 30 / 95 | 0 |
| `feignedBraking` | 37,701 / 17,977 / 44,259 | 2,700 / 1,759 / 3,496 | 8.0 % | 95 / 30 / 95 | 214 |
| `positionMirroring` | 37,701 / 17,977 / 44,259 | 7,924 / 4,005 / 9,618 | 21.6 % | 96 / 30 / 95 | 0 |
| `randomPositionOffset` | 37,701 / 17,977 / 44,259 | 7,834 / 3,164 / 8,280 | 19.3 % | 96 / 30 / 95 | 0 |
| `randomSpeedOffset` | 37,701 / 17,977 / 44,259 | 7,568 / 3,116 / 8,394 | 19.1 % | 96 / 30 / 95 | 0 |
| `reversedHeading` | 37,701 / 17,977 / 44,259 | 6,660 / 2,931 / 8,268 | 17.9 % | 96 / 30 / 95 | 37 |
| `suddenConstantSpeed` | 37,701 / 17,977 / 44,259 | 1,528 / 565 / 1,571 | 3.7 % | 45 / 16 / 34 | 95 |
| `suddenStop` | 37,701 / 17,977 / 44,259 | 3,392 / 2,219 / 3,940 | 9.6 % | 81 / 27 / 92 | 199 |
| `timeDelayAttack` | 37,701 / 17,977 / 44,259 | 7,645 / 3,532 / 8,680 | 19.9 % | 96 / 30 / 95 | 0 |
| `trafficCongestionSybil` | 73,694 / 34,706 / 83,894 | 35,993 / 16,729 / 39,635 | 48.0 % | 18,533 / 6,805 / 16,782 | 0 |
| `zeroSpeedReport` | 37,701 / 17,977 / 44,259 | 7,835 / 3,256 / 8,410 | 19.5 % | 96 / 30 / 95 | 45 |

How the archives differ from the baseline:
- **12 archives** keep the baseline's message count; the attack modifies content only.
- **`dosAttack`** adds about 47 % more messages, the floods.
- **`trafficCongestionSybil`** keeps all 37,701 baseline messages as genuine and adds phantom-vehicle messages: Train has 19,015 sender IDs, of which 18,533 carry attack labels.
- **Attacker share of senders:** about 20 % (96/482, 30/152, 95/476), consistent with the documented 20 % attacker density. The exceptions are `suddenConstantSpeed` and `suddenStop`: only 45 and 81 of the Train senders ever show a labelled deviation.

## 8. Missing fields, malformed records and schema inconsistencies (Verified)

Every record was checked against the documented schema:
- top-level and sender/receiver keys
- `attacker` ∈ {0, 1}
- `"x,y,z"` vectors with three finite numbers
- finite numeric fields
- valid `driversProfile` values
- `rcvTime` ≥ `sendTime`

| Check | Result |
|---|---|
| Malformed JSON files, non-list files, empty files | **0 / 0 / 0** |
| Attack archives: missing or extra fields, bad vectors or numbers, bad profiles, `rcvTime` < `sendTime` | **0 anomalies** in all 15 archives (1,633,604 records) |
| Baseline archive: different schema | All 99,937 records have **no `attacker` field**, **no `sender.distance_to_road_edge`**, and **every value stored as a string** (`"rcvTime": "12600318553476"`). Every numeric string parses to a finite number (0 failures), so this is a schema difference, not corruption |
| Ground-truth files | One record per **sent** message (Train 19,186; Validation 7,023; Test 18,892), with no `attacker` field and every value a string. Train and Validation nest `receiver`/`sender`; **Test is flat** (fields at top level, no receiver block). The file names are inconsistent: `_groundTruth` vs `_ground_truth`. The (`sender_id`, `messageID`) pairs match the baseline's distinct messages **100 %** in every split |
| Vector fields | `pos` and `pos_noise` are strings `"x,y,z"` in all archives, not the arrays the README shows |
| `sender_alias` | As many distinct aliases as senders in every non-Sybil archive and split (e.g. 482 / 482 in Train), so no pseudonym change is visible in this subset; Sybil has 19,035 aliases for 19,015 senders in Train |
| Repeated (`sender_id`, `messageID`) within one receiver file | Only in `dosAttack`: 86 / 1 / 38 records in Train / Validation / Test |
| Labels within an attacker sender | **Mixed for 7 of 15 attacks** (last column of §7). Labels mark *significant deviations*, not attacker identity; the significance threshold is not documented |

## 9. Commands executed

Paths: `<repo>` = the repository root (the folder that holds `run.py`),
`<data>` = `<repo>/../../data/veremi_nextgen/InTAS_highway_2` (the dataset folder, outside the repository). Run from `<repo>` in Git Bash.

```bash
# 1. Official file list with checksums, and free disk space
curl -s -m 30 -A "research-audit-script/1.0" "https://zenodo.org/api/records/19665762"   # filtered to InTAS_highway_2*
df -h /c
# 2. Layout of InTAS_highway_2.zip via one HTTP range request (central directory only, ~1 KB)
#    (scratch helper peek.py from the Day-1 audit; nothing extracted)
# 3. Safety check of the extractor, then a dry listing of the selected files
python -m pytest veremi/test_acquire.py -q -p no:cacheprovider      # 7 passed
python -I -c "import sys; sys.path.insert(0, 'veremi'); import acquire; print(acquire.official_files())"
# 4. Download, verify, extract, inspect (1,280 s, exit 0)
mkdir -p "<data>"
python -I veremi/acquire.py --data-dir "<data>" --manifest "DATASET_MANIFEST_InTAS_highway_2.json"
# 5. Post-checks: tables from the manifest; baseline numeric strings parse (0 failures); split time ranges;
#    no leftover .part/.BAD files; test suites
python -m pytest validation -q -p no:cacheprovider                  # 105 passed
```

During the session, `validation/test_portal_downloads.py::test_source_bundle_holds_the_current_code` failed once,
because my new check was first placed in `validation/`. That test requires every `validation/*.py` file to be inside
the published `portal/downloads/source.zip`. I moved the check to `veremi/test_acquire.py` instead of rebuilding the
portal bundle, and all 105 tests pass again.

## 10. Files created or changed

| Path | Change |
|---|---|
| `veremi/acquire.py` | New: acquisition, verification, safe extraction, inspection |
| `veremi/test_acquire.py` | New: zip-slip and vector-parsing checks (7 tests) |
| `DATASET_MANIFEST_InTAS_highway_2.json` | New: the manifest |
| `DATASET_ACQUISITION_REPORT.md` | New: this report |
| `DAY1_PROJECT_AND_DATASET_AUDIT.md` | Two corrections in §3 (per-sender labels; ground-truth semantics), marked "Corrected/Verified 18 Nov" |
| `<data>/archives/` (19 files), `<data>/extracted/` (17,760 files), `<data>/acquire_run.log` | Data, outside the repo |

Nothing was committed. No existing application module, test or portal file was changed.

## 11. Remaining issues

1. **Label semantics.** Labels are per message and deviation-based. Some attacker vehicles have unlabelled messages, and for `suddenConstantSpeed` and `suddenStop` some attackers have none at all. The documentation gives no identity-level ground truth. Decide whether the model targets messages (as labelled) or vehicles; for vehicles, `any(attacker)` is the best available label and under-counts those two attacks.
2. **The baseline archive has no labels and a different, all-string schema.** Use it as clean reference traffic only. It cannot be used for detection metrics.
3. **Two ground-truth schemas** (nested vs flat) and inconsistent file names. Any loader must handle both.
4. **The Sybil archive's messages from attacking senders are almost all phantoms** (18,533 attacker sender IDs in Train). Per-vehicle statistics for this attack are not comparable with the other 14.
5. **This is a low-density highway scenario.** The project's own setting is urban. Results from this subset must be reported as highway / low density only.
6. **Simulated data.** Never describe it as real-world vehicle data.
7. **Not done, as instructed:** no feature extraction, no ML training. `.gitignore` is unchanged, because the data lives outside the repo.
