"""Personal bookmarks, independent of author catalogs and translation languages."""


def project_key(project):
    return str(project.root.resolve()).casefold()


def records(profile, project):
    groups = profile.get("bookmarks", {})
    values = groups.get(project_key(project), []) if isinstance(groups, dict) else []
    result, seen = [], set()
    if not isinstance(values, list):
        return result
    for value in values:
        if not isinstance(value, dict):
            continue
        tab, entry, note = (value.get(key) for key in ("tab", "entry", "note"))
        if not isinstance(tab, str) or not isinstance(entry, str) or (tab, entry) in seen:
            continue
        result.append({"tab": tab, "entry": entry, "note": note if isinstance(note, str) else ""})
        seen.add((tab, entry))
    return result
