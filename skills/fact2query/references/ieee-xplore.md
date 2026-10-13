# IEEE Xplore web rules

## Entry and approved historical subset

Open [IEEE Xplore](https://ieeexplore.ieee.org/) → **Advanced Search → Command Search**. This entry is documented in the 2021 tutorial, not verified current authenticated navigation. Paste the Boolean string into Command Search, not an API or structured Advanced Search row.

**Historical official basis; current platform untested.** Initial rendering uses default **All Metadata**, explicit uppercase `AND`/`OR`, parenthesized groups and straight double-quoted phrases. Emit **no field prefixes**. The tutorial establishes historical field UI labels, not command serialization such as `"Document Title":`.

With no field selected, the tutorial says keywords search All Metadata: article title, author names, publication title, index terms, abstract and other data fields (non-exhaustive). This is broader than title/abstract/author-keywords-only. Its dropdown distinguishes **All Metadata**, **Full Text & Metadata**, and **Full Text Only**. Do not conflate them or claim an exhaustive current coverage definition.

The historical tutorial describes default single-word stemming and quotes as exact phrases that disable auto-stemming. Use explicit English variants when needed; do not promise present-day expansion/tokenization behavior. Initial output avoids wildcards, proximity and NOT because full needed rules/currentness are not established.

## Original evidence and verification

Reviewed original captions and screen frames on **2026-10-13 UTC**; transferred from the [video evidence report](https://github.com/lm-hust/research-toolkit/blob/ee753687fa9070a3ad313a7ec138bcc124554021/docs/research/cimo-ieee-video-evidence.md), not a fresh video fetch or current parser test. Captions were the supplied non-ASR track; audio agreement was not tested. Screen observations are separate from captions.

Official lineage: [IEEE support/training hub](https://innovate.ieee.org/ieee-xplore-support-and-training/) links the [IEEE Xplore channel](https://www.youtube.com/c/ieeexploredigitallibrary), whose canonical channel ID matches the video's publisher. Original video: [Command Search in IEEE Xplore Feb 2021](https://www.youtube.com/watch?v=fCGjZfxu4e4), IEEE Xplore, published **2021-02-08**, 242 seconds. The hub links the channel, not the individual video.

| Original timestamp / evidence | Verified historical fact |
| --- | --- |
| [00:04–00:19 captions](https://www.youtube.com/watch?v=fCGjZfxu4e4&t=4s) | Command Search: Advanced Search below Global Search, second tab. |
| [00:19–00:45 captions](https://www.youtube.com/watch?v=fCGjZfxu4e4&t=19s) | Parentheses group/prioritize expressions. “up to 20 words in each search clause.” |
| [00:47–01:14 captions](https://www.youtube.com/watch?v=fCGjZfxu4e4&t=47s) and [00:56 screen](https://www.youtube.com/watch?v=fCGjZfxu4e4&t=56s) | No field selected → All Metadata; non-exhaustive composition above. Screen distinguishes metadata/fulltext choices and named fields, not field-prefix syntax. |
| [01:14–01:36 captions](https://www.youtube.com/watch?v=fCGjZfxu4e4&t=74s) and 01:15/01:25 screen | Operators must be capitals; implicit AND described. Initial output uses explicit operators. |
| [02:13–02:43 captions](https://www.youtube.com/watch?v=fCGjZfxu4e4&t=133s) | Default stemming; exact quoted phrases disable it. |
| [03:30 screen](https://www.youtube.com/watch?v=fCGjZfxu4e4&t=210s) | Actual example `(touchscreen OR "touch screen*") NEAR/5 (haptic OR kinesthetic)` verifies grouped OR and quoted phrase syntax historically; not a query submitted by this implementation. |

## Limits and unknowns

Do not encode a current hard cap. At [00:47 screen](https://www.youtube.com/watch?v=fCGjZfxu4e4&t=47s), text says “maximum of 20 search terms”; captions above say 20 words **per clause**. Counting units are unresolved. At [02:43–03:10 captions](https://www.youtube.com/watch?v=fCGjZfxu4e4&t=163s), historical guidance says six wildcards/string, `*` any/no characters, `?` one, words “over 3 characters” (author minimum 2). This does not establish current limits, all positions or prefix counting. Unverified 25-term/10-wildcard leads are not adopted either.

NEAR/ONEAR, named field labels and wildcard examples exist historically, but exact field serialization, NOT operands/precedence, all nesting/operand/distance rules, current ceilings, punctuation/stop-word handling, exhaustive coverage and web/API parity remain unknown. Current production help was not readable in the research; official hubs and university summaries alone do not resolve these gaps.

Check locally: Command Search label; no prefixes; explicit uppercase AND/OR; grouped relationships; paired straight phrase quotes; no unsupported wildcard/proximity/exclusion or current-limit claim. Recheck primary evidence before extending the subset or on official changes/parser errors.

Source-rule state: historical official subset, reviewed date above. Local checks attach to the actual artifact. Parser and seed states: **untested unless separately executed and recorded**, even after local checks pass.
