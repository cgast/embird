"""Language-specific stop word lists for cluster keyword extraction."""
from typing import Dict, Set

# Supported languages with display labels
SUPPORTED_LANGUAGES: Dict[str, str] = {
    "en": "English",
    "de": "German",
}

STOP_WORDS_EN: Set[str] = {
    'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from', 'has', 'he',
    'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the', 'to', 'was', 'were',
    'will', 'with', 'the', 'this', 'but', 'they', 'have', 'had', 'what', 'when',
    'where', 'who', 'which', 'why', 'how', 'all', 'each', 'every', 'both', 'few',
    'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own',
    'same', 'so', 'than', 'too', 'very', 'just', 'can', 'could', 'may', 'might',
    'must', 'shall', 'should', 'would', 'now', 'also', 'into', 'over', 'after',
    'before', 'between', 'under', 'again', 'further', 'then', 'once', 'here',
    'there', 'when', 'where', 'why', 'how', 'any', 'been', 'being', 'do', 'does',
    'did', 'doing', 'about', 'against', 'up', 'down', 'out', 'off', 'through',
    'during', 'while', 'above', 'below', 'their', 'them', 'these', 'those', 'his',
    'her', 'him', 'she', 'he', 'we', 'you', 'your', 'our', 'my', 'me', 'i', 'us',
    'says', 'said', 'new', 'news', 'report', 'reports', 'according', 'like',
    'get', 'gets', 'got', 'make', 'makes', 'made', 'one', 'two', 'three', 'first',
    'year', 'years', 'day', 'days', 'week', 'weeks', 'month', 'months', 'time',
    'way', 'even', 'well', 'back', 'much', 'still', 'many', 'last', 'take', 'see',
    'come', 'use', 'used', 'using', 'go', 'know', 'need', 'want', 'look', 'think',
    'right', 'old', 'going', 'good', 'great', 'big', 'long', 'little', 'own', 'set',
    'put', 'end', 'another', 'best', 'worst', 'top', 'high', 'low', 'part', 'full',
    'early', 'late', 'say', 'latest', 'breaking', 'live', 'update', 'updates'
}

STOP_WORDS_DE: Set[str] = {
    # Articles and pronouns
    'der', 'die', 'das', 'den', 'dem', 'des', 'ein', 'eine', 'einer', 'einem',
    'einen', 'eines', 'er', 'sie', 'es', 'wir', 'ihr', 'ich', 'du', 'mir',
    'mich', 'dir', 'dich', 'uns', 'euch', 'sich', 'man',
    # Possessives
    'mein', 'meine', 'meinem', 'meinen', 'meiner', 'meines',
    'dein', 'deine', 'deinem', 'deinen', 'deiner', 'deines',
    'sein', 'seine', 'seinem', 'seinen', 'seiner', 'seines',
    'ihr', 'ihre', 'ihrem', 'ihren', 'ihrer', 'ihres',
    'unser', 'unsere', 'unserem', 'unseren', 'unserer', 'unseres',
    'euer', 'eure', 'eurem', 'euren', 'eurer', 'eures',
    # Prepositions
    'in', 'an', 'auf', 'aus', 'bei', 'mit', 'nach', 'von', 'vor', 'zu',
    'um', 'bis', 'durch', 'gegen', 'ohne', 'unter', 'zwischen', 'hinter',
    'neben', 'seit', 'wegen', 'trotz', 'per', 'pro', 'laut',
    # Conjunctions
    'und', 'oder', 'aber', 'denn', 'weil', 'dass', 'wenn', 'als', 'ob',
    'sondern', 'doch', 'jedoch', 'obwohl', 'damit', 'bevor', 'nachdem',
    'sowie', 'weder', 'noch', 'sowohl', 'entweder',
    # Common verbs (conjugated forms)
    'ist', 'sind', 'war', 'waren', 'hat', 'haben', 'hatte', 'hatten',
    'wird', 'werden', 'wurde', 'wurden', 'kann', 'konnte', 'soll', 'sollte',
    'muss', 'musste', 'darf', 'durfte', 'mag', 'mochte', 'will', 'wollte',
    'sein', 'habe', 'bin', 'bist', 'seid', 'gewesen', 'geworden',
    'worden', 'gehabt', 'gekonnt', 'gemacht', 'gesagt', 'gibt',
    # Adverbs and particles
    'nicht', 'auch', 'nur', 'noch', 'schon', 'sehr', 'mehr', 'immer',
    'wieder', 'hier', 'dort', 'dann', 'jetzt', 'nun', 'so', 'wie',
    'was', 'wer', 'wo', 'wann', 'warum', 'weshalb', 'alle', 'alles',
    'viel', 'viele', 'wenig', 'wenige', 'einige', 'andere', 'anderen',
    'anderem', 'anderer', 'anderes', 'solche', 'solchem', 'solchen',
    'solcher', 'solches', 'jede', 'jedem', 'jeden', 'jeder', 'jedes',
    'diese', 'diesem', 'diesen', 'dieser', 'dieses', 'jene', 'jenem',
    'jenen', 'jener', 'jenes',
    # Other common words
    'zum', 'zur', 'vom', 'beim', 'ins', 'ans', 'ums', 'aufs',
    'kein', 'keine', 'keinem', 'keinen', 'keiner', 'keines',
    'dazu', 'dabei', 'damit', 'darin', 'daran', 'darum',
    'dort', 'eben', 'etwa', 'etwas', 'ganz', 'gar', 'genug',
    'mal', 'wohl', 'zwar', 'erst', 'rund', 'laut',
    # News-specific
    'sagt', 'sagte', 'neue', 'neuer', 'neues', 'neuem', 'neuen',
    'neu', 'laut', 'nach', 'ueber', 'heute', 'gestern', 'morgen',
    'jahr', 'jahre', 'jahren', 'tag', 'tage', 'tagen', 'woche',
    'wochen', 'monat', 'monate', 'monaten', 'zeit',
}

_STOP_WORDS_BY_LANGUAGE: Dict[str, Set[str]] = {
    "en": STOP_WORDS_EN,
    "de": STOP_WORDS_DE,
}

DEFAULT_LANGUAGE = "en"


def get_stop_words(language: str) -> Set[str]:
    """Get the stop word set for a given language code. Falls back to English."""
    return _STOP_WORDS_BY_LANGUAGE.get(language, STOP_WORDS_EN)
