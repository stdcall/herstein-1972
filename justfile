# Machine settings such as LEAN_MATHLIB may be kept in a local .env file.
set dotenv-load

python := "uv run --locked python"

default: build

# Validated PDF, with cached no-op when source files have not changed.
build:
    {{python}} scripts/project.py build

# CI gate: format, lint, PDF links/layout, tests, corrections, no-notes PDF.
check:
    {{python}} scripts/project.py check

# Formatter check, source rules and the evaluated document (T000-T099).
lint:
    {{python}} scripts/project.py lint

# Format the Typst sources in place (Typstyle with the Tinymist settings).
fmt:
    {{python}} scripts/project.py fmt

# Unit tests: corrections schema, labels, bibliography, numbering, lint rules.
test:
    {{python}} scripts/project.py test

# The reader's list of corrections: build/herstein-1972.corrections.pdf
corrections:
    {{python}} scripts/project.py corrections

# The book without editorial notes: build/herstein-1972.no-notes.pdf
build-no-notes:
    {{python}} scripts/project.py build-no-notes

# Remove build/ and the build cache (`cache` in config/project.json).
clean:
    {{python}} scripts/project.py clean

# Each script is plain Python importing sage.all; see checks/README.md.

# Exact Sage checks: every checks/sage/*.sage and *.py with `sage -python`.
check-sage:
    #!/usr/bin/env bash
    set -euo pipefail
    shopt -s nullglob
    scripts=(checks/sage/*.sage checks/sage/*.py)
    if [ ${#scripts[@]} -eq 0 ]; then
        echo "No Sage checks yet (checks/sage/)."
        exit 0
    fi
    for script in "${scripts[@]}"; do
        echo "== $script"
        sage -python "$script"
    done

# Lean checks of checks/lean-proofs.json: compile, no warnings, standard
# axioms. With LEAN_MATHLIB set, against a prebuilt mathlib checkout of the
# pinned commit (nothing is built or fetched); otherwise in checks/lean after
# `lake build` there, as CI does.
check-lean:
    {{python}} checks/lean/check_axioms.py

# Advisory Russian prose check (Vale with typst2vast).
check-prose:
    {{python}} scripts/check_prose.py
