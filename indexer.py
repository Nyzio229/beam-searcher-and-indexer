import math
import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions

from utils import ReadFiles, ToDocTF, write_sqlite_rows


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Indexer (TF-IDF -> SQLite, ENGLISH ONLY)")
    parser.add_argument("--input_glob", required=True, help="Glob pattern for text files, e.g. './corpus/**/*.txt'")
    parser.add_argument("--db", required=True, help="Path to output SQLite DB, e.g. 'index.sqlite'")
    args, beam_args = parser.parse_known_args()

    pipeline_options = PipelineOptions(beam_args or ["--runner=DirectRunner"])

    with beam.Pipeline(options=pipeline_options) as p:
        # 1️⃣ Read files and compute term frequencies
        docs = (
            p
            | "Seed" >> beam.Create([None])
            | "ReadFiles" >> ReadFiles(args.input_glob)
            | "ToDocTF" >> beam.ParDo(ToDocTF(min_len=2, lemmatize=True))
        )

        # 2️⃣ Count total documents
        n_docs_pc = docs | "CountDocs" >> beam.combiners.Count.Globally()

        # 3️⃣ Compute document frequency (DF)
        df = (
            docs
            | "EmitDFOnes" >> beam.FlatMap(lambda kv: [(term, 1) for term in kv[1]["unique_terms"]])
            | "SumDF" >> beam.CombinePerKey(sum)
        )

        # 4️⃣ Compute IDF using smoothed formula
        df_idf = (
            df
            | "DFtoIDF" >> beam.MapTuple(
                lambda term, df_val, n_total: (term, (df_val, math.log((n_total + 1) / (df_val + 1)) + 1.0)),
                beam.pvalue.AsSingleton(n_docs_pc)
            )
        )

        # 5️⃣ Prepare IDF dictionary for side input
        idf_side = beam.pvalue.AsDict(df_idf | "IDFDict" >> beam.Map(lambda kv: (kv[0], kv[1][1])))

        # 6️⃣ Compute TF-IDF vectors (normalized)
        def compute_tfidf(doc, idf_dict):
            doc_id, payload = doc
            tf = payload["tf"]
            path = payload["path"]
            vec = {t: float(f) * idf_dict.get(t, 0.0) for t, f in tf.items() if idf_dict.get(t, 0.0) > 0.0}
            norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
            vec = {k: v / norm for k, v in vec.items()}
            return (doc_id, {"path": path, "tfidf": vec})

        tfidf_docs = docs | "TFIDF" >> beam.Map(compute_tfidf, idf_dict=idf_side)

        # 7️⃣ Prepare rows for SQLite
        to_db_docs = tfidf_docs | "DocRows" >> beam.Map(lambda kv: ("doc", (kv[0], kv[1]["path"], kv[1]["tfidf"])))
        to_db_vocab = df_idf | "VocabRows" >> beam.Map(lambda kv: ("vocab", (kv[0], kv[1][0], kv[1][1])))
        to_db_meta = n_docs_pc | "MetaRows" >> beam.Map(lambda n: ("meta", ("N", int(n))))

        # 8️⃣ Write everything to SQLite
        _ = (
            (to_db_docs, to_db_vocab, to_db_meta)
            | "FlattenAll" >> beam.Flatten()
            | "WriteSQLite" >> beam.MapTuple(lambda kind, payload: write_sqlite_rows(args.db, [(kind, payload)]))
        )

    print(f"✅ Index successfully built and saved to: {args.db}")


if __name__ == "__main__":
    main()
