# Chengzhu v2 Stable Promotion Evidence Gate

- Status: **NO_GO**
- Policy: **v2.0-R1-stable-promotion-1**
- Failed checks: **29 / 37**
- V2_STABLE_RELEASE: **FALSE**
- PMF_PROVEN: **FALSE**

| Check | Pass | Actual | Required |
| --- | :---: | --- | --- |
| human_report_evidence_type | YES | HUMAN_LABELED_CONVERSATION_EVAL | HUMAN_LABELED_CONVERSATION_EVAL |
| human_labels_available | NO | False | True |
| pilot_manifest_type | YES | AUTHORIZED_REAL_CONVERSATION_PILOT | AUTHORIZED_REAL_CONVERSATION_PILOT |
| attestation:AUTHORIZED_REAL_USE | YES | True | True |
| attestation:NO_SYNTHETIC_ROWS_IN_HUMAN_EVAL | YES | True | True |
| attestation:RAW_LABELS_KEPT_LOCAL | YES | True | True |
| attestation:NO_CRITICAL_PRIVACY_INCIDENT | YES | True | True |
| attestation:NO_KNOWN_DATA_LOSS | YES | True | True |
| profile:PROJECT_SYNC:distinct_users | NO | 0 | >=5 |
| profile:PROJECT_SYNC:sessions | NO | 0 | >=20 |
| profile:PROJECT_SYNC:cross_session_spaces | NO | 0 | >=3 |
| profile:DESIGN_REVIEW:distinct_users | NO | 0 | >=5 |
| profile:DESIGN_REVIEW:sessions | NO | 0 | >=20 |
| profile:DESIGN_REVIEW:cross_session_spaces | NO | 0 | >=3 |
| metric:opportunity_precision:sample_size | NO | 0 | >=30 |
| metric:opportunity_precision:threshold | NO | None | gte 0.8 |
| metric:interruption_regret:sample_size | NO | 0 | >=30 |
| metric:interruption_regret:threshold | NO | None | lte 0.15 |
| metric:source_attribution_accuracy:sample_size | NO | 0 | >=30 |
| metric:source_attribution_accuracy:threshold | NO | None | gte 0.95 |
| metric:recall_precision:sample_size | NO | 0 | >=20 |
| metric:recall_precision:threshold | NO | None | gte 0.9 |
| metric:useful_silence_rate:sample_size | NO | 0 | >=30 |
| metric:useful_silence_rate:threshold | NO | None | gte 0.8 |
| metric:direct_question_precision:sample_size | NO | 0 | >=20 |
| metric:direct_question_precision:threshold | NO | None | gte 0.9 |
| metric:direct_question_recall:sample_size | NO | 0 | >=20 |
| metric:direct_question_recall:threshold | NO | None | gte 0.85 |
| metric:decision_commitment_state_precision:sample_size | NO | 0 | >=30 |
| metric:decision_commitment_state_precision:threshold | NO | None | gte 0.9 |
| metric:continue_writeback_accuracy:sample_size | NO | 0 | >=20 |
| metric:continue_writeback_accuracy:threshold | NO | None | gte 0.95 |
| metric:mean_cognitive_load_delta:sample_size | NO | 0 | >=15 |
| metric:mean_cognitive_load_delta:threshold | NO | None | lte -0.25 |
| metric:space_reuse_intent_rate:sample_size | NO | 0 | >=15 |
| metric:space_reuse_intent_rate:threshold | NO | None | gte 0.7 |
| critical_incidents_zero | YES | 0 | 0 |

> Passing this gate means only that product evidence is strong enough to enter a separate stable release review.
