# beam-searcher-and-indexer

Narzędzie edukacyjne do indeksowania dokumentów (TF‑IDF) i prostego wyszukiwania (cosine + Top‑K). Projekt używa Apache Beam do przetwarzania i SQLite do przechowywania indeksu.

Ważne: przetwarzanie tekstu jest ENGLISH ONLY (tokenizacja, stopwords, lematyzacja WordNet).

## Co robi projekt
- Buduje indeks TF‑IDF z kolekcji plików tekstowych i zapisuje go do pliku SQLite.
- Pozwala wyszukiwać zapytania przy użyciu wektora TF‑IDF i kosinusowej miary podobieństwa.
- Pipeline oparty na Apache Beam (domyślnie DirectRunner).

## Główne pliki
- `indexer.py` — buduje indeks i zapisuje go do SQLite.
  - Argumenty: `--input_glob` (glob plików, np. "data/**/*.txt"), `--db` (ścieżka do pliku SQLite).
  - Domyślny runner: DirectRunner (można przekazać dodatkowe opcje Beam).
- `searcher.py` — wczytuje indeks z SQLite i zwraca top‑K wyników dla zapytania.
  - Argumenty: `--db` (ścieżka do SQLite), `--query` (tekst zapytania), `--top_k` (ile wyników, domyślnie 10).
- `utils.py` — pomocnicze funkcje: tokenizacja, normalizacja, TF/IDF, I/O z SQLite, Beam PTransformy (`ReadFiles`, `ToDocTF`).

## Schemat SQLite (zgodny z utils.py)
- `documents(doc_id TEXT PRIMARY KEY, path TEXT, vector_json TEXT)` — wektory TF‑IDF dokumentów (JSON).
- `vocab(term TEXT PRIMARY KEY, df INTEGER, idf REAL)` — słownik z DF i IDF.
- `meta(key TEXT PRIMARY KEY, value TEXT)` — metadane (np. `N` = liczba dokumentów).

## Przykładowe użycie

1) Zbuduj indeks:
Windows (wirtualne środowisko):
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r [requirements.txt](http://_vscodecontentref_/0)
python [indexer.py](http://_vscodecontentref_/1) --input_glob "data/**/*.txt" --db index.sqlite
```