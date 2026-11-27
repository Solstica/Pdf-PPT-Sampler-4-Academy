"""Terminal-only progress reporting. No changes to course data or cache keys."""
import re
import sys
import time
from collections import Counter, deque


def duration(seconds):
    seconds = max(0, int(seconds + 0.5))
    hours, rest = divmod(seconds, 3600)
    minutes, seconds = divmod(rest, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def stage(message):
    print(message, file=sys.stderr, flush=True)


class PageProgress:
    """Count completed page attempts, including cache hits and failures."""
    def __init__(self, total, label="Render", stream=None, clock=None):
        self.total = total
        self.label = label
        self.stream = stream if stream is not None else sys.stderr
        self.clock = clock if clock is not None else time.monotonic
        self.tty = self.stream.isatty()
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

    def advance(self, ident, page, status):
        if status not in ("converted", "skipped", "failed"):
            raise ValueError("Unknown page outcome")
        self.done += 1
        self.counts[status] += 1
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
        status = "complete" if final and self.done == self.total and not self.counts["failed"] else ("stopped" if final else self.current)
        line = (f"{self.label} [{bar}] {fraction:6.1%} {self.done}/{self.total} pages | "
                f"new {self.counts['converted']} cache {self.counts['skipped']} "
                f"failed {self.counts['failed']} | {rate:.1f} p/s | "
                f"elapsed {duration(elapsed)} ETA {eta} | {status}")
        if self.tty:
            self.stream.write("\r" + line.ljust(self.last_width) + ("\n" if final else ""))
            self.last_width = len(line)
        else:
            self.stream.write(line + "\n")
        self.stream.flush()
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
        if not match:
            return line
        percent, done, total = map(int, match.groups())
        now = self.clock()
        if done >= total:
            return line + " | object writing complete; waiting for Git confirmation"
        if self.first is None or done < self.first[1]:
            self.first = (now, done)
            return line + " | object ETA --:--:--"
        start, initial = self.first
        if done <= initial or now <= start:
            return line + " | object ETA --:--:--"
        eta = (total - done) * (now - start) / (done - initial)
        return line + " | object ETA ~" + duration(eta)
