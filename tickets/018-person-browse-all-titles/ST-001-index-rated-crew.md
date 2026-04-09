---
id: ST-001
ticket: "018"
title: "Index actor/writer/composer crew from rated titles in title_people"
priority: High
risk: low
status: Open
dependencies: []
subsystems: [backend]
---

# SUBTASK 01 — Index actor/writer/composer crew from rated titles in title_people

---

## Objective

When browsing by person (e.g. Paul Newman), no rated titles appear because
`title_people` only indexes directors from rated titles (per ticket 016). Actors,
writers, composers, and cinematographers from rated titles are completely absent.

Extend the people-writing loop in `pipeline.py` to index:
- `writers` from `RatedTitle.writers` (always present from the IMDB CSV)
- `actors`, `composers`, `cinematographers` from `rated_actors`, `rated_composers`,
  `rated_cinematographers` (available on full builds; `None` on cache hits — skip when absent)

---

## Pre-conditions

The existing rated loop only indexes directors:

```bash
grep -n "for rated in titles" app/services/pipeline.py
```

Expected: one match, and the loop only adds `"director"` rows.

---

## Fix

### Step 1 — `app/services/pipeline.py`: extend rated-title people indexing

Find the block at lines ~176–183:

```python
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
```

Replace with:

```python
        # Index all crew roles from rated titles so person search finds actors/writers/etc.
        # directors and writers come from the IMDB CSV (always available).
        # actors/composers/cinematographers come from the dataset build (None on cache hits).
        for rated in titles:
            rated_role_lists: list[tuple[str, list[str]]] = [
                ("director", rated.directors),
                ("writer", rated.writers),
            ]
            if rated_actors is not None:
                rated_role_lists.append(("actor", rated_actors.get(rated.imdb_id, [])))
            if rated_composers is not None:
                rated_role_lists.append(("composer", rated_composers.get(rated.imdb_id, [])))
            if rated_cinematographers is not None:
                rated_role_lists.append(
                    ("cinematographer", rated_cinematographers.get(rated.imdb_id, []))
                )
            for role, names in rated_role_lists:
                for name in names:
                    name_id = name.lower()
                    if name_id not in people_map:
                        people_map[name_id] = {"name_id": name_id, "name": name}
                    title_people_rows.append(
                        {"imdb_id": rated.imdb_id, "name_id": name_id, "role": role}
                    )
```

---

## Post-conditions

```bash
grep -n "rated_role_lists" app/services/pipeline.py
```

Expected: one match in the people-writing block.

---

## Tests

```bash
uv run ruff check app/
uv run pytest tests/ -q
```

---

## Files Changed

- `app/services/pipeline.py`

---

## Commit Message

```
fix: index actor/writer/composer crew from rated titles in title_people (ST-001)
```
