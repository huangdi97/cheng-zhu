# Chengzhu Route Eval Report

| Metric | Value |
| --- | --- |
| route_accuracy | 1.0 |
| type_accuracy | 0.9 |
| unsupported_claim_rate (blocked) | 1.0 |
| fact_precision | 1.0 |
| total cases | 10 |

## Per category

| Category | Matched / Total |
| --- | --- |
| resume_outside_knowledge | 1 / 1 |
| system_design | 1 / 1 |
| coding | 1 / 1 |
| behavioral | 1 / 1 |
| contradiction | 1 / 1 |
| hypothetical | 1 / 1 |
| company | 1 / 1 |
| mixed_language | 1 / 1 |
| topic_reset | 1 / 1 |
| long_session | 1 / 1 |

## Cases

- [PASS] resume-outside-transformer: expected=KNOWLEDGE actual=KNOWLEDGE type=KNOWLEDGE
- [PASS] system-design-short-video: expected=SYSTEM_DESIGN actual=SYSTEM_DESIGN type=SYSTEM_DESIGN
- [PASS] coding-lru: expected=CODING actual=CODING type=CODING
- [PASS] behavioral-cross-team: expected=BEHAVIORAL actual=BEHAVIORAL type=BEHAVIORAL
- [PASS] contradiction-redis-cluster: expected=EXPERIENCE_BOUNDARY actual=EXPERIENCE_BOUNDARY_KNOWLEDGE type=EXPERIENCE
- [PASS] hypothetical-traffic-100x: expected=HYPOTHETICAL actual=HYPOTHETICAL type=HYPOTHETICAL
- [PASS] company-knowledge: expected=KNOWLEDGE actual=KNOWLEDGE type=KNOWLEDGE
- [PASS] mixed-language-rag: expected=EXPERIENCE_KNOWLEDGE actual=EXPERIENCE type=EXPERIENCE
- [PASS] topic-reset-os: expected=KNOWLEDGE actual=KNOWLEDGE type=KNOWLEDGE
- [PASS] long-session-accumulation: expected=EXPERIENCE_KNOWLEDGE actual=EXPERIENCE_KNOWLEDGE type=FOLLOW_UP