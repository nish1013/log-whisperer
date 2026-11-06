"""Python traceback parsing. Pure, linear in the input size, and it never raises."""

import re
from collections import Counter
from dataclasses import dataclass

from log_whisperer.domain.model import (
    ChainReason,
    ExceptionBlock,
    Frame,
    LogKind,
    ParsedLog,
    RedactedLog,
)

MAX_CHARS = 60_000
TAIL_LINES = 200
LIBRARY_MARKERS = ("site-packages", "dist-packages", "/lib/python3.", "<frozen", "<string>")

_LEVEL = r"(?:DEBUG|INFO|WARNING|WARN|ERROR|CRITICAL|FATAL)"
_PREFIX = re.compile(
    r"(?:\[?\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d{1,9})?(?:Z|[+-]\d{2}:?\d{2})?\]?[ \t]+"
    rf"(?:\[?{_LEVEL}\]?[ \t]+)?(?:[\w.\-]{{1,100}}(?:\[\d{{1,10}}\])?[ \t]+-[ \t])?"
    rf"|{_LEVEL}:[\w.\-]{{1,100}}:"
    rf"|\[?{_LEVEL}\]?[ \t]+[\w.\-]{{1,100}}[ \t]+-[ \t])"
)
_HEADER = "Traceback (most recent call last):"
_CAUSE = "The above exception was the direct cause of the following exception:"
_CONTEXT = "During handling of the above exception, another exception occurred:"
_FRAME = re.compile(
    r'[ \t]*File "(?P<file>[^"]{1,4096})", line (?P<line>\d{1,9}), in (?P<func>.{1,512})'
)
_REPEATED = re.compile(r"[ \t]*\[Previous line repeated \d{1,12} more times?\]")
_CARETS = re.compile(r"[ \t]*[\^~]+[ \t\^~]*")
_EXCEPTION = re.compile(r"(?P<type>[A-Za-z_][\w.]{0,255})(?::[ ]?(?P<message>.*))?")
_LEVEL_WORD = re.compile(r"\b(DEBUG|INFO|WARNING|ERROR|CRITICAL)\b")


@dataclass(frozen=True)
class _Line:
    prefix: str
    body: str


@dataclass(frozen=True)
class _Block:
    start: int
    end: int
    exception: ExceptionBlock


def parse(log: RedactedLog) -> ParsedLog:
    lines = _split(log.text)
    truncated = len(log.text) > MAX_CHARS
    chain = _last_chain(_blocks(lines), lines)
    if not chain:
        levels = _count_levels(lines)
        kind: LogKind = "generic_log" if levels else "unknown"
        return ParsedLog(kind, (), None, None, levels, truncated)
    exceptions = tuple(block.exception for block in chain)
    return ParsedLog("python_traceback", exceptions, 0, _culprit(exceptions), {}, truncated)


def focus(log: RedactedLog) -> RedactedLog:
    if len(log.text) <= MAX_CHARS:
        return log
    raw = log.text.split("\n")
    lines = _split(log.text)
    kept = set(range(max(0, len(raw) - TAIL_LINES), len(raw)))
    previous: _Block | None = None
    for block in _blocks(lines):
        start = block.start
        if previous is not None and _link(lines, previous.end, block.start) is not None:
            start = previous.end
        kept.update(range(start, block.end))
        previous = block
    return RedactedLog("\n".join(raw[i] for i in sorted(kept)), log.redaction_count)


def _split(text: str) -> list[_Line]:
    result: list[_Line] = []
    for raw in text.split("\n"):
        line = raw.removesuffix("\r")
        match = _PREFIX.match(line)
        prefix = match.group(0) if match else ""
        result.append(_Line(prefix, line[len(prefix) :]))
    return result


def _blocks(lines: list[_Line]) -> list[_Block]:
    blocks: list[_Block] = []
    i = 0
    while i < len(lines):
        block = _read_block(lines, i) if lines[i].body.strip() == _HEADER else None
        if block is None:
            i += 1
            continue
        blocks.append(block)
        i = block.end
    return blocks


def _read_block(lines: list[_Line], start: int) -> _Block | None:
    frames: list[Frame] = []
    i = start + 1
    while i < len(lines):
        body = lines[i].body
        frame = _FRAME.fullmatch(body.rstrip())
        if frame is not None:
            code, i = _read_code(lines, i + 1)
            _append_frame(frames, _frame(frame, code))
        elif not body.strip():
            return None
        elif body[0] in " \t":
            i += 1
        else:
            return _finish_block(lines, start, i, tuple(frames))
    return None


def _finish_block(
    lines: list[_Line], start: int, i: int, frames: tuple[Frame, ...]
) -> _Block | None:
    exception = _EXCEPTION.fullmatch(lines[i].body.rstrip())
    if exception is None:
        return None
    message = [exception.group("message") or ""]
    prefix = lines[i].prefix
    end = i + 1
    while end < len(lines) and _continues(lines[end], prefix):
        message.append(lines[end].body.rstrip())
        end += 1
    block = ExceptionBlock(exception.group("type"), "\n".join(message).strip(), frames, None)
    return _Block(start, end, block)


def _read_code(lines: list[_Line], i: int) -> tuple[str | None, int]:
    if i >= len(lines):
        return None, i
    body = lines[i].body
    if not body.strip() or body[0] not in " \t":
        return None, i
    if _FRAME.fullmatch(body.rstrip()) or _REPEATED.fullmatch(body) or _CARETS.fullmatch(body):
        return None, i
    return body.strip(), i + 1


def _frame(match: re.Match[str], code: str | None) -> Frame:
    file = match.group("file")
    return Frame(
        file=file,
        line=int(match.group("line")),
        func=match.group("func").strip(),
        code=code,
        is_user_code=not any(marker in file for marker in LIBRARY_MARKERS),
    )


def _append_frame(frames: list[Frame], frame: Frame) -> None:
    if not frames or frames[-1] != frame:
        frames.append(frame)


def _continues(line: _Line, prefix: str) -> bool:
    body = line.body.strip()
    if not body or line.prefix != prefix:
        return False
    return body not in (_HEADER, _CAUSE, _CONTEXT)


def _last_chain(blocks: list[_Block], lines: list[_Line]) -> list[_Block]:
    chain: list[_Block] = []
    previous: _Block | None = None
    for block in blocks:
        reason = _link(lines, previous.end, block.start) if previous is not None else None
        if reason is None:
            chain = [block]
        else:
            e = block.exception
            linked = ExceptionBlock(e.type, e.message, e.frames, reason)
            chain.append(_Block(block.start, block.end, linked))
        previous = block
    return chain


def _link(lines: list[_Line], start: int, end: int) -> ChainReason | None:
    reason: ChainReason | None = None
    for line in lines[start:end]:
        body = line.body.strip()
        if not body:
            continue
        if reason is None and body == _CAUSE:
            reason = "cause"
        elif reason is None and body == _CONTEXT:
            reason = "context"
        else:
            return None
    return reason


def _culprit(exceptions: tuple[ExceptionBlock, ...]) -> Frame | None:
    for exception in exceptions:
        user = [frame for frame in exception.frames if frame.is_user_code]
        if user:
            return user[-1]
    return None


def _count_levels(lines: list[_Line]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for line in lines:
        match = _LEVEL_WORD.search(line.prefix + line.body)
        if match is not None:
            counts[match.group(1)] += 1
    return dict(counts)
