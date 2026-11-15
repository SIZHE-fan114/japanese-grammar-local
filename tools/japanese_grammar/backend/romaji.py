"""Offline Romaji <-> Kana normalization for Japanese grammar fill-blank answers."""

from __future__ import annotations

import re
import unicodedata
from typing import Iterable

_SPACE_SPLIT_RE = re.compile(r"[\s\u3000]+")
_ASCII_ALPHA_RE = re.compile(r"[a-zA-Z]")

_MACRON_BASE_MAP = {
    "ā": ("aa",),
    "ī": ("ii",),
    "ū": ("uu",),
    "ē": ("ee", "ei"),
    "ō": ("ou", "oo"),
}

_ROMAJI_MAP: dict[str, str] = {
    # 4-char special sequences
    "xtsu": "っ",
    "ltsu": "っ",
    # 3-char sequences (yoon + digraphs + small kana)
    "kya": "きゃ", "kyi": "きぃ", "kyu": "きゅ", "kye": "きぇ", "kyo": "きょ",
    "gya": "ぎゃ", "gyi": "ぎぃ", "gyu": "ぎゅ", "gye": "ぎぇ", "gyo": "ぎょ",
    "sha": "しゃ", "shi": "し", "shu": "しゅ", "she": "しぇ", "sho": "しょ",
    "sya": "しゃ", "syi": "しぃ", "syu": "しゅ", "sye": "しぇ", "syo": "しょ",
    "shya": "しゃ", "shyu": "しゅ", "shyo": "しょ",
    "ja": "じゃ", "jya": "じゃ", "jyi": "じぃ", "jyu": "じゅ", "jye": "じぇ", "jyo": "じょ",
    "zya": "じゃ", "zyi": "じぃ", "zyu": "じゅ", "zye": "じぇ", "zyo": "じょ",
    "cha": "ちゃ", "chi": "ち", "chu": "ちゅ", "che": "ちぇ", "cho": "ちょ",
    "tya": "ちゃ", "tyi": "ちぃ", "tyu": "ちゅ", "tye": "ちぇ", "tyo": "ちょ",
    "cya": "ちゃ", "cyi": "ちぃ", "cyu": "ちゅ", "cye": "ちぇ", "cyo": "ちょ",
    "tsu": "つ",
    "dya": "ぢゃ", "dyi": "ぢぃ", "dyu": "ぢゅ", "dye": "ぢぇ", "dyo": "ぢょ",
    "nya": "にゃ", "nyi": "にぃ", "nyu": "にゅ", "nye": "にぇ", "nyo": "にょ",
    "hya": "ひゃ", "hyi": "ひぃ", "hyu": "ひゅ", "hye": "ひぇ", "hyo": "ひょ",
    "bya": "びゃ", "byi": "びぃ", "byu": "びゅ", "bye": "びぇ", "byo": "びょ",
    "pya": "ぴゃ", "pyi": "ぴぃ", "pyu": "ぴゅ", "pye": "ぴぇ", "pyo": "ぴょ",
    "mya": "みゃ", "myi": "みぃ", "myu": "みゅ", "mye": "みぇ", "myo": "みょ",
    "rya": "りゃ", "ryi": "りぃ", "ryu": "りゅ", "rye": "りぇ", "ryo": "りょ",
    "xya": "ゃ", "xyu": "ゅ", "xyo": "ょ",
    "lya": "ゃ", "lyu": "ゅ", "lyo": "ょ",
    "xtu": "っ", "ltu": "っ",
    "xwa": "ゎ", "lwa": "ゎ",
    "dha": "でゃ", "dhi": "でぃ", "dhu": "でゅ", "dhe": "でぇ", "dho": "でょ",
    "tha": "てゃ", "thi": "てぃ", "thu": "てゅ", "the": "てぇ", "tho": "てょ",
    # 2-char sequences
    "ka": "か", "ki": "き", "ku": "く", "ke": "け", "ko": "こ",
    "ga": "が", "gi": "ぎ", "gu": "ぐ", "ge": "げ", "go": "ご",
    "sa": "さ", "si": "し", "su": "す", "se": "せ", "so": "そ",
    "za": "ざ", "ji": "じ", "zi": "じ", "zu": "ず", "ze": "ぜ", "zo": "ぞ",
    "ju": "じゅ", "je": "じぇ", "jo": "じょ",
    "ta": "た", "ti": "ち", "tu": "つ", "te": "て", "to": "と",
    "da": "だ", "di": "ぢ", "du": "づ", "de": "で", "do": "ど",
    "na": "な", "ni": "に", "nu": "ぬ", "ne": "ね", "no": "の",
    "ha": "は", "hi": "ひ", "hu": "ふ", "fu": "ふ", "he": "へ", "ho": "ほ",
    "fa": "ふぁ", "fi": "ふぃ", "fe": "ふぇ", "fo": "ふぉ",
    "ba": "ば", "bi": "び", "bu": "ぶ", "be": "べ", "bo": "ぼ",
    "pa": "ぱ", "pi": "ぴ", "pu": "ぷ", "pe": "ぺ", "po": "ぽ",
    "ma": "ま", "mi": "み", "mu": "む", "me": "め", "mo": "も",
    "ya": "や", "yu": "ゆ", "yo": "よ",
    "ra": "ら", "ri": "り", "ru": "る", "re": "れ", "ro": "ろ",
    "wa": "わ", "wi": "ゐ", "we": "ゑ", "wo": "を",
    "xa": "ぁ", "xi": "ぃ", "xu": "ぅ", "xe": "ぇ", "xo": "ぉ",
    "la": "ぁ", "li": "ぃ", "lu": "ぅ", "le": "ぇ", "lo": "ぉ",
    "va": "ゔぁ", "vi": "ゔぃ", "vu": "ゔ", "ve": "ゔぇ", "vo": "ゔぉ",
    "nn": "ん", "n'": "ん",
    # 1-char vowels & syllabic punctuation
    "a": "あ", "i": "い", "u": "う", "e": "え", "o": "お",
}

_SOKUON_CONSONANTS = frozenset("bcdfghjklmpqrstvwxz")
_VOWELS_OR_Y = frozenset("aiueoy")


def katakana_to_hiragana(text: str) -> str:
    """Convert standard katakana characters to hiragana for phonetic lookup."""
    out: list[str] = []
    for ch in text:
        code = ord(ch)
        if 0x30A1 <= code <= 0x30F6:
            out.append(chr(code - 0x60))
        elif ch == "ヵ":
            out.append("か")
        elif ch == "ヶ":
            out.append("け")
        elif ch == "ヴ":
            out.append("ゔ")
        else:
            out.append(ch)
    return "".join(out)


def _expand_macrons(text: str) -> list[str]:
    variants = [""]
    for ch in text:
        replacements = _MACRON_BASE_MAP.get(ch)
        if not replacements:
            variants = [prefix + ch for prefix in variants]
        else:
            expanded: list[str] = []
            for prefix in variants:
                for rep in replacements:
                    expanded.append(prefix + rep)
            variants = expanded[:8]
    return variants


def romaji_token_to_hiragana(token: str) -> str | None:
    """Convert one whitespace-free token containing optional romaji into hiragana.

    Returns None if any ASCII Latin letters remain unconverted.
    """
    nfkc = unicodedata.normalize("NFKC", token).lower()
    out: list[str] = []
    i = 0
    length = len(nfkc)
    while i < length:
        ch = nfkc[i]
        if ch in {"'", "’"}:
            i += 1
            continue
        if not ("a" <= ch <= "z"):
            out.append(ch)
            i += 1
            continue

        # Double-consonant gemination (kk/tt/ss/pp/...) and tch/cch -> っ
        if i + 2 < length and nfkc[i : i + 3] in {"tch", "cch"}:
            out.append("っ")
            i += 1
            continue
        if (
            i + 1 < length
            and ch in _SOKUON_CONSONANTS
            and nfkc[i + 1] == ch
        ):
            out.append("っ")
            i += 1
            continue

        # Syllabic 'n': nn, n', n at end of token, or n before consonant (not vowel/y)
        if ch == "n":
            nxt = nfkc[i + 1] if i + 1 < length else ""
            if nxt == "n":
                out.append("ん")
                i += 2
                continue
            if nxt in {"'", "’"}:
                out.append("ん")
                i += 2
                continue
            if not nxt or nxt == "-" or (
                not ("a" <= nxt <= "z")
            ) or (nxt not in _VOWELS_OR_Y):
                out.append("ん")
                i += 1
                continue

        matched = False
        for size in (4, 3, 2, 1):
            if i + size <= length:
                piece = nfkc[i : i + size]
                kana = _ROMAJI_MAP.get(piece)
                if kana is not None:
                    out.append(kana)
                    i += size
                    matched = True
                    break
        if not matched:
            return None

    result = "".join(out)
    if _ASCII_ALPHA_RE.search(result):
        return None
    return result


def romaji_to_hiragana_candidates(raw: str) -> list[str]:
    """Return converted hiragana string candidates for a user-submitted romaji answer."""
    nfkc = unicodedata.normalize("NFKC", str(raw or "")).strip().lower()
    if not nfkc:
        return []
    candidates: list[str] = []
    seen: set[str] = set()
    for expanded in _expand_macrons(nfkc):
        tokens = [tok for tok in _SPACE_SPLIT_RE.split(expanded) if tok]
        if not tokens:
            continue
        converted_parts: list[str] = []
        valid = True
        for tok in tokens:
            part = romaji_token_to_hiragana(tok)
            if part is None:
                valid = False
                break
            converted_parts.append(part)
        if valid:
            joined = "".join(converted_parts)
            if joined and joined not in seen:
                seen.add(joined)
                candidates.append(joined)
    return candidates


def _phonetic_hiragana_keys(expected: str) -> set[str]:
    """Generate acceptable phonetic hiragana keys for an expected Japanese answer."""
    normalized = katakana_to_hiragana(
        _SPACE_SPLIT_RE.sub("", unicodedata.normalize("NFKC", expected))
    )
    keys = {normalized}
    if normalized == "は":
        keys.add("わ")
    elif normalized == "を":
        keys.add("お")
    elif normalized == "へ":
        keys.add("え")
    if "では" in normalized and (
        normalized == "では"
        or "ではない" in normalized
        or "ではありません" in normalized
        or "ではなかった" in normalized
    ):
        keys.add(normalized.replace("では", "でわ"))
    return keys


def resolve_blank_answer_with_romaji(expected_answers: Iterable[str], submitted: str) -> str:
    """Resolve romaji or mixed romaji+Japanese input to a matching canonical answer.

    Returns the original `submitted` string untouched if it already matches directly,
    contains no ASCII Latin characters, or does not cleanly match any expected answer.
    """
    expected = [str(item) for item in expected_answers if isinstance(item, str) and item.strip()]
    if not expected or not isinstance(submitted, str) or not submitted.strip():
        return submitted

    submitted_nfkc = unicodedata.normalize("NFKC", submitted)
    submitted_compact = _SPACE_SPLIT_RE.sub("", submitted_nfkc)
    exact_norms = {
        _SPACE_SPLIT_RE.sub("", unicodedata.normalize("NFKC", item))
        for item in expected
    }
    if submitted_compact in exact_norms:
        return submitted

    submitted_hira = katakana_to_hiragana(submitted_compact)
    for exp in expected:
        exp_compact = _SPACE_SPLIT_RE.sub("", unicodedata.normalize("NFKC", exp))
        exp_hira = katakana_to_hiragana(exp_compact)
        # Allow hiragana input (e.g., from live romaji->hiragana conversion) when expected includes katakana
        if exp_hira != exp_compact and submitted_hira == exp_hira:
            return exp

    if not _ASCII_ALPHA_RE.search(submitted_nfkc):
        return submitted

    candidates = romaji_to_hiragana_candidates(submitted_nfkc)
    if not candidates:
        return submitted

    candidate_hira = {katakana_to_hiragana(cand) for cand in candidates}
    for exp in expected:
        exp_keys = _phonetic_hiragana_keys(exp)
        if candidate_hira & exp_keys:
            return exp
    return submitted
