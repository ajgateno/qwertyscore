"""Build the comparison datasets as CSVs under ./data (only those missing).

Sources (fetched on first run, cached in data/raw/):
  - Vocabulary and frequency order: google-10000-english (no-swears list),
    https://github.com/first20hours/google-10000-english, filtered to real
    words with SCOWL (http://wordlist.aspell.net/)
  - word-cost: https://github.com/stutrek/word-cost  (JS, run via scorers.js)
  - carpalx.js: https://github.com/dmtrs/carpalx.js (JS, run via scorers.js)
  - TypeRacer1000: Chen, Levy & Eisape (CogSci 2021), https://osf.io/d3z8v/
    Median measured typing time per word, in ms.

Output CSVs (each has one row per word, with every score and its percentile):
  data/scores.csv                     whole vocabulary
  data/common_100.csv                 dataset 1: the 100 most common words
  data/lowest_qwertyscore_100.csv     dataset 2: the 100 lowest qwertyscores
  data/lowest_<scorer>_100.csv        dataset 3: the 100 lowest per other scorer

Percentiles put the scorers on one scale: each word's score ranked within the
vocabulary, 0 = easiest word, 100 = hardest (ties share their average rank).
"""

import csv
import io
import statistics
import subprocess
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from qwertyscore import qwertyscore

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
RAW = DATA / "raw"

# Pinned to exact commits so results are reproducible.
_GH = "https://raw.githubusercontent.com"
SOURCES = {
    "words.txt": f"{_GH}/first20hours/google-10000-english/"
    "d0736d492489198e4f9d650c7ab4143bc14c1e9e/google-10000-english-no-swears.txt",
    "word-cost/index.js": f"{_GH}/stutrek/word-cost/"
    "fb2f9ea07e91bb110b53526018f556b5d48c8f90/index.js",
    "carpalx/utils.js": f"{_GH}/dmtrs/carpalx.js/"
    "05b1f6fdb503a3beb6de8494b611076c3a967414/src/utils.js",
    "carpalx/layout.js": f"{_GH}/dmtrs/carpalx.js/"
    "05b1f6fdb503a3beb6de8494b611076c3a967414/src/layout.js",
    # SCOWL is served by a generator, so this one cannot be pinned to a commit.
    "scowl.txt": "http://app.aspell.net/create?max_size=60&spelling=US"
    "&max_variant=0&diacritic=strip&download=wordlist&encoding=utf-8&format=inline",
}
SHORT_WORDS = set(
    "a i ah am an as at aw be by do eh go ha he hi if in is it lo ma me my no "
    "of oh ok on or ow ox pa so to uh um up us we ya ye yo".split()
)
TYPERACER_ZIP_URL = "https://osf.io/download/jz8pt/"  # TypeRacer1000_filtered.zip
TYPERACER_MIN_OBS = 20  # fewer timings than this and a word's median is too noisy

# Scorer key -> column holding its score. Lower always means easier.
SCORERS = {
    "qwertyscore": "qwertyscore",
    "word_cost": "word_cost",
    "carpalx": "carpalx",
    "typeracer": "typeracer_ms",
}
COLUMNS = (
    ["frequency_rank", "word"]
    + list(SCORERS.values())
    + ["typeracer_n"]
    + [f"{k}_pct" for k in SCORERS]
)
N = 100


def _fetch(name: str) -> Path:
    dest = RAW / name
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        print(f"fetching {SOURCES[name]}")
        urllib.request.urlretrieve(SOURCES[name], dest)
    return dest


def load_vocabulary() -> list[str]:
    """Frequency-ordered real English words.

    google-10000-english is web-derived and full of abbreviations (pm, uk, tx,
    pdf), so a word is kept only if it is a lowercase entry in the SCOWL
    size-60 US spelling list. Words of 1-2 letters must also be in
    SHORT_WORDS, because SCOWL still lists abbreviations like "pm" and "km".
    """
    text = _fetch("scowl.txt").read_text(encoding="utf-8")
    dictionary = set(text.split("\n---\n", 1)[-1].split())  # skip license header
    words = []
    for line in _fetch("words.txt").read_text().splitlines():
        w = line.strip()
        if len(w) <= 2:
            if w in SHORT_WORDS:
                words.append(w)
        elif w in dictionary:
            words.append(w)
    return list(dict.fromkeys(words))


def js_scores(words: list[str]) -> dict[str, tuple[str, str]]:
    """word -> (word_cost, carpalx) from the original JS tools via node."""
    word_cost = _fetch("word-cost/index.js")
    _fetch("carpalx/utils.js")
    carpalx_dir = _fetch("carpalx/layout.js").parent
    result = subprocess.run(
        ["node", str(ROOT / "scorers.js"), str(word_cost), str(carpalx_dir)],
        input="\n".join(words), capture_output=True, text=True, check=True,
    )
    rows = csv.DictReader(io.StringIO(result.stdout))
    return {r["word"]: (r["word_cost"], r["carpalx"]) for r in rows}


def typeracer_times() -> dict[str, tuple[float, int]]:
    """word -> (median ms, number of timings) from TypeRacer1000.

    Keeps lowercase alphabetic words only (no Shift key involved) and skips
    each race's first word, whose time includes the reaction to the race start.
    The 171 MB zip is streamed from a temp file, then only the per-word
    summary is cached in data/raw/typeracer_word_times.csv.
    """
    cache = RAW / "typeracer_word_times.csv"
    if not cache.exists():
        RAW.mkdir(parents=True, exist_ok=True)
        times: dict[str, list[int]] = {}
        with tempfile.NamedTemporaryFile(suffix=".zip") as tmp:
            print(f"fetching {TYPERACER_ZIP_URL} (171 MB)")
            urllib.request.urlretrieve(TYPERACER_ZIP_URL, tmp.name)
            csv.field_size_limit(1 << 24)
            with zipfile.ZipFile(tmp.name) as zf, zf.open(
                "TypeRacer1000_filtered.csv"
            ) as f:
                for r in csv.DictReader(io.TextIOWrapper(f, encoding="utf-8")):
                    w = r["Word"]
                    if (r["is_word"] == "1" and r["Word_in_text"] != "1"
                            and w.isascii() and w.isalpha() and w.islower()):
                        times.setdefault(w, []).append(int(r["Time"]))
        with cache.open("w", newline="") as f:
            out = csv.writer(f)
            out.writerow(["word", "median_ms", "n"])
            for w, ts in sorted(times.items()):
                out.writerow([w, statistics.median(ts), len(ts)])
    with cache.open() as f:
        return {r["word"]: (float(r["median_ms"]), int(r["n"]))
                for r in csv.DictReader(f)}


def _percentiles(rows: list[dict], col: str, key: str) -> None:
    """Add <key>_pct to each row: 0 = lowest score, 100 = highest; ties averaged."""
    scored = sorted((r for r in rows if r[col] != ""), key=lambda r: r[col])
    n = len(scored)
    i = 0
    while i < n:
        j = i
        while j + 1 < n and scored[j + 1][col] == scored[i][col]:
            j += 1
        pct = round(100 * ((i + j) / 2) / (n - 1), 2)
        for r in scored[i : j + 1]:
            r[f"{key}_pct"] = pct
        i = j + 1
    for r in rows:
        r.setdefault(f"{key}_pct", "")


def build_scores() -> list[dict]:
    words = load_vocabulary()
    js = js_scores(words)
    tr = typeracer_times()
    rows = []
    for rank, w in enumerate(words, 1):
        wc, cx = js[w]
        ms, n = tr.get(w, ("", 0))
        rows.append({
            "frequency_rank": rank,
            "word": w,
            "qwertyscore": qwertyscore(w),
            "word_cost": int(wc),
            "carpalx": float(cx) if cx else "",
            "typeracer_ms": ms if n >= TYPERACER_MIN_OBS else "",
            "typeracer_n": n,
        })
    for key, col in SCORERS.items():
        _percentiles(rows, col, key)
    return rows


def _write(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {path.relative_to(ROOT)}")


def _read(path: Path) -> list[dict]:
    with path.open() as f:
        return list(csv.DictReader(f))


def lowest(rows: list[dict], col: str, n: int = N) -> list[dict]:
    """The n lowest-scoring words for one column; ties go to the more common word."""
    scored = [r for r in rows if r[col] != ""]
    return sorted(scored, key=lambda r: (float(r[col]), int(r["frequency_rank"])))[:n]


def dataset_paths() -> dict[str, Path]:
    paths = {"common": DATA / "common_100.csv"}
    for key in SCORERS:
        paths[key] = DATA / f"lowest_{key}_100.csv"
    return paths


def ensure_datasets() -> dict[str, Path]:
    """Create any missing dataset CSV and return name -> path for all of them."""
    DATA.mkdir(exist_ok=True)
    paths = dataset_paths()
    scores_path = DATA / "scores.csv"
    if all(p.exists() for p in paths.values()) and scores_path.exists():
        return paths

    if scores_path.exists():
        rows = _read(scores_path)
    else:
        rows = build_scores()
        _write(scores_path, rows)
        rows = _read(scores_path)  # same str form as when loaded from disk

    if not paths["common"].exists():
        _write(paths["common"], rows[:N])
    for key, col in SCORERS.items():
        if not paths[key].exists():
            _write(paths[key], lowest(rows, col))
    return paths


if __name__ == "__main__":
    ensure_datasets()
