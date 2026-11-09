# NEET Sample Question Practice Application

## 1. Purpose and scope

Build a private, reliable web application where a student can select syllabus topics, create a 180-question NEET-style practice paper, take it under timed conditions, submit it, and review a scored result with explanations and study recommendations. Keep a durable history of papers, answers, scores, and topic-level trends.

This is a practice and learning tool. Generated questions should be described as original NEET-style practice, not official NEET questions or predictions. Treat the exam blueprint and syllabus as versioned data: the requested 180-question paper is the initial product requirement, while subject counts, marking rules, duration, and syllabus coverage should be configurable and checked against the applicable official exam materials before use.

## 2. Proposed architecture

Start with a **modular Python backend** exposed as a REST API, a React single-page application, and MongoDB. Keep module boundaries clear so individual backend modules can be extracted into services later if scale or independent deployment needs justify that complexity. For a single student or family deployment, a distributed microservice system would add operational overhead without an immediate benefit.

```mermaid
flowchart LR
  Student[Student] --> UI[React web app]
  UI -->|HTTPS / REST| API[Python API]
  API --> Auth[Identity and session]
  API --> Exam[Exam and attempt modules]
  API --> Results[Scoring and analytics modules]
  API --> Content[Question and syllabus modules]
  Exam --> DB[(MongoDB)]
  Results --> DB
  Content --> DB
  Content --> LLM[OpenAI API]
  LLM --> Orchestrator[Question generation workflow]
  Orchestrator --> Validate[Schema, syllabus, and quality checks]
  Validate --> Review[Question bank / review queue]
  Review --> DB
  API --> Telemetry[Logs, metrics, traces]
  Orchestrator --> LS[LangSmith tracing/evaluation]
```

### Core design choices

- **Deterministic exam delivery and scoring:** The backend selects a fixed paper from approved questions and computes marks from stored answers and a versioned marking scheme. The LLM must not decide scores or grade student responses.
- **Generate before the exam:** Generate and validate questions into a question bank before assembling a student paper. Avoid waiting on model calls while the student is taking an exam. An optional later mode can generate a paper on demand, but should publish it only after all validation succeeds.
- **Structured model output:** Ask the model for a strict question schema, then validate it in application code. Treat model output as untrusted input. Reject malformed questions and do not silently publish them.
- **Versioned content:** Store syllabus version, exam blueprint, prompt/model version, question revision, and marking-scheme revision so old attempts remain reproducible when content changes.
- **Modular monolith first:** Keep API, generation workflow, scoring, and analytics as separately testable modules. Introduce queues/workers and separate services only when workload or operational needs call for them.

## 3. Components and responsibilities

| Component | Responsibilities |
| --- | --- |
| React student application | Sign-in, syllabus/chapter selection, exam instructions, timer, question navigation, answer selection, autosave state, submission, results, explanations, and history/analytics views. |
| Python API | Authentication/authorization, request validation, business rules, API versioning, rate limits, and coordination between modules. FastAPI is a suitable starting framework. |
| Identity and profile module | Student and guardian accounts, secure sessions, preferences, and access control. Start with one student account if that fits the deployment; keep ownership checks on every student record. |
| Syllabus and blueprint module | Manage syllabus editions, subjects, chapters, topics, coverage rules, paper size, subject distribution, duration, and marking scheme as editable/versioned data. |
| Question bank module | Store approved questions, options, correct answer, explanation, topic tags, difficulty, provenance, validation/review status, and revision history. Search/filter eligible questions for paper assembly. |
| Generation workflow | Prepare syllabus context, call OpenAI with structured output, record model/prompt metadata, run validation, retry or reject failures, and route uncertain questions for human review. LangChain can orchestrate this workflow where it adds value; keep core rules in ordinary Python functions. |
| Validation and review | Check schema, one unambiguous correct option, plausible distractors, syllabus alignment, duplicates/similarity, explanation consistency, unsafe or out-of-scope content, and blueprint coverage. Automated checks reduce errors but do not establish scientific correctness; allow guardian/teacher review before questions enter the approved bank. |
| Exam/attempt module | Assemble a paper from approved questions, snapshot the paper and scoring settings, manage start/deadline/status, save answers, support resume, and enforce one final submission. Use server time as authoritative. |
| Scoring module | Score objective responses deterministically using the attempt's snapshot of the answer key and marking scheme. Persist per-question outcome and aggregate subject/topic scores. |
| Results and recommendation module | Explain correct answers, summarize strengths and gaps, identify topics for revision, and propose follow-up practice based on attempt history. Use transparent rules first; if an LLM summarizes results, provide only the required data and clearly separate suggestions from official scoring. |
| History and analytics module | List attempts and results; calculate accuracy, time spent, unanswered questions, subject/topic trends, and progress over time. Preserve historical snapshots so edits to the bank do not alter prior results. |
| MongoDB | Persist users, syllabus/blueprint versions, question bank, exam papers, attempts, answers, results, and generation/audit metadata. Add indexes for owner plus date, attempt status, syllabus/topic, and approved-question selection. |
| Background worker (later or as needed) | Run slow generation, deduplication, reports, and retryable jobs outside web requests. Use a durable queue when asynchronous workloads justify it. |
| Observability | Application logs, error reporting, request/job metrics, and traces. LangSmith can trace/evaluate LLM workflows; it does not replace general production monitoring. Redact student identifiers and answers from traces where possible. |

### Suggested student flow

1. Select syllabus edition, subjects/chapters, difficulty mix, and exam settings.
2. Backend verifies sufficient approved questions exist and assembles a paper with a fixed question order and immutable answer-key/scoring snapshot.
3. Student starts the attempt. The client shows the timer and saves answers periodically and on navigation; the server stores the authoritative state.
4. Student submits, or the server closes the attempt when time expires. Submission is idempotent so retries cannot create duplicate results.
5. Backend scores the snapshot deterministically and records subject/topic breakdowns.
6. UI displays the score, per-question answer and explanation, topic analysis, and recommended next practice. The attempt remains available in history.

## 4. Data model outline

Use MongoDB documents with stable IDs and explicit ownership/version fields. Avoid embedding unbounded attempt history inside a user document.

- **User:** ID, role, login identity, preferences, timestamps.
- **SyllabusVersion:** name/year, source/review metadata, subjects, chapter/topic tree, active status.
- **ExamBlueprint:** syllabus version, total question count (180 initially), per-subject/topic constraints, duration, marking rules, version.
- **Question:** stem, options, correct option, explanation, subject/chapter/topic IDs, difficulty, source/provenance, language, review state, content version, generation metadata, timestamps.
- **ExamPaper:** owner, selected scope, blueprint version, ordered question references plus immutable question content snapshots, answer-key snapshot, marking rules, created time.
- **Attempt:** owner, paper ID/snapshot, status, start/deadline/submission times, answer map, autosave/version metadata.
- **Result:** attempt ID, scoring version, total and subject/topic aggregates, per-question correctness/marks/time if collected, recommendation data, finalized time.
- **GenerationRun/AuditEvent:** request scope, prompt/model versions, validation outcomes, reviewer decisions, timestamps, and operational status. Store no unnecessary personal data.

For autosave, use an upsert keyed by attempt and question (or a bounded answer map with revision numbers), and reject writes after final submission. Add a unique constraint or equivalent idempotency key for finalization.

## 5. Dependencies

Choose and pin compatible versions during implementation; the list below names likely packages, not version commitments.

### Frontend

- React and TypeScript; Vite for the development/build toolchain.
- React Router for page navigation.
- TanStack Query for API state and cache; a small local state store only if needed for the active exam.
- React Hook Form and Zod for forms and client-side schema checks.
- A component library such as MUI or shadcn/ui, selected once to keep the interface consistent.
- Vitest and React Testing Library for UI tests; Playwright for end-to-end exam flow tests.

### Backend

- Python 3.x, FastAPI, Pydantic, and Uvicorn.
- PyMongo (or the MongoDB-supported async driver available at implementation time) for MongoDB access; define repository boundaries so the driver can change without leaking into business logic.
- OpenAI Python SDK for model API calls; use structured outputs/function schemas supported by the chosen model.
- LangChain components only for orchestration/retrieval patterns that are useful; keep scoring, eligibility, and validation logic deterministic and directly testable.
- Optional: Redis plus a task queue such as Celery, Dramatiq, or RQ for asynchronous generation when needed. Do not add a queue until there is a real background workload.
- Pytest, HTTPX test client, Ruff, and mypy (or Pyright) for quality checks.

### Data, deployment, and operations

- MongoDB Community/Atlas, with automated backups and a documented restore process.
- Docker and Docker Compose for reproducible local development; a managed container platform for deployment when selected.
- Secret manager/environment injection for OpenAI and database credentials; never commit secrets.
- Structured logging and error reporting (for example, OpenTelemetry-compatible instrumentation plus a hosted or self-managed backend).
- LangSmith for LLM trace inspection and dataset-based prompt/workflow evaluation, configured with privacy-aware redaction and retention.
- CI pipeline for linting, type checks, tests, dependency/security scanning, and build artifacts.

## 6. Suggested folder structure

```text
neet-practice/
├── README.md
├── NEET-Generate-Sample-Questions.md
├── .env.example
├── docker-compose.yml
├── frontend/
│   ├── package.json
│   ├── src/
│   │   ├── app/                 # Router, app shell, providers
│   │   ├── features/
│   │   │   ├── syllabus/
│   │   │   ├── exam/
│   │   │   ├── results/
│   │   │   └── history/
│   │   ├── components/          # Shared UI components
│   │   ├── services/            # Typed API client
│   │   └── types/
│   └── tests/
├── backend/
│   ├── pyproject.toml
│   ├── app/
│   │   ├── main.py              # FastAPI application entry point
│   │   ├── api/v1/              # HTTP routes and request/response models
│   │   ├── core/                # Settings, auth, errors, logging
│   │   ├── modules/
│   │   │   ├── users/
│   │   │   ├── syllabus/
│   │   │   ├── questions/
│   │   │   ├── generation/
│   │   │   ├── exams/
│   │   │   ├── scoring/
│   │   │   ├── analytics/
│   │   │   └── recommendations/
│   │   ├── db/                  # Mongo client, indexes, repositories
│   │   ├── workers/             # Optional background jobs
│   │   └── observability/
│   └── tests/
├── content/
│   ├── syllabus/                # Reviewed, versioned syllabus imports
│   ├── blueprints/
│   └── prompt-templates/
├── infra/
│   ├── docker/
│   └── deployment/              # Add environment-specific deployment files
└── docs/
    ├── api.md
    ├── data-model.md
    └── operations.md
```

The existing repository contains a `python-agent-poc/` directory. This proposed layout is a target structure; implementation can either evolve that prototype or create the `frontend/` and production backend modules alongside it, after reviewing its current contents.

## 7. Implementation steps

1. **Confirm product rules:** Identify intended user/guardian access, syllabus edition, paper duration, subject distribution, marking rules, language, and whether questions must be reviewed before use. Record these in versioned configuration rather than source-code constants.
2. **Define syllabus and blueprint:** Import the chosen official syllabus into a reviewable topic tree. Define the initial 180-question blueprint and mark its source/version/date.
3. **Define schemas and API contracts:** Specify question, paper, attempt, answer, result, and history structures; document endpoints and ownership rules before building UI and backend modules.
4. **Build the application foundation:** Set up React/TypeScript, FastAPI, MongoDB connectivity, configuration, authentication, structured logging, and local Docker development.
5. **Implement the reviewed question bank:** Add syllabus selection, question storage, review states, filters, and an authoring/import path. Establish a seed set of verified questions for initial end-to-end use.
6. **Implement generation and validation:** Add OpenAI structured generation, prompt/version tracking, schema and content checks, duplicate detection, and a review queue. Evaluate a curated set of outputs before allowing generated items into the approved bank.
7. **Implement paper assembly and exam-taking:** Select only approved, eligible questions; persist a paper snapshot; add timer, navigation, autosave, resume, and reliable submission/expiry behavior.
8. **Implement scoring and result history:** Compute results from the stored key and marking snapshot; add explanations, subject/topic aggregates, attempt history, and basic trend views.
9. **Add recommendations:** Start with understandable rules based on topic accuracy and unanswered questions. Introduce an LLM-generated narrative only as a constrained optional layer, checked against computed facts.
10. **Harden and deploy:** Verify backups/restores, access control, rate limits, data retention, privacy-conscious telemetry, error handling, accessibility, and mobile layouts. Run end-to-end flows from paper creation through historical result review.
11. **Iterate from usage:** Review question quality and student feedback, refine blueprint coverage, and add spaced practice, adaptive difficulty, or a background worker only when they solve an observed need.

## 8. Key quality and privacy safeguards

- Never let generated content enter a live exam until it passes validation and the chosen review policy.
- Show the syllabus edition and practice-paper settings for each exam; retain them with the attempt.
- Do not ask an LLM to score or infer correctness. Recompute scores from answer keys and explicit rules.
- Make submission safe to retry and autosave resilient to refreshes or brief network loss.
- Keep API keys server-side. Enforce authorization at the API for every paper, attempt, and result.
- Collect only data needed for learning history. Avoid sending student names, account identifiers, or full answer history to LLMs unless necessary; redact traces and control retention.
- Provide accessible controls, readable explanations, keyboard navigation, and responsive layouts.
- Add reviewable logging for generated-question provenance and changes to approved questions; historical exam results must remain tied to the exact content version taken.
