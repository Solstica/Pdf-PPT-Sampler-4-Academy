"""Render registered sources and publish a strict allowlist to private GitHub."""
import json
import re
import shutil
import subprocess
from pathlib import Path
import pymupdf as fitz
import yaml
from . import cli
from .config import config
from .converters import pdf_source
from .manifest import inside, load, save, sha
from .workspace import init
from .trans_registry import PRESETS, check_records, course_dir, register, store

TOOL_REPO = "solstica/pdf-ppt-sampler-4-academy"


def repo_name(url):
    match = re.fullmatch(
        r"(?:git@github\.com:|ssh://git@github\.com/|https://github\.com/)"
        r"([A-Za-z0-9][A-Za-z0-9-]*)/([A-Za-z0-9_.-]+?)(?:\.git)?/?", url,
        re.IGNORECASE)
    if not match or match[2] in {".", ".."}:
        raise ValueError("Expected a GitHub SSH or HTTPS repository URL (no credentials)")
    return (match[1] + "/" + match[2]).lower()


def run(args, cwd=None, allow_failure=False):
    p = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if p.returncode and not allow_failure:
        raise RuntimeError(args[0] + " failed: " + (p.stderr or p.stdout).strip())
    return p


def git(root, *args, allow_failure=False):
    return run(["git", "-C", str(root), *args], allow_failure=allow_failure)


def private_target(url):
    name = repo_name(url)
    if name == TOOL_REPO:
        raise ValueError("The public tooling repository is not a course destination")
    try:
        info = json.loads(run(["gh", "repo", "view", name, "--json",
                               "visibility,nameWithOwner,defaultBranchRef"]).stdout)
    except (OSError, RuntimeError, ValueError) as exc:
        raise RuntimeError("Cannot verify repository privacy. Install GitHub CLI and run gh auth login; no push performed") from exc
    if info.get("visibility") != "PRIVATE" or info.get("nameWithOwner", "").lower() != name:
        raise ValueError("Destination must be a verified PRIVATE GitHub repository")
    branch = (info.get("defaultBranchRef") or {}).get("name")
    return name, url, branch


def workspace(home, code, entry):
    base = course_dir(home, code) / "workspace"
    if not (base / "course.yaml").exists():
        init(base)
    cfg = config(base)
    edge, quality = PRESETS[entry["preset"]]
    cfg["course"] = code
    cfg["groups"] = {"lectures": {"path": "raw/lectures", "prefix": code,
                                   "preset": "trans", "order": []}}
    cfg.setdefault("presets", {})["trans"] = {"long_edge": edge, "quality": quality}
    (base / "course.yaml").write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    raw = Path(entry["raw"])
    check_records(raw, entry["documents"])
    registry_path = base / "sources/source_registry.json"
    old = {d["document_id"]: d for d in load(registry_path, {"documents": []})["documents"]}
    records = []
    for r in entry["documents"]:
        src = inside(raw, r["current_path"])
        rel = "raw/lectures/" + r["document_id"] + src.suffix.lower()
        dst = inside(base, rel)
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists() and sha(dst) != r["source_sha256"]:
            raise ValueError("Local mirror changed: " + rel)
        if not dst.exists():
            temp = dst.with_suffix(dst.suffix + ".tmp")
            shutil.copy2(src, temp)
            if sha(temp) != r["source_sha256"]:
                raise ValueError("Source changed during copy")
            temp.replace(dst)
        if sha(src) != r["source_sha256"]:
            raise ValueError("Source changed during import")
        previous = old.get(r["document_id"])
        if previous:
            if previous["source_sha256"] != r["source_sha256"]:
                raise ValueError("Local document ID conflict")
            total = previous["total_pages"]
        else:
            with pdf_source(dst) as (pdf, expected, warnings):
                with fitz.open(pdf) as doc:
                    total = len(doc)
                if expected is not None and expected != total:
                    raise ValueError("Office export page count mismatch: " + r["document_id"])
        records.append({"document_id": r["document_id"], "sequence": r["sequence"],
                        "category": "lectures", "teacher": None,
                        "original_filename": r["original_filename"],
                        "original_path": "raw/" + r["original_path"],
                        "current_path": rel, "path_history": [rel],
                        "source_sha256": r["source_sha256"], "source_bytes": dst.stat().st_size,
                        "total_pages": total, "available": True, "version_of": None,
                        "warnings": []})
    if set(old) - {d["document_id"] for d in records}:
        raise ValueError("Local registry contains unknown historical documents")
    groups = {}
    for d in records:
        groups.setdefault(d["source_sha256"], []).append(d["document_id"])
    save(registry_path, {"schema_version": 1, "documents": records,
                        "duplicates": [v for v in groups.values() if len(v) > 1]})
    for command in ("render", "validate"):
        if cli.main(["--workspace", str(base), command]):
            raise RuntimeError("Course " + command + " failed; no push performed")
    index = load(base / "sources/index.json")
    for d in index["documents"]:
        for warning in d.get("warnings", []):
            print(d["document_id"], warning)
        if any("Slide count mismatch" in w for w in d.get("warnings", [])):
            raise ValueError("Slide count mismatch; no push performed")
    check_records(raw, entry["documents"])
    return base


def checkout(home, code, url, default_branch):
    target = course_dir(home, code) / "publication"
    if not (target / ".git").is_dir():
        if target.exists() and any(target.iterdir()):
            raise ValueError("Publication checkout is not empty")
        target.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", "--", url, str(target)])
    if git(target, "remote", "get-url", "origin").stdout.strip() != url:
        raise ValueError("Publication checkout remote differs; inspect it before retry")
    if git(target, "status", "--porcelain", "--untracked-files=all").stdout.strip():
        raise ValueError("Publication checkout has uncommitted changes; inspect before retry")
    git(target, "fetch", "--prune", "origin")
    branch = default_branch or "main"
    git(target, "check-ref-format", "--branch", branch)
    head = git(target, "rev-parse", "--verify", "HEAD", allow_failure=True)
    if head.returncode:
        git(target, "symbolic-ref", "HEAD", "refs/heads/" + branch)
    elif git(target, "symbolic-ref", "--short", "HEAD").stdout.strip() != branch:
        raise ValueError("Publication checkout is on a different branch")
    remote = git(target, "rev-parse", "--verify", "refs/remotes/origin/" + branch, allow_failure=True)
    if not remote.returncode:
        if head.returncode:
            git(target, "checkout", "-B", branch, "origin/" + branch)
        elif git(target, "merge-base", "--is-ancestor", remote.stdout.strip(), head.stdout.strip(), allow_failure=True).returncode == 0:
            pass  # local pending commit is recoverable
        else:
            git(target, "merge", "--ff-only", "origin/" + branch)
    elif not head.returncode and default_branch is not None:
        # A first publish may have committed locally but failed before creating the branch.
        # If any other remote branch exists, the missing default branch is unsafe.
        if git(target, "for-each-ref", "--format=%(refname)", "refs/remotes/origin").stdout.strip():
            raise ValueError("Expected remote default branch is missing")
    return target, branch


def clean_json(value):
    """Remove local exporter exception details and volatile timestamps for publication."""
    if isinstance(value, dict):
        return {k: clean_json(v) for k, v in value.items()
                if k not in {"updated_at", "converted_at"}}
    if isinstance(value, list):
        return [clean_json(v) for v in value]
    if isinstance(value, str) and value.startswith("PowerPoint 导出不可用:"):
        return "PowerPoint unavailable; fallback exporter used"
    return value


def write_allowed(target, rel, content, allowed, only_new=False):
    dst = inside(target, rel)
    if dst != target / rel or any(p.is_symlink() for p in [target / rel, *(target / rel).parents] if p != target.parent):
        raise ValueError("Unsafe publication path: " + rel)
    if only_new and dst.exists():
        return
    if dst.is_file() and dst.read_bytes() == content:
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(content)
    allowed.add(rel)


def stage_content(base, target):
    for dirname in ("sources", "review", "protocols"):
        folder = target / dirname
        if folder.is_symlink() or (folder.exists() and any(p.is_symlink() for p in folder.rglob("*"))):
            raise ValueError("Symlink in publication tree: " + dirname)
    reg = load(base / "sources/source_registry.json")
    remote_reg = load(target / "sources/source_registry.json")
    if remote_reg is not None:
        if not isinstance(remote_reg.get("documents"), list):
            raise ValueError("Unrecognized remote registry; migrate manually")
        old = {d["document_id"]: d["source_sha256"] for d in remote_reg["documents"]}
        new = {d["document_id"]: d["source_sha256"] for d in reg["documents"]}
        if any(new.get(k) != v for k, v in old.items()):
            raise ValueError("Remote document IDs/hashes conflict; refusing overwrite")
    elif (target / "sources").exists() and any((target / "sources").iterdir()):
        raise ValueError("Existing remote sources have no compatible registry")
    allowed = set()
    # Verify all existing document folders independently, even if registry was edited.
    for d in reg["documents"]:
        ident = d["document_id"]
        old_manifest = load(target / "sources" / ident / "manifest.json")
        if old_manifest is not None and old_manifest.get("source_sha256") != d["source_sha256"]:
            raise ValueError("Remote manifest identity conflict: " + ident)
        if old_manifest is None and (target / "sources" / ident).exists():
            raise ValueError("Remote source directory lacks a manifest: " + ident)
    def put(rel, only_new=False):
        src = inside(base, rel)
        content = src.read_bytes()
        if src.suffix == ".json":
            content = (json.dumps(clean_json(load(src)), ensure_ascii=False, indent=2) + "\n").encode()
        write_allowed(target, rel, content, allowed, only_new)
    for name in ("source_registry.json", "index.json", "INDEX.md", "SOURCE_REGISTRY.md"):
        put("sources/" + name)
    for d in load(base / "sources/index.json")["documents"]:
        put("sources/" + d["document_id"] + "/manifest.json")
        for p in d["pages"]:
            rel = p["repository_path"]
            if not re.fullmatch(r"sources/[A-Z][A-Z0-9]*/[0-9]{3,}\.(webp|png|jpg)", rel):
                raise ValueError("Unexpected image path: " + rel)
            put(rel)
    put("AGENTS.md", True)
    # Keep any AI/user-authored exam and teaching settings; synchronize only the
    # trans preset when this configuration was originally generated by trans.
    remote_config = target / "course.yaml"
    if not remote_config.exists():
        put("course.yaml", True)
    else:
        if remote_config.is_symlink():
            raise ValueError("Unsafe course config path")
        cfg = yaml.safe_load(remote_config.read_text(encoding="utf-8"))
        local_cfg = config(base)
        if isinstance(cfg, dict) and cfg.get("course") == local_cfg["course"] and cfg.get("groups", {}).get("lectures", {}).get("preset") == "trans":
            if cfg.setdefault("presets", {}).get("trans") != local_cfg["presets"]["trans"]:
                cfg["presets"]["trans"] = local_cfg["presets"]["trans"]
                write_allowed(target, "course.yaml", yaml.safe_dump(cfg, allow_unicode=True).encode(), allowed)
    for dirname in ("protocols", "review"):
        for p in sorted((base / dirname).rglob("*.md")):
            put(p.relative_to(base).as_posix(), True)
    # Keep remote AI decisions; append new pending pages only.
    rel = "review/progress.json"
    current = load(target / rel, {})
    for key, value in load(base / rel, {}).items():
        current.setdefault(key, value)
    write_allowed(target, rel, (json.dumps(current, ensure_ascii=False, indent=2) + "\n").encode(), allowed)
    if not (target / ".gitignore").exists():
        write_allowed(target, ".gitignore", b"raw/\nprint/\n.env\n.venv/\n*.tmp\n", allowed)
    for rel in sorted(allowed):
        git(target, "add", "-f", "--", rel)
    staged = git(target, "diff", "--cached", "--name-only", "-z").stdout.split("\0")
    if any(p not in allowed for p in staged if p):
        raise ValueError("Unexpected staged path; no push performed")
    return allowed


def verify_outgoing(target, branch, base):
    """Reject unexpected local commits, even if the checkout is otherwise clean."""
    remote_ref = "refs/remotes/origin/" + branch
    exists = git(target, "rev-parse", "--verify", remote_ref, allow_failure=True).returncode == 0
    rev_range = remote_ref + "..HEAD" if exists else "HEAD"
    allowed = {"AGENTS.md", "course.yaml", ".gitignore", "review/progress.json",
               "sources/INDEX.md", "sources/SOURCE_REGISTRY.md",
               "sources/index.json", "sources/source_registry.json"}
    for d in load(base / "sources/index.json")["documents"]:
        allowed.add("sources/" + d["document_id"] + "/manifest.json")
        allowed.update(p["repository_path"] for p in d["pages"])
    for dirname in ("review", "protocols"):
        allowed.update(p.relative_to(base).as_posix() for p in (base / dirname).rglob("*.md"))
    for commit in git(target, "rev-list", rev_range).stdout.splitlines():
        # A pending publication commit must be generated by this tool, not a
        # manually created commit or a merge.
        metadata = git(target, "show", "-s", "--format=%s%n%P", commit).stdout.splitlines()
        if not metadata or not metadata[0].startswith("Update course visual archive ") or (len(metadata) > 1 and len(metadata[1].split()) > 1):
            raise ValueError("Unexpected outgoing local commit: " + commit)
        names = git(target, "diff-tree", "--root", "--no-commit-id", "--name-only",
                    "-r", "-z", commit).stdout.split("\0")
        if any(path not in allowed for path in names if path):
            raise ValueError("Unexpected outgoing file in commit: " + commit)


def publish(home, data, code, url, preset=None):
    entry = data.get(code)
    if not entry:
        raise ValueError("Unknown course; register the raw folder first")
    name, remote, branch = private_target(url)
    if entry.get("remote") and entry["remote"]["name"] != name:
        raise ValueError("Course already bound to a different remote")
    if entry.get("remote"):
        remote = entry["remote"]["url"]
    entry = register(home, data, entry["raw"], code, preset)
    entry["remote"] = {"name": name, "url": remote}
    store(home, data)
    base = workspace(home, code, entry)
    target, branch = checkout(home, code, remote, branch)
    stage_content(base, target)
    diff = git(target, "diff", "--cached", "--quiet", allow_failure=True).returncode
    if diff == 1:
        git(target, "commit", "-m", "Update course visual archive " + code)
    elif diff != 0:
        raise RuntimeError("Cannot inspect staged changes")
    verify_outgoing(target, branch, base)
    # Check again immediately before transmitting data.
    private_target(url)
    git(target, "push", "origin", "HEAD:refs/heads/" + branch)
    commit = git(target, "rev-parse", "HEAD").stdout.strip()
    entry["last_commit"] = commit
    entry["branch"] = branch
    store(home, data)
    print("Published", commit)
    print("https://github.com/" + name + "/blob/" + branch + "/sources/INDEX.md")
    return commit
