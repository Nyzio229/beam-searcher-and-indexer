import math
import apache_beam as beam
from apache_beam.testing.test_pipeline import TestPipeline
from apache_beam.testing.util import assert_that, equal_to

from utils import TermStatsFn, MakeTfIdfFn

# Dane testowe (proste, bez stop-słów)
DOC_ID_1 = "doc-1"
DOC_ID_2 = "doc-2"

INPUT_DOCS = [
    {"id": DOC_ID_1, "path": "path1", "text": "apple apple banana"},
    {"id": DOC_ID_2, "path": "path2", "text": "banana orange"},
]

# Oczekiwany TF: (doc_id, path, {token:count}, total_tokens)
EXPECTED_TF = [
    (DOC_ID_1, "path1", {"apple": 2, "banana": 1}, 3),
    (DOC_ID_2, "path2", {"banana": 1, "orange": 1}, 2),
]

# Oczekiwane pary do DF: (token, doc_id)
EXPECTED_DF_PAIRS = [
    ("apple", DOC_ID_1),
    ("banana", DOC_ID_1),
    ("banana", DOC_ID_2),
    ("orange", DOC_ID_2),
]


def test_termstats_tf_and_df():
    """
    Sprawdza, że TermStatsFn:
    - liczy TF i total_tokens per dokument,
    - emituje pary (token, doc_id) do liczenia DF.
    """
    with TestPipeline() as p:
        inp = p | "CreateDocs" >> beam.Create(INPUT_DOCS)

        outputs = inp | "TermStats" >> beam.ParDo(TermStatsFn()).with_outputs("tf", "df")
        tf_pc = outputs.tf
        df_pc = outputs.df

        assert_that(tf_pc, equal_to(EXPECTED_TF), label="CheckTF")
        # Distinct nie jest robione tutaj — porównujemy surowe pary (token, doc_id) z emitowanych counts.keys()
        assert_that(df_pc, equal_to(EXPECTED_DF_PAIRS), label="CheckDFPairs")


def _approx_equal(a: float, b: float, tol: float = 1e-9) -> bool:
    return math.isclose(a, b, rel_tol=0, abs_tol=tol)


def _match_tfidf(actual_list):
    """
    Niestandardowy matcher dla assert_that — porównuje TF-IDF z tolerancją.
    Zakładamy:
      N = 2
      df: apple=1, banana=2, orange=1
      idf = log(1 + N/df)
    """
    # Tworzymy słownik id -> rekord
    actual_by_id = {d["id"]: d for d in actual_list}

    # Obliczenia oczekiwane:
    # Doc1: "apple apple banana" => total=3
    #  - apple: tf=2/3, idf=log(1+2/1)=log(3)
    #  - banana: tf=1/3, idf=log(1+2/2)=log(2)
    idf_apple = math.log(3.0)
    idf_banana = math.log(2.0)
    idf_orange = math.log(3.0)

    exp_doc1 = {
        "apple": (2.0 / 3.0) * idf_apple,   # ~0.7324080774
        "banana": (1.0 / 3.0) * idf_banana, # ~0.2310491866
    }
    # Doc2: "banana orange" => total=2
    #  - banana: tf=1/2, idf=log(2)
    #  - orange: tf=1/2, idf=log(3)
    exp_doc2 = {
        "banana": 0.5 * idf_banana,  # ~0.3465735903
        "orange": 0.5 * idf_orange,  # ~0.5493061443
    }

    # Sprawdzenie doc1
    d1 = actual_by_id.get(DOC_ID_1)
    assert d1 is not None, "Brak wyniku TF-IDF dla DOC_ID_1"
    for t, v in exp_doc1.items():
        assert t in d1["tfidf"], f"Brak tokena {t} w TF-IDF dla DOC_ID_1"
        assert _approx_equal(d1["tfidf"][t], v, tol=1e-9), f"TF-IDF dla {t} w DOC_ID_1 różni się: {d1['tfidf'][t]} vs {v}"

    # Sprawdzenie doc2
    d2 = actual_by_id.get(DOC_ID_2)
    assert d2 is not None, "Brak wyniku TF-IDF dla DOC_ID_2"
    for t, v in exp_doc2.items():
        assert t in d2["tfidf"], f"Brak tokena {t} w TF-IDF dla DOC_ID_2"
        assert _approx_equal(d2["tfidf"][t], v, tol=1e-9), f"TF-IDF dla {t} w DOC_ID_2 różni się: {d2['tfidf'][t]} vs {v}"


def test_make_tfidf_with_side_inputs():
    """
    Sprawdza, że MakeTfIdfFn liczy TF-IDF poprawnie, wykorzystując side inputy:
      - df_map (słownik: token -> DF)
      - N (liczba dokumentów)
    """
    # Bazując na EXPECTED_TF wyliczymy TF-IDF
    df_map = {"apple": 1, "banana": 2, "orange": 1}
    N = 2

    with TestPipeline() as p:
        tf_pc = p | "CreateTF" >> beam.Create(EXPECTED_TF)

        df_pc = p | "CreateDFMap" >> beam.Create([df_map])
        N_pc = p | "CreateN" >> beam.Create([N])

        df_view = beam.pvalue.AsSingleton(df_pc)
        N_view = beam.pvalue.AsSingleton(N_pc)

        out = tf_pc | "ComputeTfIdf" >> beam.ParDo(MakeTfIdfFn(), df_map=df_view, N=N_view)

        # Używamy niestandardowego matchera z tolerancją na floaty
        assert_that(out, _match_tfidf, label="CheckTfIdfValues")


if __name__ == "__main__":
    # Pozwala odpalić bezpośrednio: python test_utils.py
    import pytest
    raise SystemExit(pytest.main([__file__]))