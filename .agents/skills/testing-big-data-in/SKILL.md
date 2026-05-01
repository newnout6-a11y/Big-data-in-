# Big-data-in Testing Skill

Use this skill when testing the `newnout6-a11y/Big-data-in-` Streamlit app, ingest pipeline, local Qdrant search, or Google Drive sync routing.

## Devin Secrets Needed

- `GROQ_API_KEY` / `GROQ_API_KEY_2` / `GROQ_API_KEY_3` — needed only to verify real Groq answer generation in the Streamlit UI. Without these, the app can still render diagnostic search fragments.
- `RCLONE_CONFIG` — needed only to verify real Google Drive uploads. Without it, use `RCLONE_BIN=/bin/echo` and `--dry-run` to validate routing.
- `HF_TOKEN` — optional; improves Hugging Face download reliability/rate limits for embedding models.

## Local environment notes

- Prefer `python -m streamlit run app.py` over the bare `streamlit` executable. The wrapper may point at system Python and fail to import packages installed in pyenv, such as `sentence_transformers`.
- Local Qdrant path is `qdrant_db/`. It is file-locked, so stop the running Streamlit process before opening the same local DB from a separate script.
- The Search tab defaults can filter by year. Test documents without harvested metadata may not appear if the UI applies `year >= 2018`; create a matching `harvested_meta/<pdf-stem>.json` with a modern `дата` such as `2024-01-01` before ingest.
- If testing only fragment/image rendering, Groq API credentials are not required; the UI shows retrieved fragments as diagnostic material even when answer generation fails.

## PDF image extraction E2E flow

1. Create or place a PDF in `all_pdfs/` with unique text and a visually distinctive embedded image.
2. Add `harvested_meta/<pdf-stem>.json` with at least:
   ```json
   {"источник":"local-e2e","дата":"2024-01-01","название":"Local E2E PDF"}
   ```
3. Rebuild local generated artifacts for an isolated run:
   - remove or move aside `chunks_v2.jsonl`, `qdrant_db/`, and `extracted_images/`
   - run `python ingest_v2.py --full --no-quality-filter`
   - assert `chunks_v2.jsonl` contains the PDF chunk with non-empty `images`, expected `year`, and an image path under `extracted_images/<sha>/page_N_img_M.png`
4. Run `python embed_resume_v2.py` and assert local `knowledge_hybrid` has the expected point count.
5. Start the app with:
   ```bash
   STREAMLIT_SERVER_HEADLESS=true python -m streamlit run app.py --server.port 8501 --server.address 0.0.0.0
   ```
6. In the browser Search tab, choose corpus or mixed search if needed, search the unique marker, and verify the retrieved fragment renders the image section and caption.

## Google Drive routing dry-run

Use this when real Drive credentials are unavailable:

```bash
PYTHONPATH=/path/to/Big-data-in- RCLONE_BIN=/bin/echo python -m harvester.gdrive_rclone push --dry-run
```

For extracted PDF images, assert the output includes a route like:

```text
copy /path/to/Big-data-in-/extracted_images gdrive:big-data/images/
```

The images route should copy the whole folder and should not include a file-type `--include` filter.
