"""One-shot backfill: translate missing zh_title for existing Firestore articles.

Usage:
    python scripts/backfill_zh_title.py [--dry-run] [--limit N]

Requires:
    FIREBASE_SERVICE_ACCOUNT_JSON (or ADC)
    GEMINI_API_KEY
    FIRESTORE_COLLECTION_PREFIX (optional, default: tech_pulse)
"""
import argparse
import os
import sys
import time

# Allow running from repo root without installing the package.
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from llm.gemini_client import GEMINI_FLASH_MODEL, make_client

COLLECTION_PREFIX = os.getenv("FIRESTORE_COLLECTION_PREFIX", "tech_pulse").strip("_")
COLLECTION = os.getenv("TECH_PULSE_FIRESTORE_COLLECTION", f"{COLLECTION_PREFIX}_memory_items")
SLEEP_BETWEEN_CALLS = 0.3  # seconds — stay well under Gemini rate limits


def _firestore_client():
    from google.cloud import firestore  # type: ignore[import]
    raw = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "")
    if raw.strip():
        import json
        from google.oauth2 import service_account  # type: ignore[import]
        decoded = raw if raw.strip().startswith("{") else __import__("base64").b64decode(raw).decode()
        creds = service_account.Credentials.from_service_account_info(
            json.loads(decoded),
            scopes=["https://www.googleapis.com/auth/cloud-firestore"],
        )
        return firestore.Client(credentials=creds)
    return firestore.Client()


def _translate_title(client, title: str) -> str:
    """Call Gemini Flash to produce a zh_title (≤28 繁體中文 chars)."""
    from google.genai import types  # type: ignore[import]
    prompt = (
        "Translate the following English tech news headline into a concise "
        "Traditional Chinese (繁體中文) title, ≤28 characters. "
        "Keep product names, company names, and version numbers in their original form. "
        "No trailing punctuation. Write like a serious tech editor.\n\n"
        f"Headline: {title}"
    )
    response = client.models.generate_content(
        model=GEMINI_FLASH_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction="Output only the translated title. No explanation, no quotes.",
            max_output_tokens=64,
            temperature=0.2,
        ),
    )
    text = (response.text or "").strip().strip('"').strip("「」")
    return text[:28] if text else ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill zh_title for Firestore articles")
    parser.add_argument("--dry-run", action="store_true", help="Print proposed titles without writing")
    parser.add_argument("--limit", type=int, default=0, help="Process at most N docs (0 = unlimited)")
    args = parser.parse_args()

    print(f"Collection: {COLLECTION}  dry_run={args.dry_run}  limit={args.limit or 'unlimited'}")

    db = _firestore_client()
    gemini = make_client()
    collection = db.collection(COLLECTION)

    docs = list(collection.stream())
    missing = [d for d in docs if not (d.to_dict() or {}).get("zh_title", "")]
    print(f"Total docs: {len(docs)}  Missing zh_title: {len(missing)}")

    if args.limit:
        missing = missing[: args.limit]

    total = len(missing)
    written = 0
    for i, doc in enumerate(missing, 1):
        data = doc.to_dict() or {}
        title = (data.get("title") or data.get("entity") or "").strip()
        if not title:
            print(f"  [{i}/{total}] {doc.id} — no title, skip")
            continue

        zh = _translate_title(gemini, title)
        if not zh:
            print(f"  [{i}/{total}] {doc.id} — Gemini returned empty, skip")
            continue

        print(f"  [{i}/{total}] {doc.id}")
        print(f"    EN: {title[:80]}")
        print(f"    ZH: {zh}")

        if not args.dry_run:
            doc.reference.set({"zh_title": zh}, merge=True)
            written += 1

        if i < total:
            time.sleep(SLEEP_BETWEEN_CALLS)

    if args.dry_run:
        print(f"\nDry run complete — {total} docs would be updated.")
    else:
        print(f"\nDone — {written}/{total} docs updated.")


if __name__ == "__main__":
    main()
