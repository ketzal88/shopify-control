"""Linter mecánico para descripciones (spec §8.9). No reemplaza al humanizer;
lo complementa con chequeos de bajo falso-positivo."""

def lint(text: str, required_keywords, min_words: int, max_words: int):
    issues = []
    if "—" in text or "–" in text:
        issues.append("em-dash detectado (AI tell): reemplazar por coma/dos puntos")
    n = len(text.split())
    if n < min_words:
        issues.append(f"texto demasiado corto ({n} palabras, mínimo {min_words})")
    if n > max_words:
        issues.append(f"texto demasiado largo ({n} palabras, máximo {max_words})")
    low = text.lower()
    if required_keywords and not any(k.lower() in low for k in required_keywords):
        issues.append(f"falta al menos una keyword requerida: {required_keywords}")
    return issues
