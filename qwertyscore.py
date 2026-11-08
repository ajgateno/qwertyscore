#!/opt/homebrew/bin/python3

"""qwertyscore: score how easy a word is to type on QWERTY, in "beats".

Assumes strict touch-typing technique. Each letter maps to a (hand, finger)
pair. The index fingers each cover two columns (home and reaching), but they
are still one finger, so moving between those columns is a same-finger move.

Rules (cost of a whole sequence):
    1. a single key                         -> 1 beat
    2. the same key twice in a row          -> 3 beats (strike-lift-strike)
    3. two different keys, same finger      -> 4 beats (strike-lift-shift-strike)
    4. a roll (same hand, different fingers,
       all moving left or all moving right) -> 1 beat
    5. n rolls                              -> n beats
    6. n keys alternating hands             -> n beats

Read as costs per transition between consecutive letters:
    first letter                            +1
    switch hands                            +1  (starts a new group)
    same hand, roll continues               +0
    same hand, roll changes direction       +1  (starts a new roll)
    same key again                          +2  (3 total for the pair)
    same finger, different key              +3  (4 total for the pair)
After a repeated key or a same-finger move, the newly struck key starts a
new roll, so a following key on the same hand can roll off it for free.
"""

LEFT, RIGHT = "L", "R"

# Finger columns from left to right across the keyboard. Same number means
# same finger; the order gives the direction of a roll.
_FINGERS = {
    "L_pinky": (LEFT, 0),
    "L_ring": (LEFT, 1),
    "L_middle": (LEFT, 2),
    "L_index": (LEFT, 3),
    "R_index": (RIGHT, 4),
    "R_middle": (RIGHT, 5),
    "R_ring": (RIGHT, 6),
    "R_pinky": (RIGHT, 7),
}

_KEYS_BY_FINGER = {
    "L_pinky": "qaz",
    "L_ring": "wsx",
    "L_middle": "edc",
    "L_index": "rfvtgb",  # home column rfv + reaching column tgb
    "R_index": "yhnujm",  # reaching column yhn + home column ujm
    "R_middle": "ik",
    "R_ring": "ol",
    "R_pinky": "p",
}

# letter -> (hand, finger column)
KEYMAP = {
    letter: _FINGERS[finger]
    for finger, letters in _KEYS_BY_FINGER.items()
    for letter in letters
}


def qwertyscore(word: str) -> int:
    """Return the number of beats needed to type ``word``.

    >>> qwertyscore("a")
    1
    >>> qwertyscore("asdf")        # one rightward roll
    1
    >>> qwertyscore("sad")         # roll s->a, then direction change to d
    2
    >>> qwertyscore("ll")          # repeated key
    3
    >>> qwertyscore("ft")          # same finger, different key
    4
    >>> qwertyscore("hand")        # h|a|n|d alternating hands
    4
    """
    letters = word.lower()
    for ch in letters:
        if ch not in KEYMAP:
            raise ValueError(f"unsupported character {ch!r} in {word!r}")
    if not letters:
        return 0

    beats = 1
    direction = 0  # 0 = no direction yet, +1 = moving right, -1 = moving left
    prev = letters[0]

    for ch in letters[1:]:
        prev_hand, prev_col = KEYMAP[prev]
        hand, col = KEYMAP[ch]

        if hand != prev_hand:
            beats += 1
            direction = 0
        elif ch == prev:
            beats += 2
            direction = 0
        elif col == prev_col:
            beats += 3
            direction = 0
        else:
            step = 1 if col > prev_col else -1
            if direction in (0, step):
                direction = step  # roll starts or continues: free
            else:
                beats += 1  # direction change: a new roll
                direction = step
        prev = ch

    return beats


if __name__ == "__main__":
    import sys

    for w in sys.argv[1:]:
        print(f"{w}\t{qwertyscore(w)}")
