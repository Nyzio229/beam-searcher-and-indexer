# 🔍 Indekser i wyszukiwarka dokumentów (Apache Beam + TF-IDF, tylko język angielski)

Projekt implementuje system wyszukiwania informacji składający się z dwóch modułów:

1. **Indekser (`indexer.py`)** – przetwarza pliki tekstowe i buduje indeks TF-IDF przy użyciu frameworka **Apache Beam**.  
2. **Wyszukiwarka (`searcher.py`)** – umożliwia wyszukiwanie dokumentów na podstawie zapytania tekstowego, korzystając z **podobieństwa cosinusowego**.

Całość działa **wyłącznie dla tekstów w języku angielskim** (wykorzystuje stop-słowa i lematyzację z pakietu NLTK).

---

## Jak działa system

###  Indekser (`indexer.py`)

Indekser przeszukuje folder z plikami `.txt`, przetwarza je w potoku Apache Beam i generuje plik `tfidf_index.json`, który zawiera:
- unikalny identyfikator dokumentu (UUID),
- ścieżkę do pliku,
- wektor TF-IDF opisujący wagi słów w dokumencie.

**Etapy przetwarzania:**
1. **Wczytanie plików** – pobiera zawartość każdego pliku.
2. **Tokenizacja i lematyzacja** – usuwa krótkie słowa i stop-słowa, zamienia słowa na formy podstawowe.
3. **Zliczanie TF i DF** – oblicza częstość słów i liczbę dokumentów zawierających dane słowo.
4. **Obliczanie TF-IDF** – \( tfidf(t, d) = tf(t, d) \times log(1 + N / df(t)) \)
5. **Zapis indeksu do JSON**.

**Przykład uruchomienia (lokalnie):**
```bash
python indexer.py --src "./test" --out "tfidf_index.json"
```

---

### Wyszukiwarka (`searcher.py`)

Wczytuje utworzony indeks TF-IDF i porównuje zapytanie użytkownika z każdym dokumentem, obliczając **podobieństwo cosinusowe**.

**Etapy działania:**
1. Wczytuje plik `tfidf_index.json`.
2. Tokenizuje i lematyzuje zapytanie.
3. Oblicza wektor TF-IDF zapytania.
4. Liczy podobieństwo cosinusowe z każdym dokumentem.
5. Zwraca posortowaną listę dokumentów najbardziej dopasowanych.

**Przykład uruchomienia:**
```bash
python searcher.py --index "tfidf_index.json" --q "machine learning models" --k 5
```

---

## Instalacja i uruchamianie (lokalnie)

### Utworzenie wirtualnego środowiska
```bash
python -m venv .venv
```

Aktywacja:
- **Windows (PowerShell):**
  ```powershell
  .venv\Scripts\Activate.ps1
  ```
- **Linux/macOS:**
  ```bash
  source .venv/bin/activate
  ```

### Instalacja zależności
```bash
pip install -r requirements.txt
```

### Pobranie danych NLTK
Jeśli uruchamiasz projekt po raz pierwszy:
```python
python -c "import nltk; nltk.download('stopwords'); nltk.download('wordnet'); nltk.download('omw-1.4')"
```

---

## Uruchamianie z Dockerem

Projekt można uruchomić w pełni w kontenerze Dockera.  
Obraz zawiera:
- Pythona 3.11 (slim),
- Apache Beam,
- NLTK (z pobranymi zasobami),
- wszystkie skrypty projektu.

---

### Budowanie obrazu

Upewnij się, że w katalogu projektu masz plik `Dockerfile`, a następnie uruchom:

```bash
docker build -t beam-ir:latest .
```

---

### Uruchomienie indeksera w kontenerze

**Windows (PowerShell):**
```powershell
docker run --rm `
  -v "${PWD}\test:/data/test:ro" `
  -v "${PWD}\out:/data/out" `
  beam-ir:latest `
  indexer.py --src "/data/test" --out "/data/out/tfidf_index.json"
```

**Linux/macOS (Bash):**
```bash
docker run --rm   -v "$(pwd)/test:/data/test:ro"   -v "$(pwd)/out:/data/out"   beam-ir:latest   indexer.py --src "/data/test" --out "/data/out/tfidf_index.json"
```

---

###  Uruchomienie wyszukiwarki w kontenerze

**Windows (PowerShell):**
```powershell
docker run --rm `
  -v "${PWD}\out:/data/out" `
  beam-ir:latest `
  searcher.py --index "/data/out/tfidf_index.json" --q "machine learning models" --k 5
```

**Linux/macOS (Bash):**
```bash
docker run --rm   -v "$(pwd)/out:/data/out"   beam-ir:latest   searcher.py --index "/data/out/tfidf_index.json" --q "machine learning models" --k 5
```

---

###  Uruchamianie z Docker Compose (opcjonalne)

Plik `docker-compose.yml`:
```yaml
version: "3.9"
services:
  beam-ir:
    build:
      context: .
      dockerfile: Dockerfile
    image: beam-ir:latest
    container_name: beam-ir
    working_dir: /app
    volumes:
      - ./test:/data/test:ro
      - ./out:/data/out
```

Budowa:
```bash
docker compose build
```

Uruchomienie indeksera:
```bash
docker compose run --rm beam-ir indexer.py --src "/data/test" --out "/data/out/tfidf_index.json"
```

Uruchomienie wyszukiwarki:
```bash
docker compose run --rm beam-ir searcher.py --index "/data/out/tfidf_index.json" --q "machine learning" --k 5
```

---

##  Przykładowe użycie krok po kroku

```bash
mkdir -p test out
echo "Python is a great programming language." > test/doc1.txt
echo "Machine learning and AI are related fields." > test/doc2.txt

docker build -t beam-ir:latest .

docker run --rm -v "$(pwd)/test:/data/test:ro" -v "$(pwd)/out:/data/out" beam-ir:latest indexer.py --src "/data/test" --out "/data/out/tfidf_index.json"

docker run --rm -v "$(pwd)/out:/data/out" beam-ir:latest searcher.py --index "/data/out/tfidf_index.json" --q "artificial intelligence programming" --k 5
```

---

##  Podsumowanie

- **Indekser** tworzy indeks TF-IDF z plików tekstowych.  
- **Wyszukiwarka** znajduje najbardziej podobne dokumenty do zapytania.  
- Całość działa zarówno lokalnie, jak i w Dockerze.  
- System przeznaczony jest dla **języka angielskiego** i stanowi świetny przykład użycia **Apache Beam** do przetwarzania tekstu.
