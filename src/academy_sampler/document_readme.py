"""Human-readable immutable source identity for each published document."""
import json
from urllib.parse import quote


def render_document_readme(document, first_commit_at):
    # JSON string literals preserve exact names, including Markdown punctuation,
    # and escape newlines/control characters from source filenames.
    def literal(value):
        return json.dumps(value, ensure_ascii=False)

    ident = document["document_id"]
    first = first_commit_at or "unknown (Git history unavailable)"
    fields = {
        "document_id": ident,
        "original_filename": document["original_filename"],
        "original_relative_path": document["original_path"],
        "first_archive_commit_at_utc": first,
        "total_pages": document["total_pages"],
        "source_sha256": document["source_sha256"],
    }
    # Indented code block prevents filename text from being parsed as Markdown.
    metadata = "\n".join("    " + key + ": " + literal(value) for key, value in fields.items())
    return (
        f"# {ident} — Source metadata / 原始资料信息\n\n"
        "Original filename / 原始文件名 and first archive time / 首次归档时间 (UTC):\n\n"
        + metadata + "\n\n"
        "The time is the Git commit timestamp when the manifest first entered the archive, "
        "not the GitHub server receipt time. For older documents it is recovered from Git history. "
        "Repeated syncs do not change this record.\n\n"
        "时间取 manifest 首次进入归档的 Git 提交时间（UTC），并非 GitHub 服务器接收时间。"
        "旧资料从 Git 历史补录；重复同步不会刷新此记录。\n\n"
        f"Page IDs / 页面引用: {ident}-P001 … {ident}-P{document['total_pages']:03d}.\n\n"
        "[manifest.json](manifest.json) contains current page paths, parameters and image hashes. "
        "Use the page images for content review; this README contains source metadata only.\n"
    )
