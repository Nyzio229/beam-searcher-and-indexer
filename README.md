# beam-searcher-and-indexer

Narzędzie edukacyjne do indeksowania dokumentów (TF‑IDF) i prostego wyszukiwania (cosine + Top‑K). Projekt używa Apache Beam do przetwarzania i przechowuje indeks jako JSON. Tokenizacja, stopwords i lematyzacja działają tylko dla języka angielskiego.

## Co robi projekt
- Buduje TF‑IDF index (JSON) z kolekcji plików .txt.
- Pozwala wyszukiwać zapytania przy użyciu wektora TF‑IDF i miary cosinusowej.
- Pipeline oparty na Apache Beam (domyślnie DirectRunner).

## Główne pliki
- `indexer.py` — buduje indeks i zapisuje go do pliku JSON.
  - Argumenty: `--src` (katalog z .txt plikami, rekurencyjnie), `--out` (ścieżka do pliku wynikowego, domyślnie `tfidf_index.json`).
- `searcher.py` — ładuje JSON index i zwraca top‑K wyników.
  - Argumenty: `--index` (ścieżka do JSON index), `--q` (zapytanie), `--k` (Top‑K).
- `utils.py` — tokenizacja, normalizacja, TF/IDF i Beam DoFn-y (`LoadText`, `TermStatsFn`, `MakeTfIdfFn`).
- `Dockerfile` — obraz z Python + wymaganymi zasobami NLTK (stopwords, wordnet).
- `requirements.txt` — wymagane pakiety.

## Format indeksu
Index to lista JSON obiektów:
- id: unikalne id dokumentu (UUID)
- path: oryginalna ścieżka pliku
- tfidf: słownik token → waga TF‑IDF
searcher.py oblicza normę wektorów przy wczytywaniu, aby użyć jej w miarze cosinusowej.

## Szybkie użycie — lokalnie (Windows)

1) Utwórz i aktywuj venv:
```bash
python -m venv .venv
.venv\Scripts\activate
```

2) Zainstaluj zależności:
```bash
pip install -r requirements.txt
```

3) Pobierz zasoby NLTK (jeśli nie były zainstalowane):
```bash
python -c "import nltk; nltk.download('stopwords'); nltk.download('wordnet'); nltk.download('omw-1.4')"
```

4) Zbuduj indeks (przykład z katalogu `test` w repozytorium):
```bash
python indexer.py --src test --out tfidf_index.json
```

5) Wyszukaj:
```bash
python searcher.py --index tfidf_index.json --q "lorem ipsum" --k 5
```

## Użycie z Dockerem

Obraz zawiera wymagane NLTK pakiety, więc nie trzeba ręcznie pobierać korpusów.

1) Zbuduj obraz:
```bash
docker build -t beam-indexer .
```

2) Uruchom indexer (Windows CMD przykładowo montuje bieżący katalog do /data):
```bash
docker run --rm -v %cd%/test:/data -it beam-indexer python indexer.py --src /data --out /data/tfidf_index.json
```
(PowerShell: use ${PWD} zamiast %cd%)

3) Uruchom searcher:
```bash
docker run --rm -v %cd%/test:/data -it beam-indexer python searcher.py --index /data/tfidf_index.json --q "lorem ipsum" --k 5
```

## Zależności
- Python 3.8+
- apache-beam[gcp] (podany w requirements.txt)
- nltk (stopwords, wordnet, omw-1.4)

Instalacja bez `requirements.txt`:
```bash
pip install "apache-beam[gcp]==2.53.0" nltk
```

## Uwagi
- Przetwarzanie tekstu jest EN‑ONLY. Wyniki dla innych języków będą słabe.
- Apache Beam używa domyślnie DirectRunner; można przekazać dodatkowe opcje PipelineOptions przez CLI jeśli potrzeba innego runnera.
- Index jest zapisywany jako pojedynczy JSON (lista dokumentów). Dla dużych kolekcji warto rozważyć inny format lub magazyn (np. baza danych) oraz batchowy zapis.
