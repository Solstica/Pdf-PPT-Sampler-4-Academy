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
PROGRESS_MODE = ContextVar("progress_mode", default="auto")


def default_language():
    return os.environ.get("ACADEMY_SAMPLER_LANG", "en").lower()


def default_progress_mode():
    return os.environ.get("ACADEMY_SAMPLER_PROGRESS", "auto").lower()


def msys_pty(stream):
    """Recognize Windows MSYS2/Cygwin pseudo-terminal pipes, not arbitrary pipes."""
    if os.name != "nt":
        return False
    try:
        import ctypes
        from ctypes import wintypes
        import msvcrt
        handle = msvcrt.get_osfhandle(stream.fileno())
        buffer = ctypes.create_string_buffer(4096)
        query = ctypes.windll.kernel32.GetFileInformationByHandleEx
        query.argtypes = (wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD)
        query.restype = wintypes.BOOL
        if not query(handle, 2, buffer, len(buffer)):  # FileNameInfo
            return False
        length = int.from_bytes(buffer.raw[:4], "little")
        name = buffer.raw[4:4+length].decode("utf-16-le", errors="replace")
        return bool(re.search(r"(?:msys|cygwin)-[^\\]*-pty\d+-(?:to|from)-master", name, re.I))
    except (OSError, ValueError, AttributeError, ImportError):
        return False


def live_enabled(stream):
    mode = PROGRESS_MODE.get()
    if mode == "live":
        return True
    if mode == "log" or os.environ.get("TERM") == "dumb":
        return False
    return stream.isatty() or msys_pty(stream)


def terminal_columns(stream):
    try:
        cols = os.get_terminal_size(stream.fileno()).columns
        if cols > 0:
            return cols
    except (OSError, ValueError, AttributeError):
        pass
    return shutil.get_terminal_size(fallback=(80, 24)).columns or 80


def display_width(text):
    return sum(0 if unicodedata.combining(c) else
               2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in text)


def fit_line(text, limit):
    if display_width(text) <= limit:
        return text
    chars, used = [], 0
    for c in text:
        w = display_width(c)
        if used + w > max(0, limit - 3):
            break
        chars.append(c)
        used += w
    return "".join(chars) + "." * min(3, limit)


class ProgressLine:
    """Refresh a single bounded-width line. No ANSI/cursor dependency."""
    def __init__(self, stream):
        self.stream = stream
        self.live = live_enabled(stream)
        self.last_width = 0

    @property
    def limit(self):
        return max(1, terminal_columns(self.stream) - 1)

    def write(self, text, final=False):
        if not self.live:
            write_text(self.stream, text + "\n")
            return
        if final:
            # Preserve complete final messages (e.g. Git errors).
            padding = " " * max(0, self.last_width - display_width(text))
            write_text(self.stream, "\r" + text + padding + "\n")
            self.last_width = 0
            return
        text = fit_line(text, self.limit)
        width = display_width(text)
        padding = " " * max(0, min(self.last_width, self.limit) - width)
        write_text(self.stream, "\r" + text + padding)
        self.last_width = width

    def finish(self):
        if self.live and self.last_width:
            write_text(self.stream, "\n")
            self.last_width = 0


def compact_page_line(limit, label, fraction, done, total, status, eta, rate, counts,
                      size_text, elapsed, new_size, raw_size):
    """Keep percent/count/ETA visible before optional size and detail columns."""
    bar_width = max(4, min(28, limit // 8))
    filled = min(bar_width, int(bar_width * fraction))
    bar = "=" * filled + (">" if filled < bar_width else "") + "-" * max(0, bar_width - filled - 1)
    # For complete bars the final dash count is zero.
    head = f"{label} [{bar}] {fraction:5.1%} {done}/{total}"
    primary = f" ETA {eta}"
    if display_width(head + primary) > limit:
        head = f"{label} {fraction:5.1%} {done}/{total}"
    line = head + primary
    candidates = [size_text, status, f"{rate:.1f}{tr('p/s','页/s')}",
                  f"{tr('new','新')} {counts['converted']} {tr('cache','缓存')} {counts['skipped']} {tr('failed','失败')} {counts['failed']}",
                  f"{tr('elapsed','耗时')} {elapsed}", new_size, raw_size]
    for item in candidates:
        if item and display_width(line + " | " + item) <= limit:
            line += " | " + item
    return fit_line(line, limit)


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
        self.line = ProgressLine(self.stream)
        self.tty = self.line.live
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
        self._show(force=not self.tty)

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
        size_text = new_size = raw_size = ''
        if self.documents:
            estimate = self.estimated_bytes()
            estimate_text = human_bytes(estimate)
            if estimate is not None and self.done != self.total:
                estimate_text = "~" + estimate_text
            size_text = f"{human_bytes(self.image_bytes)} / {estimate_text}"
            new_size = f"{tr('new bytes','新生成')} {human_bytes(self.new_bytes)}"
            line += f" | {tr('images','图像')} {size_text} | {new_size}"
            if self.source_bytes is not None:
                raw_size = f"{tr('raw','原件')} {human_bytes(self.source_bytes)}"
                line += " | " + raw_size
        if self.tty:
            compact = compact_page_line(self.line.limit, self.label, fraction, self.done,
                                        self.total, status, eta, rate, self.counts, size_text,
                                        duration(elapsed), new_size, raw_size)
            self.line.write(compact, final=final)
        else:
            self.line.write(line, final=final)
        self.last_print = now

    def close(self):
        if not self.closed:
            self._show(force=True, final=True)
            if self.tty:
                write_text(self.stream, f"{tr('Result','结果')}: {tr('new','新增')} {self.counts['converted']} | "
                           f"{tr('cache','缓存')} {self.counts['skipped']} | {tr('failed','失败')} {self.counts['failed']} | "
                           f"{tr('elapsed','耗时')} {duration(self.clock() - self.started)} | "
                           + (tr('complete','完成') if self.done == self.total and not self.counts['failed'] else tr('stopped','中止')) + "\n")
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
