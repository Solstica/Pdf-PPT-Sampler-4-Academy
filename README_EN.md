# Pdf-PPT-Sampler-4-Academy 1.2 (release candidate)

A deterministic Python slide pipeline and a separate multimodal study protocol. No model API, OCR, extracted text, or generated summaries. Python 3.10+, Windows first; PDF processing is portable to Linux/macOS.

Install with `pip install -e ".[test]"`; Windows Office support: `pip install -e ".[test,windows]"`. Run `academy init my-course`, enter the directory, put source files under raw, then run `academy ingest`, `academy render`, `academy validate`, `academy index`, `academy progress`. Use `academy --workspace PATH COMMAND` from elsewhere. Every command has --help and failures return nonzero.

## V1.2: incremental groups

After binding a remote, run trans PP or trans PP --group Notes -pre 1. Group selects a raw subfolder and its descendants; dot selects root files only. All sources are registered, but new documents outside the chosen group are deferred. Group-specific presets persist; the most specific folder wins. New nested documents use sources/by-group/<folder>/<ID>/, legacy and moved documents retain their published URL. GROUPS.md links all published documents by their current source group. Unique hash-based moves preserve IDs; ambiguous moves and changed sources are rejected.

## trans quick start

Install Git, GitHub CLI and pipx; run gh auth login. Install this repository with pipx (Windows Office support: pipx install ".[windows]"). Reopen your shell to refresh PATH.

~~~bash
trans "/path/to/raw" CM -pre 3
trans CM git@github.com:OWNER/PRIVATE-COURSE.git
trans --list
trans --show CM
~~~

Registration renames source documents in place, preserves original names and hashes, and persists the local course code. Publication mirrors originals locally, renders and validates pages, preserves existing remote review files, and commits/pushes only allowlisted files to a verified private repository. Presets 1–5: 1920/Q90, 1600/Q80, 1280/Q75, 1024/Q70, 800/Q60. See the Chinese README for dry-run, relocation, recovery, disk space and compatibility details.

Configure groups, unique uppercase prefixes, optional teachers, file order, exam modes and quality presets in course.yaml. Original names, paths and bytes are untouched. IDs persist across appends and detectable moves; duplicates are reported, never deleted. Changed content requires `ingest --new-version`; retain archived originals for old references. IDs are not chapter numbers.

Presets: compact 1024/Q70, balanced 1280/Q75, detailed 1920/Q90, inspection 2560/Q95. Notes default to inspection. Override with `render --document L01 --pages 3-8 --preset inspection`, or --input, --group, --long-edge, --quality, --format webp/png/jpg/jpeg, --force. WebP method 6, opaque RGB white background, original aspect ratio/order, blank pages included; no cropping, joining, enhancement or watermark. PNG ignores quality.

Manifests record source identities and per-page IDs, paths, dimensions, sizes, hashes, status and actual rendering/converter parameters. Index JSON and linked Markdown provide visual access. Cache validates actual images; per-page checkpoints support recovery. `academy batch --document L01 --size 15` writes ordered reading lists; it does not claim reading completion.

Follow AGENTS.md and protocols. Actual image inspection is mandatory. Reading states start pending and are only explicitly updated by user/AI: `academy progress --page L01-P003 --state read`. Unclear content must not be guessed. Preserve evidence, distinguish teacher requirements from user highlights and AI inference, and cite stable page IDs.

`academy print --pages L01-P003,L02-P006` copies original PDF objects across documents in list order. `--list review/PRINT_LIST.md` or a JSON array is supported, including repetitions. Never prints from compressed images.

PPT/PPTX uses Windows PowerPoint first, LibreOffice fallback (soffice on PATH), otherwise asks for manual PDF export. Hidden-slide/page-count and font review warnings are recorded. Office fidelity needs visual checks.

Keep private course workspaces separate from the public tooling repo. raw/sources/review/print/reports and source maps are ignored by default. The legacy academy command never pushes automatically. Explicit trans publication is the exception and verifies PRIVATE visibility. Before opting into private course sync, verify repository visibility and inspect staged data yourself.

Run `python -m pytest -q`. Generate a synthetic demo with `python examples/synthetic_demo.py OUTPUT`. See TEST_RESULTS.md, docs/MIGRATION.md and docs/LIMITATIONS.md. No real teaching material is shipped.
