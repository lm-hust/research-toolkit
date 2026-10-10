"""
src/research_toolkit/notebook/
Gemini Notebook integration on the notebooklm-py Python API (ADR-0008).

- `client`: the client factory `open_client()` (the single test-injection seam) and the
  Protocol describing the slice of notebooklm-py we call.
- `titles`: the `[<Zotero key>] <title>` Notebook Source title convention.
- `resolve`: pick or create the target notebook from a title or UUID.
- `sync`: incremental Zotero collection -> Gemini Notebook sync.
"""
