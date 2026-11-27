"""Persistent course registration; originals remain the authoritative source."""
import contextlib
import copy
import json
import os
import re
from pathlib import Path
from .manifest import load, save, sha, inside
from .registry import natural

PRESETS = {1: (1920, 90), 2: (1600, 80), 3: (1280, 75),
           4: (1024, 70), 5: (800, 60)}
EXTENSIONS = {".pdf", ".ppt", ".pptx"}


def state_root():
    return Path(os.environ.get("ACADEMY_SAMPLER_HOME", "~/.academy-sampler")).expanduser().resolve()


@contextlib.contextmanager
def lock(home):
    """OS advisory lock, automatically released even if the process dies."""
    home.mkdir(parents=True, exist_ok=True)
    with (home / ".lock").open("a+b") as f:
        if os.name == "nt":
            import msvcrt
            f.seek(0, 2)
            if f.tell() == 0:
                f.write(b"0")
                f.flush()
            f.seek(0)
            try:
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise RuntimeError("Another trans process is running") from exc
            try:
                yield
            finally:
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise RuntimeError("Another trans process is running") from exc
            try:
                yield
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)


def code_of(value):
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9]{0,23}", value):
        raise ValueError("Course code must be 1–24 ASCII letters/digits, starting with a letter")
    code = value.upper()
    if code in {"CON", "PRN", "AUX", "NUL"} or re.fullmatch(r"(COM|LPT)[1-9]", code):
        raise ValueError("Course code is a reserved Windows filename")
    return code


def courses(home):
    return load(home / "courses.json", {})


def store(home, data):
    save(home / "courses.json", data)


def course_dir(home, code):
    return home / "courses" / code


def source_root(home, path):
    root = Path(path).expanduser().resolve()
    if not root.is_dir():
        raise ValueError("Raw directory missing; use --relocate with its new location")
    tool = Path(__file__).resolve().parents[2]
    # For an editable install, protect the actual checkout, not all site-packages.
    if (tool / "pyproject.toml").is_file() and (tool / "src/academy_sampler").is_dir():
        if root.is_relative_to(tool) or tool.is_relative_to(root):
            raise ValueError("Raw directory overlaps the tool checkout")
    if root.is_relative_to(home) or home.is_relative_to(root):
        raise ValueError("Raw directory overlaps the trans state directory")
    return root


def scan(root):
    files = []
    for parent, dirs, names in os.walk(root, followlinks=False):
        for name in dirs + names:
            p = Path(parent) / name
            if p.is_symlink() or not p.resolve().is_relative_to(root):
                raise ValueError("Symlink or escaped path in raw directory: " + str(p))
            if name == ".git":
                raise ValueError("Raw directory must not contain a Git repository")
        for name in names:
            p = Path(parent) / name
            if p.suffix.lower() in EXTENSIONS and p.is_file():
                files.append(p.relative_to(root).as_posix())
    return sorted(files, key=lambda x: (natural(x), x))


def check_records(root, records):
    for r in records:
        path = inside(root, r["current_path"])
        if not path.is_file() or sha(path) != r["source_sha256"]:
            raise ValueError(r["document_id"] + ": source missing or changed; restore the original bytes (from your backup or verified local mirror), then add revised content as a new file")


def group_of(record):
    parent = Path(record["current_path"]).parent.as_posix()
    return parent if parent != "." else "."


def normalize_group(value):
    value = value.replace("\\", "/").rstrip("/")
    if value == ".":
        return value
    if not value or value.startswith("/") or ":" in value or any(
            p in {"", ".", ".."} for p in value.split("/")):
        raise ValueError("Group must be a relative raw subfolder (or . for root files)")
    return value


def in_group(record, group):
    actual = group_of(record)
    return group is None or actual == group or (group != "." and actual.startswith(group + "/"))


def preset_of(entry, record):
    matches = [(g, n) for g, n in entry.get("group_presets", {}).items() if in_group(record, g)]
    return max(matches, key=lambda item: len(item[0]))[1] if matches else entry["preset"]


def reconcile(root, records):
    """Detect unambiguous moves without reallocating IDs or changing public URLs."""
    files = scan(root)
    present = set(files)
    claimed = set()
    missing = []
    for r in records:
        rel = r["current_path"]
        if rel in present:
            if sha(root / rel) != r["source_sha256"]:
                raise ValueError(r["document_id"] + ": source content changed; restore original and add the revision separately")
            claimed.add(rel)
        else:
            missing.append(r)
    if not missing:
        return records
    candidates = {}
    for rel in files:
        if rel not in claimed:
            candidates.setdefault(sha(root / rel), []).append(rel)
    for r in missing:
        matches = candidates.get(r["source_sha256"], [])
        if len(matches) != 1 or sum(x["source_sha256"] == r["source_sha256"] for x in missing) != 1:
            raise ValueError(r["document_id"] + ": missing source or ambiguous move; restore its previous path")
        rel = matches.pop()
        if Path(rel).suffix.lower() != Path(r["current_path"]).suffix.lower():
            raise ValueError(r["document_id"] + ": moved source extension differs")
        r.setdefault("path_history", [r["current_path"]]).append(rel)
        r["current_path"] = rel
    return records


def plan(root, code, records):
    files = scan(root)
    check_records(root, records)
    known = {r["current_path"] for r in records}
    occupied = {p.casefold() for p in files}
    number = max((r["sequence"] for r in records), default=0)
    result = []
    for rel in files:
        if rel in known:
            continue
        number += 1
        src = Path(rel)
        ident = f"{code}{number:02d}"
        dest = src.with_name(ident + src.suffix.lower()).as_posix()
        # Check case-insensitively even on case-sensitive filesystems.
        if dest.casefold() in occupied and dest != rel:
            raise ValueError("Rename collision: " + dest)
        if dest != rel and (root / dest).exists():
            raise ValueError("Rename destination exists: " + dest)
        occupied.add(dest.casefold())
        result.append({"document_id": ident, "sequence": number,
                       "original_filename": src.name, "original_path": rel,
                       "current_path": dest, "source_sha256": sha(root / rel),
                       "source_directory": ("sources/" + ident if src.parent.as_posix() == "."
                                            else "sources/by-group/" + src.parent.as_posix() + "/" + ident)})
    return result


def move_exact(root, old, new, digest):
    """Same-directory hard-link then unlink: exclusive destination, crash-recoverable."""
    src, dst = inside(root, old), inside(root, new)
    if src == dst:
        if not src.is_file() or sha(src) != digest:
            raise ValueError("Source changed: " + old)
        return
    if dst.exists():
        if sha(dst) != digest:
            raise ValueError("Destination occupied: " + new)
        if src.exists():
            # Only resume a link created by us, never remove an unrelated duplicate.
            if sha(src) != digest or not os.path.samefile(src, dst):
                raise ValueError("Conflicting rename recovery: " + new)
            src.unlink()
        return
    if not src.is_file() or sha(src) != digest:
        raise ValueError("Source changed: " + old)
    os.link(src, dst)  # fails safely on filesystems without hard links
    if sha(dst) != digest:
        raise ValueError("Hash changed during rename: " + new)
    src.unlink()


def apply_journal(home, code, entry, data):
    journal = course_dir(home, code) / "rename-journal.json"
    pending = load(journal)
    if pending is None:
        return
    root = source_root(home, entry["raw"])
    if pending["raw"] != str(root):
        raise ValueError("Pending rename journal belongs to a different directory")
    existing = {r["document_id"]: r for r in entry["documents"]}
    for r in pending["records"]:
        if r["document_id"] in existing and existing[r["document_id"]] != r:
            raise ValueError("Journal identity conflict")
        move_exact(root, r["original_path"], r["current_path"], r["source_sha256"])
        if r["document_id"] not in existing:
            entry["documents"].append(r)
            existing[r["document_id"]] = r
    check_records(root, entry["documents"])
    store(home, data)
    journal.unlink()


def register(home, data, raw, code, preset=None, dry_run=False, relocate=False):
    code = code_of(code)
    root = source_root(home, raw)
    previous = data.get(code)
    if previous:
        entry = copy.deepcopy(previous)
        if entry["raw"] != str(root):
            if not relocate:
                raise ValueError("Course already registered at another path; use --relocate")
            if (course_dir(home, code) / "rename-journal.json").exists():
                raise ValueError("Recover the pending rename before relocation")
            check_records(root, entry["documents"])
        if not dry_run and (course_dir(home, code) / "rename-journal.json").exists():
            entry = previous
            apply_journal(home, code, entry, data)
            entry = copy.deepcopy(entry)
    else:
        entry = {"raw": str(root), "preset": 3, "documents": [], "remote": None}
    for other, value in data.items():
        if other != code:
            other_root = Path(value["raw"])
            if root.is_relative_to(other_root) or other_root.is_relative_to(root):
                raise ValueError("Raw directory overlaps registered course " + other)
    entry["documents"] = reconcile(root, entry["documents"])
    proposed = plan(root, code, entry["documents"])
    if not proposed and not entry["documents"]:
        raise ValueError("No PDF/PPT/PPTX files found")
    if dry_run:
        return proposed
    entry["raw"] = str(root)
    if preset is not None:
        entry["preset"] = preset
    data[code] = entry
    store(home, data)
    if proposed:
        save(course_dir(home, code) / "rename-journal.json",
             {"raw": str(root), "records": proposed})
        apply_journal(home, code, entry, data)
    return entry
