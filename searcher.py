from typing import Dict, Tuple
import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions

from utils import (
    load_index,
    tokenize,
    normalize_tokens,
    tf_from_tokens,
    tfidf_from_tf,
    cosine_sparse,
)

def build_query_vec(query: str, vocab_idf: Dict[str, float]) -> Dict[str, float]:
    """Build an ENGLISH-ONLY TF-IDF vector for the query."""
    tokens = normalize_tokens(tokenize(query), min_len=2, lemmatize=True)
    tf = tf_from_tokens(tokens)
    q_vec = tfidf_from_tf(tf, vocab_idf)
    return q_vec

class ComputeSimilarity(beam.DoFn):
    """Compute cosine(query, doc_vector) -> (score, doc_id, path)."""
    def __init__(self, query_vec: Dict[str, float]):
        self.query_vec = query_vec
    def process(self, doc_row: Tuple[str, str, Dict[str, float]]):
        doc_id, path, vec = doc_row
        score = cosine_sparse(self.query_vec, vec)
        if score > 0.0:
            yield (score, doc_id, path)

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Searcher (cosine TF-IDF, ENGLISH ONLY)")
    parser.add_argument("--db", required=True, help="Path to SQLite index")
    parser.add_argument("--query", required=True, help="Search query (English)")
    parser.add_argument("--top_k", type=int, default=10, help="Number of results to show")
    args, beam_args = parser.parse_known_args()

    # 1) Load index
    N, vocab_idf, documents = load_index(args.db)
    if N == 0 or not documents:
        print("Index empty. Run indexer first.")
        return

    # 2) Build query vector
    q_vec = build_query_vec(args.query, vocab_idf)

    # 3) Compute similarities with Beam and print Top-K
    pipeline_options = PipelineOptions(beam_args or ["--runner=DirectRunner"])
    with beam.Pipeline(options=pipeline_options) as p:
        scores = (
            p
            | "CreateDocs" >> beam.Create(documents)
            | "ComputeScores" >> beam.ParDo(ComputeSimilarity(q_vec))
        )

        top = scores | "TopK" >> beam.combiners.Top.Of(args.top_k, key=lambda t: t[0])

        class PrintResults(beam.DoFn):
            def process(self, _, top_list):
                # Ensure descending order by score for display
                top_sorted = sorted(top_list, key=lambda t: (-t[0], t[1]))
                for rank, (score, doc_id, path) in enumerate(top_sorted, 1):
                    print(f"{rank:2d}. score={score:.5f}  id={doc_id}  path={path}")
                yield

        _ = (
            p
            | "Dummy" >> beam.Create([None])
            | "Print" >> beam.ParDo(PrintResults(), beam.pvalue.AsSingleton(top))
        )

if __name__ == "__main__":
    main()
