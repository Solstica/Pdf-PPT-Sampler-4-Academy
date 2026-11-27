import json
import os
import subprocess
from pathlib import Path
import pytest
import pymupdf as fitz
from academy_sampler import trans, trans_publish as pub
from academy_sampler.trans_registry import courses, register, PRESETS, course_dir
from academy_sampler.manifest import sha, load, save


def pdf(path, text="synthetic"):
    path.parent.mkdir(parents=True, exist_ok=True)
    with fitz.open() as doc:
        page = doc.new_page(width=640, height=360)
        page.insert_text((30, 40), text)
        doc.new_page(width=360, height=640)
        doc.save(path)


@pytest.fixture
def setup(tmp_path, monkeypatch):
    home = tmp_path / "state"
    raw = tmp_path / "原件 with spaces"
    raw.mkdir()
    monkeypatch.setenv("ACADEMY_SAMPLER_HOME", str(home))
    for key, value in {"GIT_AUTHOR_NAME": "Synthetic Test",
                       "GIT_AUTHOR_EMAIL": "test@example.invalid",
                       "GIT_COMMITTER_NAME": "Synthetic Test",
                       "GIT_COMMITTER_EMAIL": "test@example.invalid"}.items():
        monkeypatch.setenv(key, value)
    return home, raw


def test_register_and_append(setup, tmp_path, monkeypatch):
    home, raw = setup
    pdf(raw / "lecture 10.PDF", "ten")
    pdf(raw / "lecture 2.pdf", "two")
    hashes = {p.name: sha(p) for p in raw.iterdir()}
    monkeypatch.chdir(tmp_path)
    assert trans.main([str(raw), "cm", "-pre", "4", "--dry-run"]) == 0
    assert set(p.name for p in raw.iterdir()) == set(hashes)
    assert trans.main([str(raw), "cm", "-pre", "4"]) == 0
    assert sha(raw / "CM01.pdf") == hashes["lecture 2.pdf"]
    assert sha(raw / "CM02.pdf") == hashes["lecture 10.PDF"]
    assert trans.main([str(raw), "CM"]) == 0
    assert courses(home)["CM"]["preset"] == 4
    pdf(raw / "lecture 1.pdf", "new")
    assert trans.main([str(raw), "cm"]) == 0
    data = courses(home)
    assert [r["document_id"] for r in data["CM"]["documents"]] == ["CM01", "CM02", "CM03"]
    assert data["CM"]["documents"][0]["original_filename"] == "lecture 2.pdf"
    assert trans.main(["--list"]) == 0
    assert trans.main(["--show", "CM"]) == 0
    other = tmp_path / "other"
    other.mkdir()
    assert trans.main([str(other), "CM"]) == 1
    (raw / "CM01.pdf").write_bytes(b"changed")
    assert trans.main([str(raw), "CM"]) == 1
    assert PRESETS == {1:(1920,90),2:(1600,80),3:(1280,75),4:(1024,70),5:(800,60)}


def test_recover_interrupted_rename(setup):
    home, raw = setup
    pdf(raw / "x.pdf")
    digest = sha(raw / "x.pdf")
    data = {"CM": {"raw": str(raw), "preset": 3, "remote": None, "documents": []}}
    save(home / "courses.json", data)
    record = {"document_id":"CM01","sequence":1,"original_filename":"x.pdf",
              "original_path":"x.pdf","current_path":"CM01.pdf","source_sha256":digest}
    save(course_dir(home, "CM") / "rename-journal.json", {"raw":str(raw),"records":[record]})
    os.link(raw / "x.pdf", raw / "CM01.pdf")
    assert trans.main([str(raw), "CM"]) == 0
    assert not (raw / "x.pdf").exists()
    assert sha(raw / "CM01.pdf") == digest
    assert not (course_dir(home, "CM") / "rename-journal.json").exists()


def test_collision_and_relocation(setup, tmp_path):
    home, raw = setup
    pdf(raw / "A.pdf", "first")
    pdf(raw / "CM01.pdf", "collision")
    assert trans.main([str(raw), "CM"]) == 1
    assert (raw / "A.pdf").exists() and (raw / "CM01.pdf").exists()
    (raw / "CM01.pdf").rename(raw / "B.pdf")
    assert trans.main([str(raw), "CM"]) == 0
    moved = tmp_path / "relocated"
    raw.rename(moved)
    assert trans.main([str(moved), "CM", "--relocate"]) == 0
    assert courses(home)["CM"]["raw"] == str(moved.resolve())


def test_privacy_fail_closed(setup, monkeypatch):
    home, raw = setup
    pdf(raw / "a.pdf")
    assert trans.main([str(raw), "CM"]) == 0
    def rejected(url):
        raise ValueError("public repository")
    monkeypatch.setattr(pub, "private_target", rejected)
    assert trans.main(["CM", "git@github.com:example/course.git"]) == 1
    assert not (course_dir(home, "CM") / "publication").exists()
    assert not (course_dir(home, "CM") / "workspace").exists()
    assert pub.repo_name("git@github.com:Solstica/Test.git") == "solstica/test"
    assert pub.repo_name("https://github.com/solstica/test.git") == "solstica/test"
    with pytest.raises(ValueError):
        pub.repo_name("https://token@github.com/solstica/test.git")


def test_publish_append_and_noop(setup, tmp_path, monkeypatch):
    home, raw = setup
    pdf(raw / "a.pdf")
    assert trans.main([str(raw), "CM", "-pre", "3"]) == 0
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", "--initial-branch=main", str(remote)], check=True, capture_output=True)
    url = "git@github.com:example/course.git"
    monkeypatch.setattr(pub, "private_target", lambda _: ("example/course", str(remote), "main"))
    assert trans.main(["CM", url]) == 0
    target = course_dir(home, "CM") / "publication"
    head = pub.git(target, "rev-parse", "HEAD").stdout.strip()
    manifest = load(target / "sources/CM01/manifest.json")
    assert manifest["original_filename"] == "a.pdf"
    assert manifest["pages"][0]["width"] == 1280
    assert manifest["pages"][0]["parameters"]["quality"] == 75
    tracked = pub.git(target, "ls-files").stdout.splitlines()
    assert all(not p.startswith(("raw/", "print/")) for p in tracked)
    assert all(not p.lower().endswith((".pdf", ".ppt", ".pptx")) for p in tracked)
    assert str(raw) not in (target / "sources/source_registry.json").read_text(encoding="utf8")
    assert trans.main(["CM", url]) == 0
    assert pub.git(target, "rev-parse", "HEAD").stdout.strip() == head
    # Simulate an AI editing review files in an independent remote checkout.
    other = tmp_path / "ai"
    subprocess.run(["git", "clone", str(remote), str(other)], check=True, capture_output=True)
    review = other / "review/00_综合复习稿.md"
    review.write_text("Actual AI review", encoding="utf8")
    progress = load(other / "review/progress.json")
    progress["CM01-P001"] = {"state":"read","reason":"synthetic inspection"}
    save(other / "review/progress.json", progress)
    pub.git(other, "add", "--", "review")
    pub.git(other, "commit", "-m", "AI review")
    pub.git(other, "push", "origin", "main")
    pdf(raw / "new.pdf", "new")
    assert trans.main(["CM", url, "-pre", "4"]) == 0
    assert (target / "review/00_综合复习稿.md").read_text(encoding="utf8") == "Actual AI review"
    progress = load(target / "review/progress.json")
    assert progress["CM01-P001"]["state"] == "read"
    assert progress["CM02-P001"]["state"] == "pending"
    assert load(target / "sources/CM02/manifest.json")["pages"][0]["width"] == 1024
    assert load(target / "sources/CM01/manifest.json")["pages"][0]["width"] == 1024
    assert pub.git(target, "status", "--porcelain").stdout == ""


def test_invalid_source_no_push(setup, monkeypatch):
    home, raw = setup
    (raw / "bad.pdf").write_bytes(b"not pdf")
    assert trans.main([str(raw), "CM"]) == 0
    monkeypatch.setattr(pub, "private_target", lambda _: ("example/course", "unused", "main"))
    assert trans.main(["CM", "git@github.com:example/course.git"]) == 1
    assert not (course_dir(home, "CM") / "publication").exists()


def test_outgoing_unexpected_commit(setup, tmp_path, monkeypatch):
    home, raw = setup
    pdf(raw / "a.pdf")
    assert trans.main([str(raw), "CM", "-pre", "5"]) == 0
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", "--initial-branch=main", str(remote)], check=True, capture_output=True)
    url = "git@github.com:example/course.git"
    monkeypatch.setattr(pub, "private_target", lambda _: ("example/course", str(remote), "main"))
    assert trans.main(["CM", url]) == 0
    target = course_dir(home, "CM") / "publication"
    head = pub.git(target, "rev-parse", "HEAD").stdout.strip()
    (target / "secret.txt").write_text("synthetic secret", encoding="utf8")
    pub.git(target, "add", "--", "secret.txt")
    pub.git(target, "commit", "-m", "Unexpected local change")
    assert trans.main(["CM", url]) == 1
    assert pub.git(remote, "rev-parse", "refs/heads/main").stdout.strip() == head


def test_installed_console_entrypoint():
    import sysconfig
    import sys
    scripts = Path(sysconfig.get_path("scripts"))
    exe = scripts / ("trans.exe" if sys.platform == "win32" else "trans")
    result = subprocess.run([str(exe), "--help"], capture_output=True, text=True)
    assert result.returncode == 0 and "preset-number" in result.stdout


def test_group_sync_and_move_preserves_paths(setup, tmp_path, monkeypatch):
    home, raw = setup
    pdf(raw / "a.pdf")
    assert trans.main([str(raw), "CM", "-pre", "3"]) == 0
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", "--initial-branch=main", str(remote)], check=True, capture_output=True)
    url = "git@github.com:example/course.git"
    monkeypatch.setattr(pub, "private_target", lambda _: ("example/course", str(remote), "main"))
    assert trans.main(["CM", url]) == 0
    target = course_dir(home, "CM") / "publication"
    original_image = target / "sources/CM01/001.webp"
    before = sha(original_image)
    pdf(raw / "Notes" / "Week 1" / "notes.pdf")
    pdf(raw / "Homework" / "hw.pdf")
    assert trans.main(["CM", "--group", "Notes", "-pre", "1"]) == 0
    # Natural ordering assigns homework CM02, notes CM03; only notes publish.
    notes = target / "sources/by-group/Notes/Week 1/CM03/manifest.json"
    assert notes.exists()
    assert load(notes)["pages"][0]["width"] == 1920
    assert not (target / "sources/by-group/Homework/CM02").exists()
    assert sha(original_image) == before
    assert "Notes/Week 1" in (target / "sources/GROUPS.md").read_text(encoding="utf8")
    assert trans.main(["CM"]) == 0
    homework = target / "sources/by-group/Homework/CM02/manifest.json"
    assert load(homework)["pages"][0]["width"] == 1280
    assert load(notes)["pages"][0]["width"] == 1920
    (raw / "Moved").mkdir()
    (raw / "CM01.pdf").rename(raw / "Moved/CM01.pdf")
    assert trans.main(["CM"]) == 0
    assert original_image.exists() and sha(original_image) == before
    assert load(target / "sources/CM01/manifest.json")["source_group"] == "Moved"
    assert load(target / "sources/CM01/manifest.json")["original_filename"] == "a.pdf"
    assert len(courses(home)["CM"]["documents"]) == 3
    head = pub.git(target, "rev-parse", "HEAD").stdout.strip()
    assert trans.main(["CM"]) == 0
    assert pub.git(target, "rev-parse", "HEAD").stdout.strip() == head
    from academy_sampler.workspace import batch
    base = course_dir(home, "CM") / "workspace"
    assert batch(base, "CM03", 2)[0][0]["image"].startswith("sources/by-group/Notes/Week 1/")


def test_ambiguous_move_refused(setup):
    home, raw = setup
    pdf(raw / "a.pdf")
    assert trans.main([str(raw), "CM"]) == 0
    import shutil
    (raw / "A").mkdir()
    (raw / "B").mkdir()
    shutil.copy2(raw / "CM01.pdf", raw / "A/CM01.pdf")
    (raw / "CM01.pdf").rename(raw / "B/CM01.pdf")
    assert trans.main([str(raw), "CM"]) == 1
    assert len(courses(home)["CM"]["documents"]) == 1
