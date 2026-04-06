---
ticket: "002"
subtask: 7
title: "Backend + Frontend: CSV File Upload Fallback"
status: open
effort: medium
component: full_stack
depends_on: [4]
files_modified:
  - app/api/routes.py
  - frontend/app/composables/useApi.ts
  - frontend/app/pages/index.vue
files_created: []
---

# SUBTASK 07: Backend + Frontend — CSV File Upload Fallback

---

## Objective

Add a `POST /upload-watchlist` endpoint and a corresponding frontend file input so users can manually upload their IMDB-exported CSV when the URL-based fetch fails or is unavailable.

## Context

The URL-based fetch (subtask 1) may fail if:
- IMDB's export endpoint requires authentication (returns 403)
- The user's ratings are private
- IMDB changes its export URL structure

In these cases, users should be able to fall back to manually exporting their CSV from IMDB and uploading it directly through the UI. This preserves the web-accessible workflow without requiring server filesystem access.

## Backend Implementation

### New endpoint: `POST /upload-watchlist`

```python
from fastapi import UploadFile, File
from pathlib import Path

@router.post("/upload-watchlist")
async def upload_watchlist(file: UploadFile = File(...)) -> dict:
    """Accept a manually exported IMDB ratings CSV and save it as the watchlist."""
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a .csv file.")
    
    content = await file.read()
    
    # Basic validation: check for expected IMDB CSV headers
    text = content.decode("utf-8", errors="replace")
    if "Const" not in text or "Your Rating" not in text:
        raise HTTPException(
            status_code=422,
            detail="File does not appear to be an IMDB ratings export. Expected columns: Const, Your Rating."
        )
    
    # Save to watchlist path
    settings = get_settings()
    watchlist_path = PROJECT_ROOT / settings.data.watchlist_path
    watchlist_path.parent.mkdir(parents=True, exist_ok=True)
    watchlist_path.write_text(text, encoding="utf-8")
    
    return {"message": "Watchlist uploaded successfully.", "filename": file.filename}
```

**No pipeline run triggered** — the upload just saves the file. The user then clicks generate to run the pipeline using the saved CSV.

## Frontend Implementation

### 1. Add upload function to `useApi.ts`

```typescript
async function uploadWatchlist(file: File): Promise<{ message: string }> {
  const formData = new FormData()
  formData.append('file', file)
  return $fetch('/api/v1/upload-watchlist', {
    method: 'POST',
    body: formData,
  })
}
```

### 2. Add file input to `index.vue`

Below the IMDB URL field, add a secondary option:

```vue
<v-file-input
  label="Or upload CSV manually"
  accept=".csv"
  hint="Export from IMDB → Your ratings → Export"
  persistent-hint
  variant="outlined"
  prepend-icon="mdi-upload"
  @update:model-value="handleCsvUpload"
/>
```

### 3. Handle upload in `index.vue`

```typescript
async function handleCsvUpload(files: File | File[] | null) {
  const file = Array.isArray(files) ? files[0] : files
  if (!file) return
  try {
    await api.uploadWatchlist(file)
    // Trigger pipeline with local CSV (no URL)
    await generate()
  } catch (e) {
    // Display error via existing error handling
  }
}
```

## Acceptance Criteria

- [ ] `POST /api/v1/upload-watchlist` accepts multipart CSV upload
- [ ] Uploaded file saved to `data/watchlist.csv`
- [ ] Non-CSV files rejected with 400
- [ ] Files missing expected IMDB headers rejected with 422
- [ ] Frontend file input visible below the IMDB URL field
- [ ] Uploading a CSV triggers a pipeline run and displays recommendations
- [ ] Success/error feedback shown to user
- [ ] Endpoint documented in CLAUDE.md API table (handled in subtask 8)

---

> **On completion:** update your row in [progress.md](progress.md) to `Done`, add any non-obvious decisions to [decisions.md](decisions.md), and verify the Definition of Done checklist in `CLAUDE.md`.
