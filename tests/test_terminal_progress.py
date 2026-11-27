import io
from academy_sampler.terminal_progress import PageProgress, GitProgress, duration
from academy_sampler.renderer import render
from academy_sampler.workspace import init
from academy_sampler.registry import ingest
from academy_sampler.config import config, parameters
from academy_sampler import trans_publish as pub
import pymupdf as fitz
import subprocess
import sys
import pytest


def test_page_progress_counts_and_eta():
    stream = io.StringIO()
    tick = [0.0]
    with PageProgress(4, stream=stream, clock=lambda: tick[0]) as bar:
        bar.document("CM01", 4)
        tick[0] = 2
        bar.advance("CM01", 1, "converted")
        tick[0] = 4
        bar.advance("CM01", 2, "skipped")
        assert "ETA 00:00:04" in stream.getvalue()
        tick[0] = 6
        bar.advance("CM01", 3, "failed")
        tick[0] = 8
        bar.advance("CM01", 4, "converted")
    assert "4/4 pages" in stream.getvalue()
    assert "new 2 cache 1 failed 1" in stream.getvalue()
    assert "stopped" in stream.getvalue()
    assert duration(3661) == "01:01:01"


def test_git_eta_is_object_based():
    tick = [0.0]
    bar = GitProgress(clock=lambda: tick[0])
    assert bar.annotate("Counting objects: 100%") == "Counting objects: 100%"
    assert "ETA --:--:--" in bar.annotate("Writing objects:  10% (10/100)")
    tick[0] = 5
    assert "ETA ~00:00:10" in bar.annotate("Writing objects:  40% (40/100), 2 MiB | 400 KiB/s")
    assert "waiting for Git confirmation" in bar.annotate("Writing objects: 100% (100/100), done.")


def test_render_callback_on_real_pages_and_cache(tmp_path, monkeypatch):
    root = tmp_path / "course"
    init(root)
    src = root / "raw/lectures/a.pdf"
    with fitz.open() as pdf:
        pdf.new_page()
        pdf.new_page()
        pdf.save(src)
    c = config(root)
    d = ingest(root, c)["documents"][0]
    events = []
    callback = lambda *args: events.append(args)
    params = parameters(c, "lectures", edge=200)
    render(root, d, params, on_page=callback)
    assert events == [("L01", 1, "converted"), ("L01", 2, "converted")]
    events.clear()
    render(root, d, params, on_page=callback)
    assert events == [("L01", 1, "skipped"), ("L01", 2, "skipped")]
    from PIL import Image
    original = Image.Image.save
    def broken(self, fp, *args, **kwargs):
        if str(fp).endswith("001.webp.tmp"):
            raise OSError("synthetic failure")
        return original(self, fp, *args, **kwargs)
    monkeypatch.setattr(Image.Image, "save", broken)
    events.clear()
    render(root, d, params, force=True, on_page=callback)
    assert events == [("L01", 1, "failed"), ("L01", 2, "converted")]


@pytest.mark.parametrize("exitcode", [0, 7])
def test_push_stream_cr_and_exit(tmp_path, monkeypatch, capsys, exitcode):
    real_popen = subprocess.Popen
    commands = []
    def substitute(cmd, **kwargs):
        commands.append(cmd)
        return real_popen([sys.executable, "-c",
            "import sys; sys.stderr.write('Writing objects:  20% (2/10)\\rWriting objects: 100% (10/10), done.\\n'); sys.stderr.flush(); sys.exit(" + str(exitcode) + ")"], **kwargs)
    monkeypatch.setattr(pub.subprocess, "Popen", substitute)
    if exitcode:
        with pytest.raises(RuntimeError, match="Git push failed"):
            pub.push_live(tmp_path, "main")
    else:
        pub.push_live(tmp_path, "main")
    output = capsys.readouterr().err
    assert "--progress" in commands[0]
    assert "Writing objects:  20%" in output
    assert "waiting for Git confirmation" in output
    assert ("Git push confirmed" in output) == (exitcode == 0)



def test_size_estimate_by_preset_and_chinese():
    from academy_sampler.terminal_progress import LANGUAGE, human_bytes
    token = LANGUAGE.set("zh")
    try:
        stream = io.StringIO()
        plan = {"A01": (2, 3), "A02": (2, 3), "A03": (2, 1)}
        with PageProgress(6, stream=stream, documents=plan, source_bytes=10000) as bar:
            assert bar.estimated_bytes() is None
            bar.record_size("A01", 1, 100)
            bar.advance("A01", 1, "converted")
            assert bar.estimated_bytes() is None  # G1 still unsampled
            bar.record_size("A03", 1, 400)
            bar.advance("A03", 1, "skipped")
            assert bar.estimated_bytes() == 1200
            assert bar.image_bytes == 500 and bar.new_bytes == 100
            for ident, page, size in [("A01",2,200),("A02",1,300),("A02",2,500),("A03",2,600)]:
                bar.record_size(ident, page, size)
                bar.advance(ident,page,"converted")
            assert bar.estimated_bytes() == 2100
            assert bar.new_bytes == 1700
        assert "图像" in stream.getvalue() and "预计剩余" in stream.getvalue()
        assert "2.05 KiB" in stream.getvalue()
        assert "写入对象:" in GitProgress().annotate("Writing objects: 100% (10/10), done.")
        assert human_bytes(1024) == "1.00 KiB"
    finally:
        LANGUAGE.reset(token)



@pytest.mark.parametrize("lang", ["en", "zh"])
@pytest.mark.parametrize("columns", [60, 80, 120, 200])
def test_live_progress_stays_on_one_line(monkeypatch, lang, columns):
    from academy_sampler import terminal_progress as tp
    stream = io.StringIO()
    monkeypatch.setattr(tp, "terminal_columns", lambda _: columns)
    mode = tp.PROGRESS_MODE.set("live")
    language = tp.LANGUAGE.set(lang)
    tick = [0.]
    try:
        with PageProgress(4, stream=stream, clock=lambda: tick[0],
                          documents={"CM01": (4, 3)}, source_bytes=10**6) as bar:
            for page in range(1, 5):
                tick[0] += 1
                bar.record_size("CM01", page, 40000)
                bar.advance("CM01", page, "converted")
            ongoing = stream.getvalue()
            assert "\r" in ongoing and "\n" not in ongoing
            for frame in ongoing.split("\r"):
                assert tp.display_width(frame) < columns
        out = stream.getvalue()
        assert out.count("\n") == 2
        assert "100.0%" in out and "4/4" in out
        assert "ETA 00:00:00" in out
    finally:
        tp.LANGUAGE.reset(language)
        tp.PROGRESS_MODE.reset(mode)


def test_auto_and_log_modes(monkeypatch):
    from academy_sampler import terminal_progress as tp
    stream = io.StringIO()
    monkeypatch.setattr(tp, "msys_pty", lambda _: True)
    monkeypatch.setenv("TERM", "xterm")
    assert tp.live_enabled(stream)
    token = tp.PROGRESS_MODE.set("log")
    try:
        assert not tp.live_enabled(stream)
        line = tp.ProgressLine(stream)
        line.write("first")
        line.write("second", final=True)
        assert stream.getvalue() == "first\nsecond\n"
    finally:
        tp.PROGRESS_MODE.reset(token)
