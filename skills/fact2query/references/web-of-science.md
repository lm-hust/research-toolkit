# Web of Science Core Collection web rules

## Entry and approved subset

Open [Web of Science](https://www.webofscience.com/), select **Core Collection → Advanced Search → Query Builder**. Paste field-tag syntax there, not into a Fielded Search row. Authenticated navigation and parser acceptance have not been tested.

Default `TS=(...)` (Topic) searches **Title, Abstract, Author Keywords and Keywords Plus**. Keywords Plus adds coverage beyond author keywords; TS is not equivalent to Scopus TITLE-ABS-KEY or IEEE All Metadata. Confirmed field restrictions may use `TI=(...)`, `AB=(...)` or `AK=(...)`; `KP=(...)` is documented but not a default restriction.

Use explicit uppercase `OR`, `AND` and parentheses; operators are case-insensitive, but explicit grouping avoids precedence dependence. Default rendering needs only these groups, supported tags and straight double-quoted phrases.

**Phrase semantics:** quotes find exact phrases and turn off lemmatization/internal synonym expansion. Thus `"soil drainage"` does not find “drainage of soil”; quoting `"mouse"` does not expand to “mice”. Exact Search is off by default for unquoted terms, which use stemming/lemmatization. Record UI setting if actually tested; do not invent it.

Optional wildcards are Latin-alphabet only: `*` zero/many characters, `?` one, `$` zero/one. Topic/Title right truncation needs at least three preceding characters; left truncation needs at least three following characters; internal wildcards are documented. Wildcards turn off lemmatization. No wildcard after `/ @ #` or `. , : ; !`, nor in publication-year search. Prefer explicit variants when expansion behavior matters.

## Primary rules and verification

Reviewed original official bodies on **2026-10-12 UTC**, via ordinary public Help Center JSON bodies; canonical original links below. Transferred from the [bounded research report](https://github.com/lm-hust/research-toolkit/blob/d435e2ca93260875a443443e8441b344f35f2992/docs/research/cimo-platform-syntax.md), not a new fetch or live test. The retrieval API served **web help**, not bibliographic searches or web/API parity evidence.

| Original official article / locator | Verified rule |
| --- | --- |
| [Core Collection Advanced Search Field Tags](https://webofscience.zendesk.com/hc/en-us/articles/26916347018257-Web-of-Science-Core-Collection-Advanced-Search-Field-Tags), TS/TI/AB/AK/KP/ALL entries | Field tags above; TS includes Keywords Plus. `ALL=` is the command tag, not the “AF” descriptive label in other articles. |
| [Advanced Search Query Builder](https://webofscience.zendesk.com/hc/en-us/articles/20130361503249-Advanced-Search-Query-Builder), opening and Exact Search | Query Builder from Advanced Search, accepts field tags; Exact Search off by default; quotes for exact phrases. |
| [Advanced Search – Fielded Search](https://webofscience.zendesk.com/hc/en-us/articles/20129792747921-Advanced-Search-Fielded-Search), opening | Structured field rows are a different entry from pasted Query Builder syntax. |
| [Search Operators](https://webofscience.zendesk.com/hc/en-us/articles/20016122409105-Search-Operators), operators and precedence | AND/OR/NOT/NEAR/SAME; parentheses first, then NEAR/x → SAME → NOT → AND → OR. |
| [Search Rules](https://webofscience.zendesk.com/hc/en-us/articles/25350084904721-Search-Rules), Exact Search, Wildcards, limits | Quoting and wildcard rules above; lemmatization turns off above an unspecified English-term threshold. |
| [Core Collection Search Fields](https://webofscience.zendesk.com/hc/en-us/articles/26916258216209-Web-of-Science-Core-Collection-Search-Fields), Topic and All Fields | TS phrases; All Fields does not support NEAR or SAME. |

## Conflicts, unknowns and local checks

**Preserve the All Fields conflict:** Search Operators says **49** Boolean/proximity operators; Search Rules says **100**. Both published bodies exempt other fields from operator-count limits. Neither number is selected as fact2query's cap; initial output does not use ALL to evade or resolve this conflict.

NEAR/x (maximum separating words; bare NEAR defaults 15; NEAR/0 adjacent) and SAME (same Address) are documented but **outside the initial rendering subset**. An AND-containing NEAR operand is documented invalid; that does not establish every cross-clause nesting combination. NOT is documented, not a default exclusion.

Unknown: numeric term threshold for lemmatization, general character/nesting ceilings, wildcard expansion ceiling, maximum proximity distance/all operand combinations, detailed punctuation normalization and web/API parity. An operator-count exemption is not guaranteed unlimited complexity.

Check locally: correct collection and Query Builder label; TS/TI/AB/AK spelling and `=`; grouped OR/AND; paired ASCII quotes; exact phrases' lost variants explained; wildcard rules if used. Recheck original rules before new syntax or on official changes/parser errors.

Source-rule state: verified bounded official subset, dated above. Local checks attach to the rendered artifact; parser and seed states are **untested unless separately executed and recorded**.
