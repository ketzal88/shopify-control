"""Linter mecánico para descripciones (checklist §9). No reemplaza al humanizer;
lo complementa con chequeos de bajo falso-positivo.

Antes cubría 3 de los 8 ítems del checklist y no era ejecutable (no tenía CLI),
así que el "corré el lint" del skill era autorreportado. Ahora cubre además:
palabras prohibidas (§2), registro/voseo (§2) y presencia de bloque GEO (§5),
y se puede correr de verdad:

    echo "texto" | python .claude/hooks/description_lint.py --keywords "acero quirúrgico" --geo

Salida: una línea por issue en stderr, exit 1 si hay issues, exit 0 si está limpio.
IMPORTANTE: lintear el TEXTO PLANO, no el HTML (el CLI ya despeja tags).
"""
import argparse
import re
import sys

# §2 Vocabulario NO — materiales que blunua NO usa (el material es acero quirúrgico,
# así que declarar oro/plata sería un claim falso sobre el producto).
# Ojo con los límites de palabra: "dorado" y "plateado" describen el ACABADO y son
# válidos; "oro" y "plata" como material, no.
FORBIDDEN_MATERIAL = [
    r"\boro\b", r"\bplata\b", r"\bchapad[oa]s?\b", r"\benchapad[oa]s?\b",
    r"\blaminad[oa]s?\b", r"bañad[oa]s? en oro", r"\bplaqué\b",
]

# §2 Lujo-vacío y superlativos.
FORBIDDEN_HYPE = [
    r"\bde lujo\b", r"\blujo\b", r"\blujosa?\b", r"\bexclusiv[oa]s?\b",
    r"\bglamour\b", r"\bdeslumbrante\b", r"\bespectacular\b",
    r"\bincreíble\b", r"\bde ensueño\b", r"\búnico en el mundo\b",
    r"\bel mejor\b", r"\bla mejor\b",
]

# §2 Claims médicos. Nota deliberada: NO incluimos "mágico" aunque figure en la
# lista curada, porque la propia tienda tiene colecciones llamadas "Brillo mágico".
# Un linter que se dispara con el nombre de una colección de la marca termina
# desactivado. El ítem humano del checklist sigue cubriendo el espíritu.
FORBIDDEN_MEDICAL = [
    r"\bcurativ[oa]s?\b", r"\bpropiedades curativas\b", r"\bmedicinal(es)?\b",
    r"\bsana\b", r"\bsanación\b", r"\bcura\b",
]

# §2 Registro: blunua es español neutro SIN voseo.
VOSEO = [
    r"\bvos\b", r"\btenés\b", r"\bquerés\b", r"\bpodés\b", r"\bsabés\b", r"\bsos\b",
    r"\bdecime\b", r"\bfijate\b", r"\bmirá\b", r"\bhacé\b", r"\bandá\b", r"\bvení\b",
    r"\bponé\b", r"\bdejá\b", r"\bmandá\b", r"\brespondé\b", r"\bmejorá\b",
    r"\bescribí\b", r"\belegí\b", r"\bprobá\b", r"\bcontame\b", r"\bavisame\b",
    r"\bacordate\b", r"\bquedate\b", r"\bllevate\b",
]

DEFAULT_MIN_WORDS = 80
DEFAULT_MAX_WORDS = 150


def strip_html(text: str) -> str:
    """Texto plano: los tags no son palabras y no deben contarse ni chequearse."""
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _hits(text_low: str, patterns) -> list:
    return [p for p in patterns if re.search(p, text_low)]


def _pretty(pattern: str) -> str:
    """La regex sin sus artefactos, para que el mensaje se lea como una palabra."""
    s = pattern.replace(r"\b", "")
    s = re.sub(r"\(([^)]*)\)\?", "", s)          # medicinal(es)? -> medicinal
    s = re.sub(r"\[([^\]])[^\]]*\]", r"\1", s)   # chapad[oa]s?  -> chapados?
    s = re.sub(r".\?", "", s)                    # chapados?     -> chapado
    return s.strip()


def lint(text: str, required_keywords=None, min_words: int = DEFAULT_MIN_WORDS,
         max_words: int = DEFAULT_MAX_WORDS, dialect: str = "neutro",
         check_geo: bool = False):
    """Devuelve una lista de issues (vacía = pasa).

    `check_geo` es opt-in para no romper usos que linteen fragmentos; el CLI lo
    activa por defecto porque ahí se lintea la descripción completa.
    """
    issues = []
    plain = strip_html(text)
    low = plain.lower()

    if "—" in plain or "–" in plain:
        issues.append("em-dash detectado (AI tell): reemplazar por coma/dos puntos")

    n = len(plain.split())
    if n < min_words:
        issues.append(f"texto demasiado corto ({n} palabras, mínimo {min_words})")
    if n > max_words:
        issues.append(f"texto demasiado largo ({n} palabras, máximo {max_words})")

    if required_keywords and not any(k.lower() in low for k in required_keywords):
        issues.append(f"falta al menos una keyword requerida: {required_keywords}")

    for hit in _hits(low, FORBIDDEN_MATERIAL):
        issues.append(f"material prohibido: '{_pretty(hit)}' (el material es acero quirúrgico; "
                      "para el color decir 'acabado dorado/plateado')")
    for hit in _hits(low, FORBIDDEN_HYPE):
        issues.append(f"lujo-vacío/superlativo prohibido: '{_pretty(hit)}'")
    for hit in _hits(low, FORBIDDEN_MEDICAL):
        issues.append(f"claim médico prohibido: '{_pretty(hit)}' (sí se puede decir "
                      "'no irrita' o 'apto para pieles sensibles')")

    if dialect == "neutro":
        for hit in _hits(low, VOSEO):
            issues.append(f"voseo detectado: '{_pretty(hit)}' (el registro es español neutro)")

    if check_geo and "?" not in plain:
        issues.append("falta el bloque GEO: no hay preguntas frecuentes")

    return issues


def main():
    # La consola de Windows no usa UTF-8 por defecto y este linter imprime
    # acentos y ñ; sin esto, quien lo invoque desde otro proceso revienta.
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    ap = argparse.ArgumentParser(description="Linter de descripciones (checklist §9). Texto por stdin.")
    ap.add_argument("--keywords", default="", help="keywords requeridas, separadas por coma")
    ap.add_argument("--min", type=int, default=DEFAULT_MIN_WORDS)
    ap.add_argument("--max", type=int, default=DEFAULT_MAX_WORDS)
    ap.add_argument("--dialect", default="neutro", choices=["neutro", "rioplatense"])
    ap.add_argument("--no-geo", action="store_true", help="no exigir bloque de preguntas frecuentes")
    args = ap.parse_args()

    text = sys.stdin.read()
    keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]
    issues = lint(text, keywords, args.min, args.max, args.dialect, check_geo=not args.no_geo)

    if not issues:
        print("lint OK: sin issues")
        sys.exit(0)
    for issue in issues:
        print(f"- {issue}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
