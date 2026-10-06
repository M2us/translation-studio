"""Human-readable constraint descriptions; the core remains the validator."""
import json
from .i18n import tr


def literal(value):
    return json.dumps(value, ensure_ascii=False)


def describe_rules(rules, language):
    rows = []
    def add(key, text):
        severity = tr("rule_" + rules.get("severity", {}).get(key, "error"), language)
        rows.append(severity + ": " + text)
    if not rules.get("allowEmpty", False):
        add("allowEmpty", tr("rule_nonempty", language))
    for key, label in (("maxCodePoints", "rule_chars"), ("maxLines", "rule_lines")):
        if rules.get(key) is not None:
            add(key, tr(label, language, limit=rules[key]))
    if rules.get("maxLines") is not None:
        rows.append(tr("rule_newline", language, token=literal(rules.get("lineBreakToken", "\n"))))
    byte = rules.get("byteLimit")
    if byte:
        add("byteLimit", tr("rule_bytes", language, limit=byte["maxBytes"],
                            encoding=byte["encoding"], terminator=byte["terminatorBytes"]))
    for token in rules.get("requiredTokens", []):
        add("requiredTokens", tr("rule_token", language, token=literal(token["token"]), count=token["count"]))
    if rules.get("allowedCharacters") is not None:
        add("allowedCharacters", tr("rule_allowed", language, characters=literal(rules["allowedCharacters"])))
    if rules.get("forbiddenCharacters"):
        add("forbiddenCharacters", tr("rule_forbidden", language, characters=literal(rules["forbiddenCharacters"])))
    return "\n".join(rows) or tr("rule_none", language)


def describe_issue(issue, language):
    if issue.code == "empty_text":
        message = tr("rule_nonempty", language)
    elif issue.code == "constraint":
        rule, actual, limit = (issue.values[key] for key in ("rule", "actual", "limit"))
        if rule in ("maxCodePoints", "maxLines", "byteLimit") and isinstance(actual, int):
            message = tr("exceeded_" + rule, language, excess=actual - limit, actual=actual, limit=limit)
        elif rule in ("allowedCharacters", "forbiddenCharacters"):
            message = tr("invalid_characters", language, characters=actual)
        elif rule == "requiredTokens":
            message = tr("invalid_token", language, actual=actual, limit=limit)
        else:
            message = issue.message(language)
    else:
        message = issue.message(language)
    return tr("rule_" + issue.severity, language) + ": " + message
