"""Acquire and validate the VeReMi NextGen InTAS_highway_2 subset (Zenodo record 19665762, CC-BY 4.0).

    python -I veremi/acquire.py --data-dir <dir outside the repo> --manifest <manifest.json>

Steps: list the official files of the subset from the Zenodo API -> check disk space -> download -> verify size and
the official MD5 -> safe extraction of the outer and inner zips -> inspect every JSON file (counts, labels, schema).
Idempotent: a file that is already present is re-verified, never overwritten. Anything that fails is recorded in the
manifest and the exit code is 1; nothing is skipped silently.
"""
import argparse
import hashlib
import io
import json
import math
import os
import platform
import shutil
import sys
import time
import urllib.request
import zipfile
import zlib
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

RECORD = "19665762"
API = f"https://zenodo.org/api/records/{RECORD}"
SUBSET = "InTAS_highway_2"
UA = {"User-Agent": "research-dataset-fetch/1.0"}
SPLITS = ("Train", "Validation", "Test")
# Message schema documented in the dataset README (record file README.md, checked 2026-11-18).
TOP = {"rcvTime", "sendTime", "sender_id", "sender_alias", "messageID", "attacker", "receiver", "sender"}
RECEIVER = {"pos", "pos_noise", "spd", "spd_noise", "acl", "acl_noise", "hed", "hed_noise", "driversProfile"}
SENDER = RECEIVER | {"distance_to_road_edge"}
VECTORS = {"pos", "pos_noise"}                       # serialised as "x,y,z" strings
NUMBERS = {"spd", "spd_noise", "acl", "acl_noise", "hed", "hed_noise", "distance_to_road_edge"}
PROFILES = {"NORMAL", "CAUTIOUS", "AGGRESSIVE"}


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def official_files():
    with urllib.request.urlopen(urllib.request.Request(API, headers=UA), timeout=60) as r:
        rec = json.load(r)
    meta = rec["metadata"]
    files = sorted((f for f in rec["files"] if f["key"] == SUBSET + ".zip" or f["key"].startswith(SUBSET + "_")),
                   key=lambda f: f["key"])
    source = {"record": RECORD, "doi": rec.get("doi"), "title": meta.get("title"),
              "publication_date": meta.get("publication_date"), "license": (meta.get("license") or {}).get("id"),
              "creators": [c.get("name") for c in meta.get("creators", [])], "api_url": API,
              "record_url": f"https://zenodo.org/records/{RECORD}", "files_in_record": len(rec["files"]),
              "bytes_in_record": sum(f["size"] for f in rec["files"])}
    return source, files


def md5_of(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(f, archives):
    """Download one file to <name>.part, verify size + MD5, then rename. Existing files are verified, not replaced."""
    name, want = f["key"], f["checksum"].split(":", 1)[1]
    entry = {"file": name, "url": f["links"]["self"], "size_official": f["size"], "md5_official": want}
    dest, part = archives / name, archives / (name + ".part")
    if dest.exists():
        entry.update(action="already present", size_actual=dest.stat().st_size, md5_actual=md5_of(dest))
    elif part.exists():
        return {**entry, "verified": False, "error": f"{part.name} already exists; not overwritten"}
    else:
        for attempt in range(1, 4):
            try:
                h, n, t0 = hashlib.md5(), 0, time.time()
                req = urllib.request.Request(entry["url"], headers=UA)
                with urllib.request.urlopen(req, timeout=120) as r, open(part, "xb") as out:
                    for chunk in iter(lambda: r.read(1 << 20), b""):
                        out.write(chunk)
                        h.update(chunk)
                        n += len(chunk)
                break
            except OSError as e:                      # network errors (URLError is an OSError)
                part.unlink(missing_ok=True)
                if attempt == 3:
                    return {**entry, "verified": False, "error": f"download failed after 3 attempts: {e}"}
                time.sleep(5 * attempt)
        entry.update(action="downloaded", downloaded_utc=now(), seconds=round(time.time() - t0, 1),
                     size_actual=n, md5_actual=h.hexdigest())
    entry["verified"] = entry["size_actual"] == f["size"] and entry["md5_actual"] == want
    if entry["action"] == "downloaded":
        if entry["verified"]:
            part.rename(dest)
        else:
            bad = archives / (name + ".BAD")          # kept for inspection, never used
            part.rename(bad)
            entry["error"] = f"size or MD5 mismatch; kept as {bad.name}"
    elif not entry["verified"]:
        entry["error"] = "existing file does not match the official size/MD5; not overwritten"
    return entry


def safe_target(root, member):
    """Reject absolute paths, drive letters, '..' and symlinks (zip-slip); return the resolved target path."""
    p = PurePosixPath(member.filename.replace("\\", "/"))
    if p.is_absolute() or ".." in p.parts or (p.parts and ":" in p.parts[0]):
        raise ValueError(f"unsafe path in archive: {member.filename!r}")
    if (member.external_attr >> 16) & 0o170000 == 0o120000:
        raise ValueError(f"symlink in archive: {member.filename!r}")
    target = (root / Path(*p.parts)).resolve()
    if root.resolve() not in target.parents:
        raise ValueError(f"path escapes the extraction folder: {member.filename!r}")
    return target


def crc_of(path):
    crc = 0
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            crc = zlib.crc32(chunk, crc)
    return crc


def extract_inner(zf, root):
    """CRC-test, then extract every member; an existing file is skipped only if its CRC and size match."""
    bad = zf.testzip()
    if bad:
        raise ValueError(f"CRC error in member {bad}")
    members = [m for m in zf.infolist() if not m.is_dir()]
    need = sum(m.file_size for m in members)
    if shutil.disk_usage(root.parent if root.parent.exists() else root.anchor).free < need + (1 << 30):
        raise OSError(f"not enough free disk space to extract {need:,} bytes")
    written = identical = 0
    for m in members:
        target = safe_target(root, m)
        if target.exists():
            if target.stat().st_size == m.file_size and crc_of(target) == m.CRC:
                identical += 1
                continue
            raise FileExistsError(f"{target} exists with different content; not overwritten")
        target.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(m) as src, open(target, "xb") as out:
            shutil.copyfileobj(src, out)
        written += 1
    return {"members": len(members), "uncompressed_bytes": need, "written": written, "already_identical": identical}


def extract_archive(path, out_root):
    """Outer zip = <subset>/<Split>/<subset>.zip; each inner zip is opened in memory and its JSON files extracted."""
    info = {"archive": path.name, "splits": {}}
    with zipfile.ZipFile(path) as outer:
        bad = outer.testzip()
        if bad:
            raise ValueError(f"CRC error in member {bad}")
        for m in outer.infolist():
            if m.is_dir():
                continue
            safe_target(out_root, m)                  # validate the name even though the inner zip is not written
            parts = PurePosixPath(m.filename).parts
            if not m.filename.endswith(".zip") or len(parts) < 2 or parts[-2] not in SPLITS:
                raise ValueError(f"unexpected member layout: {m.filename!r}")
            with zipfile.ZipFile(io.BytesIO(outer.read(m))) as inner:
                info["splits"][parts[-2]] = {"inner_zip": m.filename, "inner_zip_bytes": m.file_size,
                                             **extract_inner(inner, out_root / path.stem / parts[-2])}
    return info


def vector(v):
    try:
        xyz = [float(x) for x in str(v).split(",")]
    except ValueError:
        return None
    return xyz if len(xyz) == 3 and all(map(math.isfinite, xyz)) else None


def inspect_split(folder, keep_ids=False):
    """Counts, labels and schema checks for every received-CAM file of one split."""
    st, issues, examples = Counter(), Counter(), {}
    senders, aliases, types, profiles = defaultdict(lambda: [0, 0]), set(), defaultdict(Counter), Counter()
    box, times, ids = [math.inf, math.inf, -math.inf, -math.inf], [math.inf, -math.inf], set()

    def issue(kind, where):
        issues[kind] += 1
        examples.setdefault(kind, where)

    for fp in sorted(folder.rglob("*.json")):
        st["files"] += 1
        st["json_bytes"] += fp.stat().st_size
        try:
            msgs = json.loads(fp.read_bytes())
        except ValueError as e:
            issue("malformed_json_file", f"{fp.name}: {e}")
            continue
        if not isinstance(msgs, list):
            issue("file_is_not_a_list", fp.name)
            continue
        st["empty_files"] += not msgs
        seen = set()
        for i, m in enumerate(msgs):
            where = f"{fp.name}[{i}]"
            st["records"] += 1
            if not isinstance(m, dict):
                issue("record_is_not_an_object", where)
                continue
            for k in TOP - set(m):
                issue(f"missing:{k}", where)
            for k in set(m) - TOP:
                issue(f"extra:{k}", where)
            for k in ("rcvTime", "sendTime", "messageID", "sender_alias", "sender_id", "attacker"):
                types[k][type(m.get(k)).__name__] += 1
            a = m.get("attacker")
            if a in (0, 1) and not isinstance(a, bool):
                st[f"label_{a}"] += 1
            else:
                issue("attacker_not_0_or_1", where)
            for side, fields in (("receiver", RECEIVER), ("sender", SENDER)):
                d = m.get(side)
                if not isinstance(d, dict):
                    issue(f"{side}_is_not_an_object", where)
                    continue
                for k in fields - set(d):
                    issue(f"missing:{side}.{k}", where)
                for k in set(d) - fields:
                    issue(f"extra:{side}.{k}", where)
                for k, v in d.items():
                    types[f"{side}.{k}"][type(v).__name__] += 1
                for k in VECTORS & set(d):
                    if vector(d[k]) is None:
                        issue(f"bad_vector:{side}.{k}", where)
                for k in NUMBERS & set(d):
                    v = d[k]
                    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
                        issue(f"bad_number:{side}.{k}", where)
                if d.get("driversProfile") not in PROFILES:
                    issue(f"bad_profile:{side}", where)
                profiles[f"{side}:{d.get('driversProfile')}"] += 1
            r, s = m.get("rcvTime"), m.get("sendTime")
            if isinstance(r, int) and isinstance(s, int):
                if r < s:
                    issue("rcvTime_before_sendTime", where)
                times[0], times[1] = min(times[0], s), max(times[1], s)
            key = (str(m.get("sender_id")), str(m.get("messageID")))
            if key in seen:
                st["repeated_message_in_same_receiver_file"] += 1
            seen.add(key)
            if keep_ids:
                ids.add(key)
            sv = senders[m.get("sender_id")]
            sv[0] += 1
            sv[1] += a == 1
            aliases.add(m.get("sender_alias"))
            p = vector((m.get("sender") or {}).get("pos"))
            if p:
                box = [min(box[0], p[0]), min(box[1], p[1]), max(box[2], p[0]), max(box[3], p[1])]
    out = dict(st)
    out.update(senders=len(senders), attacker_senders=sum(1 for n, b in senders.values() if b),
               mixed_label_senders=sum(1 for n, b in senders.values() if 0 < b < n), sender_aliases=len(aliases),
               attack_share=round(st["label_1"] / st["records"], 5) if st["records"] else None,
               sender_pos_bbox_m=[round(x, 1) for x in box] if math.isfinite(box[0]) else None,
               sendTime_range_s=[round(times[0] / 1e9, 1), round(times[1] / 1e9, 1)] if math.isfinite(times[0]) else None,
               anomalies=dict(issues), anomaly_examples=examples,
               field_types={k: dict(v) for k, v in sorted(types.items())}, drivers_profiles=dict(profiles))
    return out, ids


def inspect_ground_truth(path, baseline_ids):
    """The separate ground-truth files: record count, schema variant, value types, overlap with baseline messages."""
    recs = json.loads(path.read_bytes())
    shapes, types, keys, missing = Counter(), defaultdict(Counter), Counter(), Counter()
    ids = set()
    for m in recs:
        shape = "nested (receiver/sender)" if "sender" in m else ("flat" if "pos" in m else "other")
        shapes[shape] += 1
        keys[tuple(sorted(m))] += 1
        for k, v in m.items():
            if not isinstance(v, dict):
                types[k][type(v).__name__] += 1
        for k in ("sender_id", "messageID"):
            missing[k] += k not in m
        ids.add((str(m.get("sender_id")), str(m.get("messageID"))))
    return {"file": path.name, "records": len(recs), "distinct_(sender_id,messageID)": len(ids),
            "schema_variants": dict(shapes), "key_sets": {", ".join(k): n for k, n in keys.most_common(3)},
            "has_attacker_field": any("attacker" in m for m in recs), "missing_id_fields": dict(missing),
            "value_types": {k: dict(v) for k, v in types.items()},
            "baseline_messages_in_split": len(baseline_ids),
            "baseline_messages_found_in_ground_truth": len(baseline_ids & ids)}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data-dir", required=True, type=Path)
    ap.add_argument("--manifest", required=True, type=Path)
    a = ap.parse_args()
    archives, extracted = a.data_dir / "archives", a.data_dir / "extracted"
    archives.mkdir(parents=True, exist_ok=True)
    extracted.mkdir(exist_ok=True)
    failures = []

    source, files = official_files()
    total = sum(f["size"] for f in files)
    free = shutil.disk_usage(a.data_dir).free
    print(f"{SUBSET}: {len(files)} official files, {total:,} bytes; free disk {free / 1e9:.1f} GB")
    if free < 20 * total:                               # archives + roughly 5x for extracted JSON, with margin
        sys.exit(f"STOP: need at least {20 * total / 1e9:.1f} GB free for download and extraction")

    downloads = []
    for f in files:
        e = fetch(f, archives)
        downloads.append(e)
        print(f"  {'OK ' if e['verified'] else 'FAIL'} {e['action'] if 'action' in e else 'not downloaded':<15} "
              f"{e['file']}  {e.get('size_actual', 0):,} B  md5 {e.get('md5_actual', '-')}" + (f"  ERROR: {e['error']}" if 'error' in e else ""))
        if not e["verified"]:
            failures.append(f"download/verify: {e['file']}: {e.get('error')}")

    extraction, inspection = [], {}
    for e in downloads:
        if not (e["verified"] and e["file"].endswith(".zip")):
            continue
        try:
            extraction.append(extract_archive(archives / e["file"], extracted))
        except (ValueError, OSError, zipfile.BadZipFile) as err:
            failures.append(f"extract: {e['file']}: {err}")
            extraction.append({"archive": e["file"], "error": str(err)})
    baseline_ids = {}
    for x in extraction:
        if "error" in x:
            continue
        stem = Path(x["archive"]).stem
        attack = stem[len(SUBSET) + 1:] or "baseline (no attack)"
        inspection[attack] = {}
        for split in SPLITS:
            res, ids = inspect_split(extracted / stem / split, keep_ids=stem == SUBSET)
            inspection[attack][split] = res
            if stem == SUBSET:
                baseline_ids[split] = ids
            if res["anomalies"].get("malformed_json_file"):
                failures.append(f"inspect: {stem}/{split}: {res['anomalies']['malformed_json_file']} malformed JSON files")
    ground_truth = []
    for e in downloads:
        if e["verified"] and e["file"].endswith(".json"):
            split = next(s for s in SPLITS if f"_{s}_" in e["file"])
            ground_truth.append({"split": split, **inspect_ground_truth(archives / e["file"], baseline_ids.get(split, set()))})

    manifest = {
        "created_utc": now(), "subset": SUBSET, "source": source,
        "data_dir": os.path.relpath(a.data_dir.resolve(), a.manifest.resolve().parent).replace("\\", "/"),
        "layout": {"archives": "archives/<official file name>",
                   "extracted": "extracted/<archive stem>/<Train|Validation|Test>/<inner folder>/veh_<id>.json"},
        "environment": {"python": platform.python_version(), "platform": platform.platform(),
                        "script": "veremi/acquire.py", "script_md5": md5_of(Path(__file__))},
        "files": downloads,
        "totals": {"files": len(files), "bytes_official": total,
                   "bytes_verified": sum(e.get("size_actual", 0) for e in downloads if e["verified"]),
                   "all_verified": all(e["verified"] for e in downloads)},
        "extraction": extraction, "inspection": inspection, "ground_truth_files": ground_truth,
        "failures": failures, "status": "OK" if not failures else "FAILED",
    }
    a.manifest.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(f"manifest: {a.manifest}  status: {manifest['status']}")
    for f in failures:
        print("  FAILURE:", f)
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
