"""Terminal-only progress reporting. No changes to course data or cache keys."""
import os
import shutil
import unicodedata
from contextvars import ContextVar
import re
import sys
import time
from collections import Counter, deque


LANGUAGE = ContextVar("terminal_language", default="en")


def default_language():
    return os.environ.get("ACADEMY_SAMPLER_LANG", "en").lower()


def tr(en, zh):
    return zh if LANGUAGE.get() == "zh" else en


def human_bytes(value):
    if value is None:
        return "--"
    n = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(n) < 1024 or unit == "TiB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.2f} {unit}"
        n /= 1024


def write_text(stream, value):
    try:
        stream.write(value)
    except UnicodeEncodeError:
        encoding = stream.encoding or "ascii"
        stream.write(value.encode(encoding, errors="replace").decode(encoding))
    stream.flush()


def duration(seconds):
    seconds = max(0, int(seconds + 0.5))
    hours, rest = divmod(seconds, 3600)
    minutes, seconds = divmod(rest, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def stage(message, zh=None):
    write_text(sys.stderr, (tr(message, zh) if zh is not None else message) + "\n")


class PageProgress:
    """Count completed page attempts, including cache hits and failures."""
    def __init__(self, total, label=None, stream=None, clock=None, documents=None, source_bytes=None):
        self.total = total
        self.label = label or tr("Render", "转换")
        self.documents = documents or {}  # document ID -> (selected page count, preset key)
        self.source_bytes = source_bytes
        self.sizes = {}  # (document ID, page) -> validated image bytes
        self.image_bytes = 0
        self.new_bytes = 0
        self.by_doc = Counter()
        self.doc_bytes = Counter()
        self.by_preset = Counter()
        self.preset_bytes = Counter()
        self.stream = stream if stream is not None else sys.stderr
        self.clock = clock if clock is not None else time.monotonic
        self.tty = self.stream.isatty() and shutil.get_terminal_size(fallback=(120, 24)).columns >= 190
        self.started = self.clock()
        self.last_print = self.started
        self.last_width = 0
        self.counts = Counter()
        self.done = 0
        self.samples = deque([(self.started, 0)], maxlen=41)
        self.current = ""
        self.closed = False
        self._show(force=True)

    def document(self, ident, pages):
        self.current = f"{ident} (0/{pages})"
        self._show(force=True)

    def record_size(self, ident, page, size):
        if size > 0:
            self.sizes[(ident, page)] = size

    def estimated_bytes(self):
        """Actual validated bytes plus per-document (or same-preset) sample means."""
        if self.counts["failed"]:
            return None
        if self.done == self.total:
            return self.image_bytes
        if not self.documents:
            return None
        estimate = self.image_bytes
        for ident, (pages, preset) in self.documents.items():
            remaining = pages - self.by_doc[ident]
            if remaining <= 0:
                continue
            if self.by_doc[ident]:
                mean = self.doc_bytes[ident] / self.by_doc[ident]
            elif self.by_preset[preset]:
                mean = self.preset_bytes[preset] / self.by_preset[preset]
            else:
                return None
            estimate += remaining * mean
        return round(estimate)

    def advance(self, ident, page, status):
        if status not in ("converted", "skipped", "failed"):
            raise ValueError("Unknown page outcome")
        self.done += 1
        self.counts[status] += 1
        size = self.sizes.pop((ident, page), 0)
        if size and status != "failed":
            self.image_bytes += size
            self.new_bytes += size if status == "converted" else 0
            self.by_doc[ident] += 1
            self.doc_bytes[ident] += size
            if ident in self.documents:
                preset = self.documents[ident][1]
                self.by_preset[preset] += 1
                self.preset_bytes[preset] += size
        self.current = f"{ident}-P{page:03d}"
        self.samples.append((self.clock(), self.done))
        self._show(force=self.done == self.total)

    def _show(self, force=False, final=False):
        now = self.clock()
        interval = 0.1 if self.tty else 1.0
        if not force and now - self.last_print < interval:
            return
        elapsed = now - self.started
        fraction = min(1.0, self.done / self.total) if self.total else 1.0
        filled = int(20 * fraction)
        bar = "#" * filled + "-" * (20 - filled)
        t0, n0 = self.samples[0]
        rate = (self.done - n0) / (now - t0) if now > t0 else 0
        remaining = max(0, self.total - self.done)
        eta = duration(remaining / rate) if remaining and rate > 0 and self.done >= 2 else ("00:00:00" if not remaining else "--:--:--")
        status = tr("complete", "完成") if final and self.done == self.total and not self.counts["failed"] else (tr("stopped", "中止") if final else self.current)
        line = (f"{self.label} [{bar}] {fraction:6.1%} {self.done}/{self.total} {tr('pages','页')} | "
                f"{tr('new','新增')} {self.counts['converted']} {tr('cache','缓存')} {self.counts['skipped']} "
                f"{tr('failed','失败')} {self.counts['failed']} | {rate:.1f} {tr('p/s','页/s')} | "
                f"{tr('elapsed','耗时')} {duration(elapsed)} {tr('ETA','预计剩余')} {eta} | {status}")
        if self.documents:
            estimate = self.estimated_bytes()
            estimate_text = human_bytes(estimate)
            if estimate is not None and self.done != self.total:
                estimate_text = "~" + estimate_text
            line += (f" | {tr('images','图像')} {human_bytes(self.image_bytes)}"
                     f" / {tr('est.','预计')} {estimate_text}"
                     f" | {tr('new bytes','新生成')} {human_bytes(self.new_bytes)}")
            if self.source_bytes is not None:
                line += f" | {tr('raw','原件')} {human_bytes(self.source_bytes)}"
        width = sum(2 if unicodedata.east_asian_width(c) in ("W","F") else 1 for c in line)
        if self.tty:
            write_text(self.stream, "\r" + line + " " * max(0, self.last_width - width) + ("\n" if final else ""))
            self.last_width = width
        else:
            write_text(self.stream, line + "\n")
        self.last_print = now

    def close(self):
        if not self.closed:
            self._show(force=True, final=True)
            self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class GitProgress:
    """Pass Git's own output through; estimate remaining object-writing time only."""
    writing = re.compile(r"^Writing objects:\s+(\d+)%\s+\((\d+)/(\d+)\)")

    def __init__(self, clock=None):
        self.clock = clock if clock is not None else time.monotonic
        self.first = None

    def annotate(self, line):
        match = self.writing.match(line)
        translated = line
        if LANGUAGE.get() == "zh":
            prefixes = {"Enumerating objects:": "枚举对象:", "Counting objects:": "统计对象:",
                        "Compressing objects:": "压缩对象:", "Writing objects:": "写入对象:",
                        "remote: Resolving deltas:": "远端解析差异:", "Resolving deltas:": "解析差异:",
                        "Total ": "合计 "}
            for prefix, replacement in prefixes.items():
                if line.startswith(prefix):
                    translated = replacement + line[len(prefix):]
                    if translated.endswith("done."):
                        translated = translated[:-5] + "完成."
                    break
        if not match:
            return translated
        percent, done, total = map(int, match.groups())
        now = self.clock()
        if done >= total:
            return translated + tr(" | object writing complete; waiting for Git confirmation", " | 对象写入完成，等待 Git 确认")
        if self.first is None or done < self.first[1]:
            self.first = (now, done)
            return translated + tr(" | object ETA --:--:--", " | 对象预计剩余 --:--:--")
        start, initial = self.first
        if done <= initial or now <= start:
            return translated + tr(" | object ETA --:--:--", " | 对象预计剩余 --:--:--")
        eta = (total - done) * (now - start) / (done - initial)
        return translated + tr(" | object ETA ~", " | 对象预计剩余 ~") + duration(eta)
