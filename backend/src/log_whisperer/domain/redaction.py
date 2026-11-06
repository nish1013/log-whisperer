"""Secret masking. Every pattern is bounded so a scan stays linear in the input size."""

import re
from collections.abc import Callable
from dataclasses import dataclass

from log_whisperer.domain.model import RawLog, RedactedLog

Span = tuple[int, int]
Finder = Callable[[str], list[Span]]

_EMAIL_LOCAL = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._%+-")
_EMAIL_LOCAL_MAX = 64
_OCTET = r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)"

_AWS_KEY = re.compile(r"AKIA[0-9A-Z]{16}")
_BEARER = re.compile(r"(?<=Bearer )[A-Za-z0-9._~+/=-]{8,4096}")
_JWT = re.compile(r"eyJ[A-Za-z0-9_-]{1,4096}\.eyJ[A-Za-z0-9_-]{1,4096}\.[A-Za-z0-9_-]{0,4096}")
_API_KEY = re.compile(r"(?<![A-Za-z0-9])(?:sk|pk)(?:-|_live_|_test_)[A-Za-z0-9_-]{16,256}")
_URL_CREDENTIALS = re.compile(
    r"[A-Za-z][A-Za-z0-9+.-]{0,31}://(?P<cred>[^\s:/@]{1,256}:[^\s/@]{1,256})@"
)
_EMAIL_TAIL = re.compile(
    r"[A-Za-z0-9._%+-]@[A-Za-z0-9-]{1,63}(?:\.[A-Za-z0-9-]{1,63}){0,8}\.[A-Za-z]{2,24}\b"
)
_IPV4 = re.compile(rf"(?<![\d.]){_OCTET}(?:\.{_OCTET}){{3}}(?!\.?\d)")
_TOKEN = re.compile(r"(?<![A-Za-z0-9+/_=-])[A-Za-z0-9+/_-]{33,}={0,2}(?![A-Za-z0-9+/_=-])")
_HEX = re.compile(r"[0-9a-fA-F]{33,}")
_MIXED = (re.compile(r"[0-9]"), re.compile(r"[A-Z]"), re.compile(r"[a-z]"))


@dataclass(frozen=True)
class _Rule:
    name: str
    find: Finder


def redact(log: RawLog) -> RedactedLog:
    pieces: list[tuple[str, bool]] = [(log.text, False)]
    count = 0
    for rule in _RULES:
        next_pieces: list[tuple[str, bool]] = []
        for text, masked in pieces:
            if masked:
                next_pieces.append((text, True))
                continue
            cursor = 0
            for start, end in rule.find(text):
                next_pieces.append((text[cursor:start], False))
                next_pieces.append((f"[REDACTED:{rule.name}]", True))
                cursor = end
                count += 1
            next_pieces.append((text[cursor:], False))
        pieces = [(text, masked) for text, masked in next_pieces if text]
    return RedactedLog(text="".join(text for text, _ in pieces), redaction_count=count)


def _spans(pattern: re.Pattern[str], group: int | str = 0) -> Finder:
    def find(text: str) -> list[Span]:
        return [match.span(group) for match in pattern.finditer(text)]

    return find


def _emails(text: str) -> list[Span]:
    spans: list[Span] = []
    floor = 0
    position = 0
    while (match := _EMAIL_TAIL.search(text, position)) is not None:
        start = match.start()
        limit = max(floor, start - _EMAIL_LOCAL_MAX + 1)
        while start > limit and text[start - 1] in _EMAIL_LOCAL:
            start -= 1
        spans.append((start, match.end()))
        floor = position = match.end()
    return spans


def _high_entropy(text: str) -> list[Span]:
    spans: list[Span] = []
    for match in _TOKEN.finditer(text):
        token = match.group(0)
        if _HEX.fullmatch(token) or all(p.search(token) for p in _MIXED):
            spans.append(match.span())
    return spans


_RULES: tuple[_Rule, ...] = (
    _Rule("aws_key", _spans(_AWS_KEY)),
    _Rule("bearer", _spans(_BEARER)),
    _Rule("jwt", _spans(_JWT)),
    _Rule("api_key", _spans(_API_KEY)),
    _Rule("url_credentials", _spans(_URL_CREDENTIALS, "cred")),
    _Rule("email", _emails),
    _Rule("ipv4", _spans(_IPV4)),
    _Rule("high_entropy", _high_entropy),
)
