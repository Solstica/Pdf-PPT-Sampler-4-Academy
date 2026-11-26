# V1.0 acceptance

Executed on Windows, Python 3.13, with editable installation `pip install -e ".[test,windows]"`. Synthetic sources only; no real reference-course content was imported.

Five pytest scenarios cover: Chinese/English text, superscript formula, vector lines/circles, landscape/portrait/square pages and blank page; recursive Unicode/space paths; identical names/content; stable IDs and manual teaching order; move/rename detection and explicit changed-content versions; source bytes unchanged; valid cache skip; inspection rerender preserving other pages; image corruption detection and repair; per-page failure checkpoint and resume; PNG/JPEG; ordered cross-document vector copying including repeated pages; all reading states and reason checks; invalid references; CLI help/error codes; Git ignore rules for original/rendered/printing/review/source map data.

PDF/CLI synthetic demo: init → ingest → render → validate. New progress remains pending. The test vector output contains original drawing/font objects and no rasterized replacement pages.

Office export: PowerPoint and LibreOffice actual export NOT TESTED for this release. Windows code is available; this report does not claim conversion fidelity. Linux/macOS execution also NOT TESTED; see docs/LIMITATIONS.md.

During test setup, the host system temporary directory denied access; acceptance used an isolated project `.tests/` directory with `pytest --basetemp .tests/run5`. This environment issue did not affect source handling.



最终结果：5 passed in 22.61s。Editable install、wheel 构建及初始化资源打包检查通过；合成 demo 的 2 份 PDF / 8 页 CLI 完整流程通过。
