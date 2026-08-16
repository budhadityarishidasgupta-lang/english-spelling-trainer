# Kiarolabs Verbal Reasoning Sprint MVP

## Scope

Isolated Verbal Reasoning learning domain. It uses only `vr_*` tables and shares only the existing platform database infrastructure.

## Student MVP

- Basic / Intermediate / Mastery
- 15 fixed paper slots per level
- exactly 35 questions required before a paper can start
- 30-minute server-time-based timer
- previous / next / question navigator
- draft answers persisted separately from attempt history
- manual submit or automatic timeout submit
- append-only final attempts
- score and unanswered count
- per-question answer review and authored explanation

Run:

```bash
streamlit run verbal_reasoning_app/student_app.py
```

## Admin MVP

Run:

```bash
streamlit run verbal_reasoning_app/admin_app.py
```

The CSV importer is idempotent and never deletes learning history. It accepts common aliases for these canonical fields:

- level
- paper_number
- question_number
- question_code
- question_type
- question_text
- option_a
- option_b
- option_c
- option_d
- correct_option
- explanation

Allowed levels: `BASIC`, `INTERMEDIATE`, `MASTERY`.

## Production boundary

The MVP currently uses a temporary `student_id=1` bridge in the student UI. Before production deployment, the existing authenticated platform `user_id` must be passed into the VR app. Do not create a VR-specific user table.

## Data safety

- no reads/writes to spelling, maths, synonym, grammar, or NVR tables
- all SQL is inside `verbal_reasoning_app/repository/`
- final attempts are append-only
- draft answer changes are stored in `vr_session_answers`, not attempts
- CSV re-upload does not delete papers, sessions, or attempts
