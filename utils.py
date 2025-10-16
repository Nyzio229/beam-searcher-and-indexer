from __future__ import annotations

import apache_beam as beam

import os
import re
import math
import json
import hashlib
import sqlite3
from typing import Dict, Iterable, List, Tuple
from collections import Counter

# --- NLTK stopwords & lemmatizer (EN only) ---
import nltk
from nltk.corpus import stopwords
from nltk.data import find as nltk_find

# Ensure required corpora are present (quietly)
try:
    nltk_find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords', quiet=True)

try:
    nltk_find('corpora/wordnet')
    from nltk.stem import WordNetLemmatizer
    _HAS_WORDNET = True
except LookupError:
    nltk.download('wordnet', quiet=True)
    try:
        nltk_find('corpora/wordnet')
        from nltk.stem import WordNetLemmatizer
        _HAS_WORDNET = True
    except LookupError:
        _HAS_WORDNET = False

# --- Tokenization (EN-only alphanum) ---
TOKEN_RE = re.compile(r"[A-Za-z0-9_]+", re.UNICODE)

def tokenize(text: str) -> List[str]:
    """Return lowercase alphanumeric tokens."""
    if not text:
        return []
    return [t.lower() for t in TOKEN_RE.findall(text)]

# English stopwords only
_EN_STOPWORDS = set(stopwords.words('english'))

def normalize_tokens(tokens: Iterable[str],
                     min_len: int = 2,
                     lemmatize: bool = True) -> List[str]:
    """
    Filter by English stopwords & length; optional WordNet lemmatization.
    """
    toks = [t for t in tokens if len(t) >= min_len and t not in _EN_STOPWORDS]
    if lemmatize and _HAS_WORDNET:
        lemm = WordNetLemmatizer()
        toks = [lemm.lemmatize(t) for t in toks]
    return toks

# --- Vector math ---
def tf_from_tokens(tokens: Iterable[str]) -> Dict[str, int]:
    return dict(Counter(tokens))

def idf_from_df(df: Dict[str, int], N: int) -> Dict[str, float]:
    """Smoothed IDF: log((N+1)/(df+1)) + 1"""
    return {term: math.log((N + 1) / (df_val + 1)) + 1.0 for term, df_val in df.items()}

def tfidf_from_tf(tf: Dict[str, int], idf: Dict[str, float]) -> Dict[str, float]:
    vec = {t: float(f) * idf.get(t, 0.0) for t, f in tf.items() if idf.get(t, 0.0) > 0.0}
    norm = math.sqrt(sum(v*v for v in vec.values())) or 1.0
    return {k: v / norm for k, v in vec.items()}

def cosine_sparse(a: Dict[str, float], b: Dict[str, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(a.get(k, 0.0) * b.get(k, 0.0) for k in a.keys())

# --- Stable document ID ---
def stable_doc_id(path: str) -> str:
    abspath = os.path.abspath(path)
    return hashlib.sha1(abspath.encode('utf-8')).hexdigest()

# --- Beam transforms ---
class ReadFiles(beam.PTransform):
    """Read files matching a glob; emit (path, text)."""
    def __init__(self, file_glob: str):
        super().__init__()
        self.file_glob = file_glob
    def expand(self, pcoll):
        return (
            pcoll
            | "MatchFiles" >> beam.io.fileio.MatchFiles(self.file_glob)
            | "ReadMatches" >> beam.io.fileio.ReadMatches()
            | "ToPathText" >> beam.Map(lambda m: (m.metadata.path, m.read_utf8()))
        )

class ToDocTF(beam.DoFn):
    """(path,text) -> (doc_id, {'path','tf','unique_terms'}) in ENGLISH ONLY."""
    def __init__(self, min_len: int = 2, lemmatize: bool = True):
        self.min_len = min_len
        self.lemmatize = lemmatize
    def process(self, path_text: Tuple[str, str]):
        path, text = path_text
        doc_id = stable_doc_id(path)
        tokens = normalize_tokens(tokenize(text), min_len=self.min_len, lemmatize=self.lemmatize)
        tf = tf_from_tokens(tokens)
        yield (doc_id, {"path": path, "tf": tf, "unique_terms": list(tf.keys())})

# --- SQLite helpers ---
def write_sqlite_rows(db_path: str, rows):
    """Write ('doc'|'vocab'|'meta', payload) rows to SQLite."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS documents (
        doc_id TEXT PRIMARY KEY,
        path   TEXT NOT NULL,
        vector_json TEXT NOT NULL
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS vocab (
        term TEXT PRIMARY KEY,
        df   INTEGER NOT NULL,
        idf  REAL NOT NULL
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS meta (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )""")
    conn.commit()
    for kind, payload in rows:
        if kind == 'doc':
            doc_id, path, vec = payload
            cur.execute("INSERT OR REPLACE INTO documents(doc_id, path, vector_json) VALUES(?,?,?)",
                        (doc_id, path, json.dumps(vec, ensure_ascii=False)))
        elif kind == 'vocab':
            term, df_val, idf_val = payload
            cur.execute("INSERT OR REPLACE INTO vocab(term, df, idf) VALUES(?,?,?)",
                        (term, int(df_val), float(idf_val)))
        elif kind == 'meta':
            key, value = payload
            cur.execute("INSERT OR REPLACE INTO meta(key, value) VALUES(?,?)",
                        (key, str(value)))
    conn.commit()
    conn.close()

def load_index(db_path: str):
    """Load N, vocab idf dict, and document vectors from SQLite."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT value FROM meta WHERE key='N'")
    row = cur.fetchone()
    N = int(row[0]) if row else 0
    vocab_idf: Dict[str, float] = {}
    for term, idf_val in cur.execute("SELECT term, idf FROM vocab"):
        vocab_idf[term] = float(idf_val)
    documents = []
    for doc_id, path, vector_json in cur.execute("SELECT doc_id, path, vector_json FROM documents"):
        documents.append((doc_id, path, json.loads(vector_json)))
    conn.close()
    return N, vocab_idf, documents