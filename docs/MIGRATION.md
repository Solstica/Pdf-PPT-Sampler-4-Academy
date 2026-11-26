# Migration

Reference: Solstica/Computational-Material, commit b9a24e3. Read README, test reports, tools, test scripts and index/manifest schemas before migration. Local review contained only .gitkeep placeholders, so no study text or progress was imported.

Reused the PyMuPDF full-page pixmap → Pillow RGB/resample/encode pipeline, temporary PowerPoint/LibreOffice PDF context, SHA256 source registry concept, atomic JSON writes, per-page parameters, original page IDs and insert_pdf vector printing approach. Refactored into independent modules with editable packaging and CLI.

Changed original renaming into non-mutating registration; removed fixed teacher names; added configurable groups/presets, explicit new versions, move detection, actual-image hash cache checks, per-page checkpoints, batch lists, progress/reference validation, cross-document ordered printing, private-workspace defaults and AI protocols. No real source files, images, registry records, personal metadata, notes or exam content were copied. Synthetic fixture only.
