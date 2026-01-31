NEGATIVE_RAW = [
    "nepřijdu", "nemůžu", "nemohu", "nehraju", "nezvládnu",
    "bohužel", "tentokrát ne", "nejdu", "nepůjdu",
    "nemám čas", "nemám možnost","omluvte"
]

CONDITIONAL_RAW = [
    "když", "pokud", "jestli", "jen když", "pouze pokud",
    "možná", "uvidím", "zatím nevím", "dám vědět",
    "podle", "záleží"
]
REINFORCES_RAW=["Nechci"]

POSITIVE_RAW = [
    "dorazím", "přijdu", "půjdu", "hraju", "nastoupím",
    "napiš mě", "zapiš mě", "počítej se mnou",
    "berte mě", "mohu", "můžu", "jo", "ano", "jj", "můžete"
]

import re
import unicodedata

def normalize(text):
    text = text.lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text
NEGATIVE = [normalize(w) for w in NEGATIVE_RAW]
CONDITIONAL = [normalize(w) for w in CONDITIONAL_RAW]
POSITIVE = [normalize(w) for w in POSITIVE_RAW]
REINFORCES = [normalize(w) for w in REINFORCES_RAW]

def classify(text):
    t = normalize(text)

    if any(w in t for w in NEGATIVE):
        return "NE"
    if any(w in t for w in POSITIVE):
        return "ANO"
    if any(w in t for w in REINFORCES):
        return "NECHCI"

    return "NEJASNÉ"


