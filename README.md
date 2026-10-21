# BluntScore — Multi-Source Sentiment Analysis & Rating Engine

BluntScore ingests reviews from multiple sources, classifies each opinion as
positive / neutral / negative using NLP, and produces a normalized **0–100
sentiment score** for any searchable topic, served through a FastAPI REST API.

**Tech:** Python, FastAPI, SQLAlchemy, SQLite, VADER

## Quick start
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate   |   Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # Windows: copy .env.example .env
uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000/docs for interactive API docs.

## Run tests
```bash
pytest -v
```
