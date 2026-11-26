# Known limitations

- No concurrent writers or database locking. Use one command at a time. PDF render parallelism is not implemented.
- Source PDFs must remain locally available for full validation and vector printing. Explicit new versions do not archive original bytes; retain old originals yourself. Identical duplicates moved simultaneously can be ambiguous; review path history.
- PowerPoint/LibreOffice export requires local software. Font substitution cannot be reliably detected automatically; warnings require visual review. Animations and live objects become static PDF content.
- Windows is the executed test platform; Linux/macOS code paths use portable Python but require platform CI/Office testing before claiming full platform validation.
- PDF annotations depend on the PDF renderer; external resources/fonts and encrypted or malformed PDFs can fail. Errors are reported; no silent OCR fallback.
- AI protocols are instructions, not an automated reading engine. A user may mark a page read; software cannot prove human/AI visual inspection occurred.
- Markdown print lists extract every syntactically matching page ID, including duplicates. Keep explanatory examples outside the actual list.
- Source maps and course files can be sensitive even with ASCII identifiers. Defaults ignore them, but users can override Git ignore rules; inspect staged files before publishing.
