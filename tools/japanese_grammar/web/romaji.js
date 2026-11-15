/**
 * Offline Romaji <-> Kana helper for Japanese Grammar fill-blank inputs.
 * Supports Hepburn & Kunrei-shiki variants, sokuon (double consonants),
 * syllabic 'n' handling with IME cursor preservation, and live preview hints.
 */

const MACRON_MAP = {
  'ā': 'aa',
  'ī': 'ii',
  'ū': 'uu',
  'ē': 'ee',
  'ō': 'ou',
};

const ROMAJI_TABLE = {
  xtsu: 'っ', ltsu: 'っ',
  kya: 'きゃ', kyi: 'きぃ', kyu: 'きゅ', kye: 'きぇ', kyo: 'きょ',
  gya: 'ぎゃ', gyi: 'ぎぃ', gyu: 'ぎゅ', gye: 'ぎぇ', gyo: 'ぎょ',
  sha: 'しゃ', shi: 'し', shu: 'しゅ', she: 'しぇ', sho: 'しょ',
  sya: 'しゃ', syi: 'しぃ', syu: 'しゅ', sye: 'しぇ', syo: 'しょ',
  shya: 'しゃ', shyu: 'しゅ', shyo: 'しょ',
  jya: 'じゃ', jyi: 'じぃ', jyu: 'じゅ', jye: 'じぇ', jyo: 'じょ',
  zya: 'じゃ', zyi: 'じぃ', zyu: 'じゅ', zye: 'じぇ', zyo: 'じょ',
  cha: 'ちゃ', chi: 'ち', chu: 'ちゅ', che: 'ちぇ', cho: 'ちょ',
  tya: 'ちゃ', tyi: 'ちぃ', tyu: 'ちゅ', tye: 'ちぇ', tyo: 'ちょ',
  cya: 'ちゃ', cyi: 'ちぃ', cyu: 'ちゅ', cye: 'ちぇ', cyo: 'ちょ',
  tsu: 'つ',
  dya: 'ぢゃ', dyi: 'ぢぃ', dyu: 'ぢゅ', dye: 'ぢぇ', dyo: 'ぢょ',
  nya: 'にゃ', nyi: 'にぃ', nyu: 'にゅ', nye: 'にぇ', nyo: 'にょ',
  hya: 'ひゃ', hyi: 'ひぃ', hyu: 'ひゅ', hye: 'ひぇ', hyo: 'ひょ',
  bya: 'びゃ', byi: 'びぃ', byu: 'びゅ', bye: 'びぇ', byo: 'びょ',
  pya: 'ぴゃ', pyi: 'ぴぃ', pyu: 'ぴゅ', pye: 'ぴぇ', pyo: 'ぴょ',
  mya: 'みゃ', myi: 'みぃ', myu: 'みゅ', mye: 'みぇ', myo: 'みょ',
  rya: 'りゃ', ryi: 'りぃ', ryu: 'りゅ', rye: 'りぇ', ryo: 'りょ',
  xya: 'ゃ', xyu: 'ゅ', xyo: 'ょ',
  lya: 'ゃ', lyu: 'ゅ', lyo: 'ょ',
  xtu: 'っ', ltu: 'っ',
  xwa: 'ゎ', lwa: 'ゎ',
  dha: 'でゃ', dhi: 'でぃ', dhu: 'でゅ', dhe: 'でぇ', dho: 'でょ',
  tha: 'てゃ', thi: 'てぃ', thu: 'てゅ', the: 'てぇ', tho: 'てょ',
  ka: 'か', ki: 'き', ku: 'く', ke: 'け', ko: 'こ',
  ga: 'が', gi: 'ぎ', gu: 'ぐ', ge: 'げ', go: 'ご',
  sa: 'さ', si: 'し', su: 'す', se: 'せ', so: 'そ',
  za: 'ざ', ji: 'じ', zi: 'じ', zu: 'ず', ze: 'ぜ', zo: 'ぞ',
  ja: 'じゃ', ju: 'じゅ', je: 'じぇ', jo: 'じょ',
  ta: 'た', ti: 'ち', tu: 'つ', te: 'て', to: 'と',
  da: 'だ', di: 'ぢ', du: 'づ', de: 'で', do: 'ど',
  na: 'な', ni: 'に', nu: 'ぬ', ne: 'ね', no: 'の',
  ha: 'は', hi: 'ひ', hu: 'ふ', fu: 'ふ', he: 'へ', ho: 'ほ',
  fa: 'ふぁ', fi: 'ふぃ', fe: 'ふぇ', fo: 'ふぉ',
  ba: 'ば', bi: 'び', bu: 'ぶ', be: 'べ', bo: 'ぼ',
  pa: 'ぱ', pi: 'ぴ', pu: 'ぷ', pe: 'ぺ', po: 'ぽ',
  ma: 'ま', mi: 'み', mu: 'む', me: 'め', mo: 'も',
  ya: 'や', yu: 'ゆ', yo: 'よ',
  ra: 'ら', ri: 'り', ru: 'る', re: 'れ', ro: 'ろ',
  wa: 'わ', wi: 'ゐ', we: 'ゑ', wo: 'を',
  xa: 'ぁ', xi: 'ぃ', xu: 'ぅ', xe: 'ぇ', xo: 'ぉ',
  la: 'ぁ', li: 'ぃ', lu: 'ぅ', le: 'ぇ', lo: 'ぉ',
  va: 'ゔぁ', vi: 'ゔぃ', vu: 'ゔ', ve: 'ゔぇ', vo: 'ゔぉ',
  nn: 'ん', "n'": 'ん',
  a: 'あ', i: 'い', u: 'う', e: 'え', o: 'お',
};

const ROMAJI_PREFIXES = new Set();
for (const key of Object.keys(ROMAJI_TABLE)) {
  for (let len = 1; len < key.length; len += 1) {
    ROMAJI_PREFIXES.add(key.slice(0, len));
  }
}
ROMAJI_PREFIXES.add('n');
ROMAJI_PREFIXES.add('tc');
ROMAJI_PREFIXES.add('cc');

const SOKUON_CONSONANTS = new Set('bcdfghjklmpqrstvwxz'.split(''));
const VOWELS_OR_Y = new Set('aiueoy'.split(''));

export function containsLatinLetters(text) {
  const nfkc = String(text || '').normalize('NFKC');
  return /[a-zA-Z]/.test(nfkc);
}

function expandMacrons(text) {
  let out = '';
  for (const ch of String(text || '')) {
    out += MACRON_MAP[ch] || ch;
  }
  return out;
}

/**
 * Convert a string containing optional ASCII romaji to hiragana.
 * When `flushTerminalN` is false (live typing mode), incomplete trailing syllables
 * and trailing `'n'` are kept intact so the learner can continue typing.
 */
export function convertRomajiToHiragana(raw, { flushTerminalN = false } = {}) {
  const normalized = expandMacrons(String(raw || '').normalize('NFKC'));
  let out = '';
  let i = 0;
  const len = normalized.length;

  while (i < len) {
    const chRaw = normalized[i];
    const ch = chRaw.toLowerCase();

    if (ch < 'a' || ch > 'z') {
      out += chRaw;
      i += 1;
      continue;
    }

    const rem = normalized.slice(i).toLowerCase();

    // Pending tail during live typing: keep buffer untouched until next char
    if (!flushTerminalN) {
      if (rem === 'n') {
        out += normalized.slice(i);
        break;
      }
      if (rem.length < 4 && (ROMAJI_PREFIXES.has(rem) || (rem.length === 1 && SOKUON_CONSONANTS.has(rem)))) {
        // Note: if rem is a full 1-char vowel ('a','i','u','e','o') or 2-char kana, let table match below!
        if (!ROMAJI_TABLE[rem]) {
          out += normalized.slice(i);
          break;
        }
      }
    }

    // Gemination: tch / cch or double consonant (except n / y)
    if (rem.startsWith('tch') || rem.startsWith('cch')) {
      out += 'っ';
      i += 1;
      continue;
    }
    if (i + 1 < len && SOKUON_CONSONANTS.has(ch) && normalized[i + 1].toLowerCase() === ch) {
      out += 'っ';
      i += 1;
      continue;
    }

    // Syllabic n
    if (ch === 'n') {
      const next = i + 1 < len ? normalized[i + 1].toLowerCase() : '';
      if (next === 'n') {
        out += 'ん';
        i += 2;
        continue;
      }
      if (next === "'" || next === '’') {
        out += 'ん';
        i += 2;
        continue;
      }
      if (!next) {
        out += flushTerminalN ? 'ん' : chRaw;
        i += 1;
        continue;
      }
      const nextIsAsciiLetter = next >= 'a' && next <= 'z';
      if (!nextIsAsciiLetter || !VOWELS_OR_Y.has(next)) {
        out += 'ん';
        i += 1;
        continue;
      }
    }

    let matched = false;
    for (const size of [4, 3, 2, 1]) {
      if (i + size <= len) {
        const piece = normalized.slice(i, i + size).toLowerCase();
        if (Object.prototype.hasOwnProperty.call(ROMAJI_TABLE, piece)) {
          out += ROMAJI_TABLE[piece];
          i += size;
          matched = true;
          break;
        }
      }
    }

    if (!matched) {
      out += chRaw;
      i += 1;
    }
  }

  return out;
}

/**
 * Compute live kana preview + particle equivalence hints for one blank's value.
 */
export function inspectRomajiPreview(raw, { includeKanaParticleHints = false } = {}) {
  const text = String(raw || '');
  const trimmed = text.normalize('NFKC').trim();
  if (!trimmed) {
    return null;
  }
  if (!containsLatinLetters(text)) {
    if (!includeKanaParticleHints) {
      return null;
    }
    const compactKana = trimmed.replace(/[\s\u3000]+/g, '');
    const alts = [];
    if (compactKana === 'わ') {
      alts.push({ kana: 'は', label: '助词「は」' });
    } else if (compactKana === 'お') {
      alts.push({ kana: 'を', label: '宾格「を」' });
    } else if (compactKana === 'え') {
      alts.push({ kana: 'へ', label: '方向「へ」' });
    } else if (compactKana.includes('でわ')) {
      alts.push({ kana: compactKana.replace(/でわ/g, 'では'), label: '「では」' });
    }
    if (!alts.length) {
      return null;
    }
    return {
      raw: trimmed,
      kana: '',
      partialKana: '',
      particleAlternatives: alts,
    };
  }
  const tokens = trimmed
    .split(/[\s\u3000]+/)
    .filter(Boolean);
  if (!tokens.length) {
    return null;
  }

  const converted = tokens.map((tok) => convertRomajiToHiragana(tok, { flushTerminalN: true })).join('');
  const stillHasLatin = containsLatinLetters(converted);
  const compactRomaji = tokens.join('').toLowerCase();

  const particleAlternatives = [];
  if (compactRomaji === 'wa') {
    particleAlternatives.push({ kana: 'は', label: '助词「は」' });
  } else if (compactRomaji === 'o') {
    particleAlternatives.push({ kana: 'を', label: '宾格「を」' });
  } else if (compactRomaji === 'e') {
    particleAlternatives.push({ kana: 'へ', label: '方向「へ」' });
  } else if (compactRomaji.includes('dewa') && !stillHasLatin) {
    particleAlternatives.push({ kana: converted.replace(/でわ/g, 'では'), label: '「では」' });
  }

  return {
    raw: text.trim(),
    kana: stillHasLatin ? '' : converted,
    partialKana: stillHasLatin ? converted : '',
    particleAlternatives,
  };
}
