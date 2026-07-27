"""Turkish-aware text normalisation for lexical retrieval.

Why this module exists
----------------------
Turkish is agglutinative: a single root takes a chain of suffixes, so the same
concept appears as many surface forms.

    embedding · embedding'ler · embedding'lerin · embeddinglerden
    vektör    · vektörler     · vektörlerin     · vektörlere

A keyword matcher that compares raw tokens treats every one of those as a
different word, so a query using one form misses a document using another.
Almost every RAG tutorial ignores this because almost every RAG tutorial is in
English, where the problem is mild.

Three things are handled here:

1. **Dotted/dotless I.** Turkish has four i's: ``i İ ı I``. Python's ``.lower()``
   maps ``I`` to ``i``, which is wrong for Turkish -- ``I`` lowercases to ``ı``
   and ``İ`` lowercases to ``i``. Getting this wrong silently breaks matching on
   any word containing an I.
2. **Apostrophe suffixes.** Turkish attaches suffixes to proper nouns and
   acronyms with an apostrophe: ``RAG'in``, ``SQLite'ta``. Splitting there
   recovers the root for free.
3. **Suffix stripping with vowel harmony.** Suffixes come in front/back vowel
   variants (``-ler`` vs ``-lar``). Checking harmony before stripping avoids
   mangling words that merely end in the same letters.

Deliberately *not* handled: consonant softening (``kitap`` -> ``kitabı``),
buffer consonants, and irregular forms. A full morphological analyser is a
project of its own. This is a retrieval aid, not a linguistics library -- it
only has to make two spellings of the same idea collide more often than not.
"""

from __future__ import annotations

import re
import unicodedata

VOWELS = "aeıioöuü"
FRONT_VOWELS = "eiöü"
BACK_VOWELS = "aıou"

#: never strip below this many characters -- prevents "veri" -> "ver" -> "ve"
MIN_STEM_LENGTH = 4

_TOKEN = re.compile(r"[0-9a-zçğıöşü]+", re.UNICODE)

# Turkish-specific case folding. str.lower() gets I/İ wrong.
_LOWER_MAP = str.maketrans({"I": "ı", "İ": "i", "Ş": "ş", "Ğ": "ğ", "Ü": "ü", "Ö": "ö", "Ç": "ç"})
_UPPER_I = str.maketrans({"ı": "i"})

# (suffix, harmony) where harmony is "front", "back" or "any".
# Ordered longest-first inside each group so the longest match wins.
_SUFFIXES: list[tuple[str, str]] = [
    # --- derivational ---
    ("liklerinden", "front"), ("lıklarından", "back"),
    ("sizlik", "front"), ("sızlık", "back"), ("suzluk", "back"), ("süzlük", "front"),
    ("lik", "front"), ("lık", "back"), ("luk", "back"), ("lük", "front"),
    ("siz", "front"), ("sız", "back"), ("suz", "back"), ("süz", "front"),
    ("ci", "front"), ("cı", "back"), ("cu", "back"), ("cü", "front"),
    ("çi", "front"), ("çı", "back"), ("çu", "back"), ("çü", "front"),
    # --- verbal ---
    ("mek", "front"), ("mak", "back"),
    ("iyor", "any"), ("ıyor", "any"), ("uyor", "any"), ("üyor", "any"),
    ("ecek", "front"), ("acak", "back"),
    ("miş", "front"), ("mış", "back"), ("muş", "back"), ("müş", "front"),
    ("dir", "front"), ("dır", "back"), ("dur", "back"), ("dür", "front"),
    ("tir", "front"), ("tır", "back"), ("tur", "back"), ("tür", "front"),
    # --- case ---
    ("lerden", "front"), ("lardan", "back"),
    ("lerin", "front"), ("ların", "back"),
    ("lere", "front"), ("lara", "back"),
    ("lerde", "front"), ("larda", "back"),
    ("leri", "front"), ("ları", "back"),
    ("den", "front"), ("dan", "back"), ("ten", "front"), ("tan", "back"),
    ("de", "front"), ("da", "back"), ("te", "front"), ("ta", "back"),
    ("nin", "front"), ("nın", "back"), ("nun", "back"), ("nün", "front"),
    ("in", "front"), ("ın", "back"), ("un", "back"), ("ün", "front"),
    ("ye", "front"), ("ya", "back"),
    ("yi", "front"), ("yı", "back"), ("yu", "back"), ("yü", "front"),
    ("le", "front"), ("la", "back"),
    # --- possessive / plural ---
    ("imiz", "front"), ("ımız", "back"), ("umuz", "back"), ("ümüz", "front"),
    ("iniz", "front"), ("ınız", "back"), ("unuz", "back"), ("ünüz", "front"),
    ("ler", "front"), ("lar", "back"),
    ("ma", "back"), ("me", "front"),
    ("im", "front"), ("ım", "back"), ("um", "back"), ("üm", "front"),
    ("i", "front"), ("ı", "back"), ("u", "back"), ("ü", "front"),
    ("e", "front"), ("a", "back"),
]

#: Turkish softens a final voiceless consonant when a vowel-initial suffix
#: attaches: kitap -> kitabı, benzerlik -> benzerliği. Reversing it after a
#: strip lets 'benzerliği' reach the same stem as 'benzerlik'.
_SOFTENED = {"ğ": "k", "b": "p", "c": "ç", "d": "t"}

# longest-first overall, so "lerinden" is tried before "den"
_SUFFIXES.sort(key=lambda pair: len(pair[0]), reverse=True)


def fold_case(text: str) -> str:
    """Lowercase correctly for Turkish (``I`` -> ``ı``, ``İ`` -> ``i``)."""
    return text.translate(_LOWER_MAP).lower()


def deaccent(text: str) -> str:
    """Fold Turkish diacritics so 'çalışma' and 'calisma' collide.

    Applied only in the *fallback* comparison path, never to the primary token
    stream -- 'sac' and 'saç' are different words and folding them always would
    lose real signal.
    """
    text = text.translate(_UPPER_I)
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def last_vowel(word: str) -> str | None:
    """Rightmost vowel, which determines which suffix variant may attach."""
    for char in reversed(word):
        if char in VOWELS:
            return char
    return None


def _harmony_of(word: str) -> str | None:
    vowel = last_vowel(word)
    if vowel is None:
        return None
    return "front" if vowel in FRONT_VOWELS else "back"


def strip_suffixes(word: str, min_stem: int = MIN_STEM_LENGTH) -> str:
    """Iteratively remove suffixes whose vowel harmony matches the stem.

    Two guards keep this from eating real word material:

    * **Single-character suffixes are only allowed on the first pass.** Without
      this, ``parçalar`` loses ``-lar`` to give ``parça`` and then loses the
      final ``-a`` too, landing on ``parç`` -- which no longer matches
      ``parçalama``. One bare vowel may be a case ending; two in a row is the
      stemmer running away.
    * **Consonant softening is reversed between passes.** ``benzerliği`` strips
      to ``benzerliğ``; restoring ``ğ`` -> ``k`` gives ``benzerlik``, which then
      strips ``-lik`` and meets ``benzer`` -- the same stem the unsuffixed form
      reaches.

    Bounded to four passes so a pathological word cannot loop.
    """
    stem = word
    for pass_index in range(4):
        harmony = _harmony_of(stem)
        for suffix, required in _SUFFIXES:
            if len(suffix) == 1 and pass_index > 0:
                continue
            if not stem.endswith(suffix):
                continue
            candidate = stem[: -len(suffix)]
            if len(candidate) < min_stem:
                continue
            # the suffix variant must agree with the stem's own harmony
            if required != "any" and harmony is not None and required != harmony:
                continue
            if last_vowel(candidate) is None:
                continue  # a stem with no vowel is not a Turkish word
            # undo consonant softening exposed by the strip
            if candidate[-1] in _SOFTENED:
                candidate = candidate[:-1] + _SOFTENED[candidate[-1]]
            stem = candidate
            break
        else:
            break
    return stem


def stem_word(word: str) -> str:
    """Normalise one token to a comparable stem."""
    # 'RAG'in' / 'SQLite'ta' -> the apostrophe already marks the root boundary
    # exactly, so take the root and stop. Stripping further would turn
    # 'SQLite'ta' into 'sqli' by treating the root's own '-te' as a suffix.
    if "'" in word or "’" in word:
        return fold_case(re.split(r"['’]", word)[0])
    word = fold_case(word)
    if len(word) <= MIN_STEM_LENGTH:
        return word
    return strip_suffixes(word)


def tokenize(text: str, stem: bool = True) -> list[str]:
    """Split text into normalised tokens, optionally stemmed."""
    folded = fold_case(text)
    # keep apostrophes attached so stem_word can use them as boundaries
    raw = re.findall(r"[0-9a-zçğıöşü]+(?:['’][0-9a-zçğıöşü]+)*", folded)
    if not stem:
        return raw
    return [stem_word(token) for token in raw]


def expand_tokens(text: str) -> list[str]:
    """Tokens expanded to **both** surface form and stem.

    This is the form the lexical index actually uses, and the reason the
    stemmer above does not need to be perfect.

    A rule-based Turkish stemmer cannot decide whether a final vowel is a case
    ending or part of the root: ``belge`` (root) and ``belgeler`` (inflected)
    reduce to ``belg`` and ``belge`` respectively, and never meet. Chasing that
    with more rules trades one class of error for another.

    Indexing both representations sidesteps the problem entirely -- two forms
    of a word match if *either* representation agrees::

        belge      -> {belge, belg}
        belgeler   -> {belgeler, belge}     shared: belge
        SQLite     -> {sqlite, sqli}
        SQLite'ta  -> {sqlite}              shared: sqlite
        benzerlik  -> {benzerlik, benzer}
        benzerliği -> {benzerliği, benzer}  shared: benzer

    The stem is a recall *enhancer*, not a source of truth. Duplicated tokens
    are kept rather than deduplicated so BM25 term frequencies stay meaningful.
    """
    tokens: list[str] = []
    for surface in tokenize(text, stem=False):
        tokens.append(surface)
        stem = stem_word(surface)
        if stem and stem != surface:
            tokens.append(stem)
    return tokens


def shares_root(a: str, b: str) -> bool:
    """True if two words plausibly share a root, via surface or stem."""
    return bool(set(expand_tokens(a)) & set(expand_tokens(b)))


def normalize(text: str) -> str:
    """Whole-string normalisation: stemmed tokens joined by single spaces."""
    return " ".join(tokenize(text))
