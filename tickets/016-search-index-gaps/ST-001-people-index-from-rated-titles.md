---
id: ST-001
ticket: "016"
title: "Index directors from rated titles in people table"
priority: High
risk: low
status: Open
dependencies: []
subsystems: [backend]
---

# SUBTASK 01 — Index directors from rated titles in people table

---

## Objective

`search_people` fails to find directors (e.g. Martin Scorsese) whose well-known films
the user has already rated. The root cause: the people-writing loop in `pipeline.py`
only iterates `scored_candidates` (unrated titles). If a director's qualifying films are
all in the user's watchlist, they have zero rows in `title_people` and the `JOIN` in
`search_people` filters them out entirely.

`RatedTitle.directors` is always populated from the IMDB ratings CSV export and is
available in `titles` within the same pipeline scope. No changes to `candidates.py` are
needed — just extend the people-writing loop to also iterate rated titles.

---

## Pre-conditions

Confirm the bug: the people-writing loop only covers scored candidates.

```bash
grep -n "for candidate, _score in scored_candidates" app/services/pipeline.py
grep -n "for rated in titles" app/services/pipeline.py
```

Expected: first grep finds one match, second finds zero (the rated loop does not exist yet).

---

## Fix

### Step 1 — `app/services/pipeline.py`: extend the people-writing loop

Find the block at lines ~154–172:

```python
        # Populate people and title_people tables for the person browse feature
        people_map: dict[str, dict] = {}
        title_people_rows: list[dict] = []
        for candidate, _score in scored_candidates:
            for role, names in [
                ("director", candidate.directors),
                ("actor", candidate.actors),
                ("writer", candidate.writers),
                ("composer", candidate.composers),
                ("cinematographer", candidate.cinematographers),
            ]:
                for name in names:
                    name_id = name.lower()
                    if name_id not in people_map:
                        people_map[name_id] = {"name_id": name_id, "name": name}
                    title_people_rows.append(
                        {"imdb_id": candidate.imdb_id, "name_id": name_id, "role": role}
                    )
        write_people(list(people_map.values()), title_people_rows)
```

Replace with:

```python
        # Populate people and title_people tables for the person browse feature
        people_map: dict[str, dict] = {}
        title_people_rows: list[dict] = []
        for candidate, _score in scored_candidates:
            for role, names in [
                ("director", candidate.directors),
                ("actor", candidate.actors),
                ("writer", candidate.writers),
                ("composer", candidate.composers),
                ("cinematographer", candidate.cinematographers),
            ]:
                for name in names:
                    name_id = name.lower()
                    if name_id not in people_map:
                        people_map[name_id] = {"name_id": name_id, "name": name}
                    title_people_rows.append(
                        {"imdb_id": candidate.imdb_id, "name_id": name_id, "role": role}
                    )

        # Also index directors from rated titles so directors of well-known (already-rated)
        # films still appear in person search. RatedTitle.directors is always populated
        # from the IMDB CSV export, so no candidates.py changes are needed.
        for rated in titles:
            for name in rated.directors:
                name_id = name.lower()
                if name_id not in people_map:
                    people_map[name_id] = {"name_id": name_id, "name": name}
                title_people_rows.append(
                    {"imdb_id": rated.imdb_id, "name_id": name_id, "role": "director"}
                )

        write_people(list(people_map.values()), title_people_rows)
```

---

## Post-conditions

After the fix, the rated loop exists:

```bash
grep -n "for rated in titles" app/services/pipeline.py
```

Expected: one match in the people-writing block.

---

## Tests

```bash
uv run ruff check app/
uv run pytest tests/ -q
```

All existing tests must pass with zero new failures.

---

## Files Changed

- `app/services/pipeline.py`

---

## Commit Message

```
fix: index directors from rated titles in people table so search finds them (ST-001)
```
