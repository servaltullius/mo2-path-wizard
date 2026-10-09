"""Qt QSettings(IniFormat) 값 인코딩/디코딩.

MO2는 ModOrganizer.ini를 QSettings로 읽고 쓰므로, 경로 값도 Qt 규칙을 그대로 따라야 한다.
- 일반 문자열: `\\`, `"` 이스케이프, `,` `;` `=` 또는 앞뒤 공백이 있으면 값 전체를 따옴표로 감싼다.
- @ByteArray(...): 0x80 이상 바이트는 `\\xNN`, `\\xNN` 직후의 16진수 문자도 `\\xNN`으로 이스케이프한다.
  (Qt는 `\\x` 뒤의 16진수를 탐욕적으로 읽기 때문)
"""

from __future__ import annotations

_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")
_SIMPLE_ESCAPES = {
    "\a": "\\a",
    "\b": "\\b",
    "\f": "\\f",
    "\n": "\\n",
    "\r": "\\r",
    "\t": "\\t",
    "\v": "\\v",
    "\\": "\\\\",
    '"': '\\"',
}
_SIMPLE_UNESCAPES = {
    "a": "\a",
    "b": "\b",
    "f": "\f",
    "n": "\n",
    "r": "\r",
    "t": "\t",
    "v": "\v",
    "\\": "\\",
    '"': '"',
    "'": "'",
    "?": "?",
    ";": ";",
    ",": ",",
    "=": "=",
}


def _needs_quotes(text: str) -> bool:
    if not text:
        return False
    return any(ch in text for ch in ",;=") or text[0].isspace() or text[-1].isspace()


def escape_string(value: str) -> str:
    """일반 문자열 값을 Qt INI 형식으로 이스케이프한다(비 ASCII는 UTF-8 그대로)."""
    out = "".join(_SIMPLE_ESCAPES.get(ch, ch) for ch in value)
    return f'"{out}"' if _needs_quotes(value) else out


def unescape_string(raw: str) -> str:
    """Qt INI 값(따옴표/이스케이프 포함)을 실제 문자열로 되돌린다.

    `\\xNN`은 Qt처럼 16진수를 탐욕적으로 읽어 한 문자(코드 포인트)로 만든다.
    여러 값(`a, b`) 목록은 다루지 않고 하나의 문자열로 취급한다.
    """
    out: list[str] = []
    in_quotes = False
    i = 0
    n = len(raw)
    while i < n:
        ch = raw[i]
        if ch == '"':
            in_quotes = not in_quotes
            i += 1
            continue
        if ch != "\\" or i + 1 >= n:
            out.append(ch)
            i += 1
            continue
        nxt = raw[i + 1]
        if nxt == "x":
            j = i + 2
            while j < n and raw[j] in _HEX_DIGITS:
                j += 1
            if j == i + 2:
                out.append("x")
            else:
                out.append(chr(int(raw[i + 2 : j], 16)))
            i = j
            continue
        if nxt in "01234567":
            j = i + 1
            while j < n and j < i + 4 and raw[j] in "01234567":
                j += 1
            out.append(chr(int(raw[i + 1 : j], 8)))
            i = j
            continue
        out.append(_SIMPLE_UNESCAPES.get(nxt, nxt))
        i += 2
    return "".join(out)


def encode_bytearray(data: bytes) -> str:
    """bytes를 Qt INI의 `@ByteArray(...)` 값으로 만든다."""
    parts: list[str] = []
    escape_next_hex = False
    for byte in data:
        ch = chr(byte)
        if ch in _SIMPLE_ESCAPES:
            parts.append(_SIMPLE_ESCAPES[ch])
            escape_next_hex = False
        elif byte < 0x20 or byte >= 0x7F or (escape_next_hex and ch in _HEX_DIGITS):
            parts.append(f"\\x{byte:x}")
            escape_next_hex = True
        else:
            parts.append(ch)
            escape_next_hex = False
    text = "@ByteArray(" + "".join(parts) + ")"
    raw_text = data.decode("latin-1")
    return f'"{text}"' if _needs_quotes(raw_text) else text


def decode_bytearray(raw: str) -> bytes | None:
    """`@ByteArray(...)` 값을 bytes로 되돌린다. ByteArray가 아니면 None."""
    text = unescape_string(raw.strip())
    if not (text.startswith("@ByteArray(") and text.endswith(")")):
        return None
    inner = text[len("@ByteArray(") : -1]
    try:
        return inner.encode("latin-1")
    except UnicodeEncodeError:
        # Qt 규칙을 벗어난 값(예: UTF-8 원문이 그대로 들어간 경우)은 그대로 UTF-8로 본다.
        return inner.encode("utf-8", errors="surrogateescape")


def encode_path_bytearray(path: str) -> str:
    """Windows 경로 문자열을 MO2 gamePath 형식(@ByteArray, 백슬래시, UTF-8)으로 만든다."""
    return encode_bytearray(path.replace("/", "\\").encode("utf-8"))


def decode_path_bytearray(raw: str) -> str | None:
    """MO2 gamePath 같은 @ByteArray 경로 값을 문자열로 되돌린다."""
    data = decode_bytearray(raw)
    if data is None:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("latin-1")
