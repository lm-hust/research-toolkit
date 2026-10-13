# Scopus web rules

## Entry and approved subset

Open [Scopus](https://www.scopus.com/) → **Advanced Search**; paste the complete fielded query, not an API parameter. Authenticated navigation and parser acceptance have not been tested.

Default broad text field: `TITLE-ABS-KEY(...)`. It searches title, abstract and keywords. KEY includes **AUTHKEY, INDEXTERMS, TRADENAME and CHEMNAME**: author keywords, controlled indexed terms, trade names and chemical names. It is not author-keywords-only, and not equivalent to WoS Topic or IEEE All Metadata.

Use explicit uppercase `OR` for alternatives, `AND` for co-required concepts and parentheses around concept groups. For a confirmed narrower field, `TITLE(...)`, `ABS(...)`, `TITLE-ABS(...)` and `AUTHKEY(...)` are documented. Default rendering needs only fielded Boolean groups and straight double-quoted phrases.

**Phrase semantics:** `"..."` is a **loose/approximate** phrase, not a universal exact-match promise. Exact `{...}` preserves included stop words, spaces and punctuation and treats wildcard characters literally. Use exact braces only for a confirmed restriction with its losses explained; loose phrases are the default.

Optional verified `*` is multi-character; it must occur with a word, not alone. It works within loose quoted phrases. Double truncation such as `*daylight*` is disallowed. Avoid wildcard/proximity combinations unless their needed rules are independently established.

## Primary rules and verification

Reviewed original official bodies on **2026-10-12 UTC**, transferred from the [bounded research report](https://github.com/lm-hust/research-toolkit/blob/d435e2ca93260875a443443e8441b344f35f2992/docs/research/cimo-platform-syntax.md); this is source verification, not a fresh fetch or live parser test by fact2query.

| Original source / locator | Verified rule |
| --- | --- |
| Elsevier, [How can I best use the Advanced search?](https://www.elsevier.support/scopus/answer/how-can-i-best-use-the-advanced-search), introduction, Operators, Field codes and textual/keyword field tables (displayed update 2026-08-24) | Advanced Search accepts field codes; field spellings above; `OR`, `AND`, `AND NOT`; precedence OR → W/n, PRE/n → AND → AND NOT, parentheses first. Explicit grouping avoids relying on that precedence. |
| Same source, phrases | “Use straight double quotation marks to search for a loose or approximate phrase.” Braces are exact; wildcard characters in braces are literal. |
| Elsevier, [Search Tips: What makes a Scopus search complex?](https://www.elsevier.support/scopus/answer/search-tips-what-makes-a-scopus-search-complex), limits and Don'ts (displayed update 2025-10-20) | “NO EXPLICIT limit on the length of queries or the number of boolean operators”; complex strings may still be unreliable/time out. Double truncation is disallowed; proximity with an exact-phrase operand is discouraged. |

`W/n` and `PRE/n` are documented as within/preceding but are **outside the initial rendering subset**. Basic documentation does not establish all distances, operands or nesting. Exclusion `AND NOT` is documented but not a default scope restriction.

## Unknowns and local checks

Unknown: `?` definition and comprehensive wildcard prefix/position rules; exact proximity counting/bounds/nesting; general parser ceilings; current authenticated navigation; web/API parity. Do not turn “no explicit limit” into a guarantee of unlimited accepted complexity.

Check locally: correct hyphenated field spelling; parentheses around alternatives and co-required groups; paired ASCII quotes; loose versus exact phrase choice matches the confirmed intent; any optional wildcard follows the subset above. Recheck original rules before new syntax or on official changes/parser errors.

Source-rule state: verified bounded official subset, dated above. Local-check state belongs to the actual six-query artifact. Parser and seed states: **untested unless separately executed and recorded**.
