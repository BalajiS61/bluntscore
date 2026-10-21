"""Domain words VADER's general-purpose lexicon misses or under-weights.

Scale matches VADER: -4 (extremely negative) .. +4 (extremely positive).
"""
REVIEW_LEXICON: dict[str, float] = {
    # negative product/service terms
    "overpriced": -2.0,
    "laggy": -1.8,
    "buggy": -2.0,
    "glitchy": -1.8,
    "overheats": -1.9,
    "overheating": -1.9,
    "defective": -2.3,
    "flimsy": -1.6,
    "unresponsive": -1.8,
    "refund": -1.2,
    "returned": -1.0,
    "crashes": -2.0,
    "crashing": -2.0,
    "rip-off": -2.5,
    "ripoff": -2.5,
    # positive product/service terms
    "durable": 1.8,
    "sturdy": 1.5,
    "snappy": 1.6,
    "seamless": 1.8,
    "reliable": 1.9,
    "worth": 1.2,
    "affordable": 1.4,
    "intuitive": 1.7,
    "responsive": 1.4,
}
