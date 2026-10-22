#!/bin/sh
set -eu
SUBMISSION_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
BUILD_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/iscmi-va280.XXXXXX")
trap 'rm -rf "$BUILD_ROOT"' EXIT HUP INT TERM
cp "$SUBMISSION_ROOT/manuscript.tex" "$SUBMISSION_ROOT/IEEEtran.cls" "$BUILD_ROOT/"
cp "$SUBMISSION_ROOT/fig01.pdf" "$SUBMISSION_ROOT/fig02.pdf" "$SUBMISSION_ROOT/fig03.pdf" "$BUILD_ROOT/"
cd "$BUILD_ROOT"
tectonic --keep-logs manuscript.tex
pages=$(pdfinfo manuscript.pdf | awk '/^Pages:/ {print $2}')
if [ "$pages" != 5 ]; then
  echo "Expected five pages including references; build has $pages." >&2
  if [ -n "${ISCMI_QA_DIR:-}" ]; then
    mkdir -p "$ISCMI_QA_DIR"
    cp manuscript.pdf manuscript.log "$ISCMI_QA_DIR/"
  fi
  exit 1
fi
cp manuscript.pdf "$SUBMISSION_ROOT/VA280.pdf"
if [ -n "${ISCMI_QA_DIR:-}" ]; then
  mkdir -p "$ISCMI_QA_DIR"
  cp manuscript.log "$ISCMI_QA_DIR/"
fi
echo "Built $SUBMISSION_ROOT/VA280.pdf (5 pages)"
