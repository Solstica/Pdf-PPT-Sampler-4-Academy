# Known limitations

- No concurrent writers or database locking. Use one command at a time. PDF render parallelism is not implemented.
- Source PDFs must remain locally available for full validation and vector printing. Explicit new versions do not archive original bytes; retain old originals yourself. Identical duplicates moved simultaneously can be ambiguous; review path history.
- PowerPoint/LibreOffice export requires local software. Font substitution cannot be reliably detected automatically; warnings require visual review. Animations and live objects become static PDF content.
- Windows is the executed test platform; Linux/macOS code paths use portable Python but require platform CI/Office testing before claiming full platform validation.
- PDF annotations depend on the PDF renderer; external resources/fonts and encrypted or malformed PDFs can fail. Errors are reported; no silent OCR fallback.
- AI protocols are instructions, not an automated reading engine. A user may mark a page read; software cannot prove human/AI visual inspection occurred.
- Markdown print lists extract every syntactically matching page ID, including duplicates. Keep explanatory examples outside the actual list.
- Source maps and course files can be sensitive even with ASCII identifiers. Defaults ignore them, but users can override Git ignore rules; inspect staged files before publishing.

## V1.1 release candidate

- trans serializes operations using a per-user OS lock, retains a hash-verified local raw mirror, and uses hard-link/unlink with a recoverable rename journal. Filesystems lacking hard links cannot rename via trans; use a supported volume. Interrupted operations roll forward on retry. Do not edit sources while commands run.
- Changed original content is rejected; restore the original and add the revision separately. Course remote rebinding and legacy registry migration require manual inspection; no automatic destructive migration.
- A clean dedicated publication checkout is required. Failed pushes retain commits; divergent remote history or uncommitted local changes require manual recovery. No force-push.
- GitHub CLI authentication and Git access are both required. The privacy check fails closed. Real private GitHub push, Office export and global Windows Git Bash PATH need local validation; automated tests use synthetic PDFs and local Git remotes.

## V1.2 candidate

- Group synchronization registers all newly found raw files, but publishes only the selected subtree and retains all previously published documents. Full validation still checks all included original sources. The complete raw directory must remain accessible.
- New nested documents use sources/by-group; existing published paths remain stable even after moving between groups. GROUPS.md is the authoritative current grouping. Manual source renames are tracked by unique hash but not renamed again. Ambiguous duplicate moves fail closed.
- Course-specific group presets persist, with longest matching path taking precedence. Full sync reapplies these presets. Group name matching uses actual folder spelling and case.
- No real private remote V1.2 group sync or Office export has been tested; CI uses synthetic PDFs and local remotes.
