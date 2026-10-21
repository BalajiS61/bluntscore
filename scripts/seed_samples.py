"""Load the bundled sample dataset into your real database (bluntscore.db).

Run from the project folder:   python -m scripts.seed_samples
Safe to run more than once: reviews and ratings that already exist are skipped.
"""
from app.db.database import SessionLocal, init_db
from app.services.ingestion_service import load_sample_dataset


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        results = load_sample_dataset(db)
        print(f"\n{'Topic':<22}{'Score':>7}  {'Verdict':<15}{'New reviews':>12}{'New ratings':>13}")
        print("-" * 69)
        for r in results:
            score = "-" if r.breakdown.score is None else f"{r.breakdown.score:.1f}"
            print(f"{r.topic.name:<22}{score:>7}  {r.breakdown.verdict:<15}"
                  f"{r.inserted_reviews:>12}{r.inserted_ratings:>13}")
    finally:
        db.close()
    print("\nDone. Start the server and open /docs to explore the data.")


if __name__ == "__main__":
    main()
