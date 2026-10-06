# Research Report: NotebookLM Community Python Clients & NotebookLMGateway Architecture (Issue #2)

**Target Issue:** lm-hust/research-toolkit#2  
**Context Alignment:** Aligned with domain language in `CONTEXT.md` (`NotebookLMGateway`, `NotebookSource`, `DistilledEvidence`, `FulltextCheckpoint`).

---

## 1. Landscape Comparison of Community Projects

| Project | Language & Transport | Core Strengths | Weaknesses / Limitations | Recommendation for `research-toolkit` |
| :--- | :--- | :--- | :--- | :--- |
| **`teng-lin/notebooklm-py`** | Python (Async)<br>• Web: `batchexecute` RPC<br>• Android: Bearer gRPC | • **Most mature & feature-complete**<br>• Dual backend (Web cookies or Android master token)<br>• Typed dataclasses (`AskResult`, `ChatReference`)<br>• Golden payload tests running daily in CI<br>• Preserves citation offsets & grounded source text | Reverse-engineered private Google endpoints; subject to RPC identifier rotations | **Primary Engine Recommended** |
| **`ishandutta2007/notebooklm-api`** | Python<br>• Web reverse-engineered endpoints | • Python SDK + CLI + MCP server<br>• Artifact generation (audio, slides, quizzes) | • Less isolated transport layer<br>• Slower adaptation to Google internal schema drifts than `notebooklm-py` | Secondary alternative |
| **`jacob-bd/notebooklm-mcp-cli`** | Python<br>• Web endpoints + Chrome DevTools Protocol | • Chrome DevTools Protocol (CDP) for local cookie extraction<br>• CLI aliases and REPL | • Primarily built around CLI/MCP server interactions rather than a standalone library SDK | Useful reference for CDP cookie extraction |
| **`tmc/nlm`** | Go<br>• Web endpoints | • Single binary CLI & MCP server<br>• Direct Chrome cookie file parsing | • Written in Go (not Python); cannot be imported as an internal Python module | Non-Python, unsuitable for direct library import |
| **`gabrielchua/open-notebooklm`** | Python + Llama 3.3 / local LLMs | • Completely open source and local | • **Not a client for Google NotebookLM**; it is an open-source clone replicating the podcast feature | Out of scope for NotebookLM gateway |

**Verdict:** `teng-lin/notebooklm-py` is the clear community front-runner. It provides the exact SDK primitives required for issue #2 (notebook lifecycle, PDF source attachment, and offset-aware citation extraction).

---

## 2. Authentication Mechanics & Session Management

Google does not expose an official public OAuth client for NotebookLM. Reverse-engineered clients authenticate using either Google Web session cookies or Android master tokens:

### A. Web Session Cookies (`backend="web"`)
* **Tokens involved:**
  * Base identity cookies: `SID`, `HSID`, `SSID`, `APISID`, `SAPISID`, `__Secure-1PSID`, `__Secure-3PSID`.
  * Time-sliced security tokens: `__Secure-1PSIDTS`, `__Secure-3PSIDTS` (rotates frequently, often within 2–24 hours).
  * CSRF Token: `SNlM0e` extracted from `WIZ_global_data` in page HTML.
* **Extraction Strategies:**
  1. **Interactive Browser Login:** `notebooklm login` launches Playwright Chromium. The user logs in (supporting 2FA), and Playwright serializes `storage_state.json` (`~/.notebooklm/profiles/default/storage_state.json`).
  2. **Direct Browser Cookie Extraction:** `notebooklm login --browser-cookies chrome` reads and decrypts cookies from local Chrome SQLite database using OS keyrings (via `rookiepy`), requiring no browser launch if already logged in.
  3. **Headless / CI injection:** Read JSON payload from `NOTEBOOKLM_AUTH_JSON` environment variable.
* **Session Lifetime:**
  * Persistent cookies last up to 2 years, but the session is invalidated quickly if `__Secure-1PSIDTS` expires or if Google flags IP/user-agent anomalies.

### B. Android Master Token (`backend="android"`)
* `notebooklm-py` supports logging in via Google Master Token (`notebooklm login --master-token --account you@example.com`), producing `master_token.json`.
* **Mechanism:** Interacts with Google's mobile authentication endpoint (`oauth2:https://www.googleapis.com/auth/experimentsandconfigs`), minting short-lived OAuth bearer tokens for gRPC calls.
* **Session Lifetime:** High durability. Does not suffer from web cookie expiration (`*PSIDTS`).
* **Security Caution:** A Google Master Token is an account-equivalent master secret. The toolkit must enforce strict permissions (`0600`) and recommend dedicated research accounts rather than personal accounts.

---

## 3. Actionable Gateway Architecture

```
                 +------------------------+
                 |   CLI / Staged Flow    |
                 |  (FulltextCheckpoint)  |
                 +-----------+------------+
                             |
                             v
                 +------------------------+
                 |   NotebookLMGateway    | <<Protocol>>
                 +-----------+------------+
                             |
         +-------------------+-------------------+
         |                                       |
         v                                       v
+-----------------------------+     +-------------------------------+
|    NotebookLMPyAdapter      |     |  GeminiGroundingFallback      |
| (Primary: notebooklm-py)    |     |  (Official Google GenAI SDK)  |
+--------------+--------------+     +-------------------------------+
| • Web RPC / Android gRPC    |     | • Official Gemini 1.5 Pro API |
| • Cookie / Master Token     |     | • Direct PDF upload via FileAPI|
| • Automatic Session Check   |     | • Zero reverse-engineering    |
+-----------------------------+     +-------------------------------+
```

1. Core Dependency: `notebooklm-py>=0.8.0`.
2. Gateway Protocol: `NotebookLMGateway` defining `check_health()`, `create_notebook(title)`, `upload_source(notebook_id, pdf_path)`, and `query_sources(notebook_id, prompt)`.
3. Grounding Output: Maps `ChatReference` verbatim quoted spans directly to `DistilledEvidence`.
4. Resilient Fallback: `GeminiGroundingFallbackAdapter` using official Google GenAI File API when internal RPC identifiers rotate.
