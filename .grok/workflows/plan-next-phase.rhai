// Plan the next modernization phase for SpectraX.
// Reads docs/PLAN.md + current code, picks the phase, researches it in parallel,
// synthesizes a shippable implementation plan, adversarially challenges it.
//
// Args (all optional):
//   phase: integer 0-4 to force a phase, or omit/"auto" to detect from code
//   depth: "quick" | "full" (default full) — quick skips adversarial challenge

let meta = #{
    name: "plan-next-phase",
    description: "Survey SpectraX docs/code and produce a shippable implementation plan for the next modernization phase",
    when_to_use: "Before starting work on the next PLAN.md phase, or to re-plan a phase after the codebase has moved",
    phases: [
        #{ title: "Survey", detail: "read PLAN.md + detect which phase is next" },
        #{ title: "Research", detail: "parallel deep-dives scoped to that phase" },
        #{ title: "Draft", detail: "synthesize implementation plan" },
        #{ title: "Challenge", detail: "adversarial review of the plan against code" },
        #{ title: "Finalize", detail: "write polished plan artifact" },
    ],
};

// --- schemas -----------------------------------------------------------------

let survey_schema = #{
    "type": "object",
    "required": ["next_phase", "phase_title", "rationale", "already_done", "open_questions", "blockers"],
    "properties": #{
        "next_phase": #{ "type": "integer", "minimum": 0, "maximum": 4 },
        "phase_title": #{ "type": "string" },
        "rationale": #{ "type": "string" },
        "already_done": #{
            "type": "array",
            "items": #{ "type": "string" },
            "maxItems": 20,
        },
        "open_questions": #{
            "type": "array",
            "items": #{ "type": "string" },
            "maxItems": 10,
        },
        "blockers": #{
            "type": "array",
            "items": #{ "type": "string" },
            "maxItems": 10,
        },
        "plan_status": #{ "type": "string" },
    },
};

let research_schema = #{
    "type": "object",
    "required": ["dimension", "findings", "files_touched", "risks", "test_gaps"],
    "properties": #{
        "dimension": #{ "type": "string" },
        "findings": #{
            "type": "array",
            "maxItems": 12,
            "items": #{
                "type": "object",
                "required": ["claim", "evidence", "path"],
                "properties": #{
                    "claim": #{ "type": "string" },
                    "evidence": #{ "type": "string" },
                    "path": #{ "type": "string" },
                },
            },
        },
        "files_touched": #{
            "type": "array",
            "items": #{ "type": "string" },
            "maxItems": 30,
        },
        "risks": #{
            "type": "array",
            "items": #{ "type": "string" },
            "maxItems": 8,
        },
        "test_gaps": #{
            "type": "array",
            "items": #{ "type": "string" },
            "maxItems": 8,
        },
        "recommendations": #{
            "type": "array",
            "items": #{ "type": "string" },
            "maxItems": 8,
        },
    },
};

let draft_schema = #{
    "type": "object",
    "required": ["title", "summary", "pr_plan", "success_criteria", "out_of_scope", "open_decisions"],
    "properties": #{
        "title": #{ "type": "string" },
        "summary": #{ "type": "string" },
        "pr_plan": #{
            "type": "array",
            "minItems": 1,
            "maxItems": 8,
            "items": #{
                "type": "object",
                "required": ["id", "title", "goal", "tasks", "files", "tests", "depends_on"],
                "properties": #{
                    "id": #{ "type": "string" },
                    "title": #{ "type": "string" },
                    "goal": #{ "type": "string" },
                    "tasks": #{
                        "type": "array",
                        "items": #{ "type": "string" },
                        "maxItems": 12,
                    },
                    "files": #{
                        "type": "array",
                        "items": #{ "type": "string" },
                        "maxItems": 20,
                    },
                    "tests": #{
                        "type": "array",
                        "items": #{ "type": "string" },
                        "maxItems": 10,
                    },
                    "depends_on": #{
                        "type": "array",
                        "items": #{ "type": "string" },
                        "maxItems": 5,
                    },
                    "risk": #{ "type": "string" },
                },
            },
        },
        "success_criteria": #{
            "type": "array",
            "items": #{ "type": "string" },
            "maxItems": 12,
        },
        "out_of_scope": #{
            "type": "array",
            "items": #{ "type": "string" },
            "maxItems": 10,
        },
        "open_decisions": #{
            "type": "array",
            "items": #{
                "type": "object",
                "required": ["question", "recommendation"],
                "properties": #{
                    "question": #{ "type": "string" },
                    "recommendation": #{ "type": "string" },
                    "impact_if_wrong": #{ "type": "string" },
                },
            },
            "maxItems": 8,
        },
        "risks": #{
            "type": "array",
            "items": #{ "type": "string" },
            "maxItems": 8,
        },
        "estimated_effort": #{ "type": "string" },
    },
};

let challenge_schema = #{
    "type": "object",
    "required": ["verdict", "issues", "missing", "over_scoped"],
    "properties": #{
        "verdict": #{ "type": "string", "enum": ["approve", "revise"] },
        "issues": #{
            "type": "array",
            "maxItems": 10,
            "items": #{
                "type": "object",
                "required": ["severity", "detail", "evidence"],
                "properties": #{
                    "severity": #{ "type": "string", "enum": ["blocker", "major", "nit"] },
                    "detail": #{ "type": "string" },
                    "evidence": #{ "type": "string" },
                },
            },
        },
        "missing": #{
            "type": "array",
            "items": #{ "type": "string" },
            "maxItems": 10,
        },
        "over_scoped": #{
            "type": "array",
            "items": #{ "type": "string" },
            "maxItems": 8,
        },
        "suggested_edits": #{
            "type": "array",
            "items": #{ "type": "string" },
            "maxItems": 10,
        },
    },
};

// --- args --------------------------------------------------------------------

let force_phase = ();
let depth = "full";
if args != () {
    if args.phase != () { force_phase = args.phase; }
    if args.depth != () { depth = args.depth; }
}

// --- Phase: Survey -----------------------------------------------------------

phase("Survey");
log("Surveying docs/PLAN.md and codebase to identify the next phase");

let survey_prompt = "";
survey_prompt += "You are surveying the SpectraX repo to decide which modernization phase is next.\n";
survey_prompt += "Repo root is the current workspace. Python package lives under video-feed/ (import: videofeed).\n\n";
survey_prompt += "REQUIRED reads (use read_file / list_dir / grep — do not answer from memory):\n";
survey_prompt += "1. docs/PLAN.md — full document, especially §4 Phases and §7 Open questions\n";
survey_prompt += "2. CLAUDE.md or Claude.md — layout/gotchas\n";
survey_prompt += "3. video-feed/videofeed/ structure (list_dir)\n";
survey_prompt += "4. Grep for Phase-0 markers already landed: auth middleware, bearer, create_app, ";
survey_prompt += "api/v1, FileSecretsStore, secrets.compare_digest, slowapi, TestClient auth tests, ";
survey_prompt += ".github/workflows, pyproject.toml, src/spectrax\n";
survey_prompt += "5. Spot-check routes/auth.py, visualizer.py, surveillance.py for current security posture\n\n";
survey_prompt += "Phase detection rules (apply in order):\n";
survey_prompt += "- Phase 0 incomplete if: no real API auth middleware, DELETE unauthenticated, ";
survey_prompt += "no CI, /paths side-server still present, detail=str(e) still leaks, no characterization tests.\n";
survey_prompt += "- Phase 1 incomplete if: still video-feed/ + setup.py, no pyproject.toml src layout, sys.path hack remains.\n";
survey_prompt += "- Phase 2 incomplete if: set_* setters still wire routes, no create_app lifespan, no SecretsStore.\n";
survey_prompt += "- Phase 3 incomplete if: no /api/v1, no EventBus/SSE, no MediaMTX HTTP auth callback.\n";
survey_prompt += "- Phase 4 incomplete if: docs still stale vs code, no external module proof-of-life.\n\n";

if force_phase != () {
    survey_prompt += "OVERRIDE: args.phase is set to ";
    survey_prompt += json_encode(force_phase);
    survey_prompt += ". Still survey, but set next_phase to that value and note the override in rationale.\n\n";
} else {
    survey_prompt += "No phase override — detect the earliest incomplete phase (usually 0).\n\n";
}

survey_prompt += "Return structured JSON only. already_done = concrete checklist items from PLAN.md that ARE already true in code. ";
survey_prompt += "open_questions = PLAN §7 items still relevant to next_phase. blockers = things that would prevent starting.\n";
survey_prompt += "Empty arrays are valid only after you inspected the code.";

let survey = agent(survey_prompt, #{
    label: "survey",
    capability_mode: "read-only",
    agent_type: "explore",
    output_schema: survey_schema,
});

if survey == () || !survey.success || survey.output == () {
    pause("infra", "Survey agent failed — resume to retry, or pass args.phase explicitly.");
}

let next_phase = survey.output.next_phase;
let phase_title = survey.output.phase_title;
let survey_rationale = survey.output.rationale;
let already_done = survey.output.already_done;
let open_qs = survey.output.open_questions;
let blockers = survey.output.blockers;

// Defaults for canned validate_only / partial schema fills
if next_phase == () { next_phase = 0; }
if phase_title == () { phase_title = "Stop the bleeding (security)"; }
if survey_rationale == () { survey_rationale = "defaulted: survey field missing"; }
if already_done == () { already_done = []; }
if open_qs == () { open_qs = []; }
if blockers == () { blockers = []; }

log("Next phase: " + next_phase.to_string() + " — " + phase_title);

// --- Phase: Research ---------------------------------------------------------

phase("Research");
log("Parallel research for Phase " + next_phase.to_string());

// Dimension packs per phase (fixed lists — no discovery agent)
let dimensions = [];
if next_phase == 0 {
    dimensions = [
        "security-auth",
        "security-hardening",
        "tests-and-ci",
        "dashboard-and-mjpeg-auth",
    ];
} else if next_phase == 1 {
    dimensions = [
        "packaging-layout",
        "dependency-refresh",
        "import-and-cli-migration",
        "deprecation-cleanup",
    ];
} else if next_phase == 2 {
    dimensions = [
        "process-inversion-lifespan",
        "di-routers",
        "config-and-secrets",
        "deploy-systemd-macos",
    ];
} else if next_phase == 3 {
    dimensions = [
        "api-v1-contract",
        "eventbus-sse",
        "mediamtx-auth-callback",
        "integration-tests",
    ];
} else {
    dimensions = [
        "docs-rewrite",
        "first-external-module",
        "dashboard-api-only",
        "success-criteria-audit",
    ];
}

let research_base = "";
research_base += "You are researching Phase ";
research_base += next_phase.to_string();
research_base += " (";
research_base += phase_title;
research_base += ") of the SpectraX modernization plan for ONE dimension only.\n\n";
research_base += "Read docs/PLAN.md section for this phase AND the listed files in the live codebase under video-feed/.\n";
research_base += "Use read_file, grep, list_dir — never invent file contents.\n";
research_base += "Survey rationale (context only): ";
research_base += json_encode(survey_rationale);
research_base += "\nAlready done (do not re-plan these): ";
research_base += json_encode(already_done);
research_base += "\nOpen questions from plan: ";
research_base += json_encode(open_qs);
research_base += "\n\n";

// Dimension-specific instructions
fn dimension_brief(dim, phase_n) {
    if dim == "security-auth" {
        let s = "";
        s += "DIMENSION: security-auth. Focus on PLAN Phase 0 items 1-2,7: bearer+session auth over existing app, ";
        s += "admin scope on DELETE, delete /auth/verify, secrets.compare_digest, rate-limit login, bind 127.0.0.1 default.\n";
        s += "Read: video-feed/videofeed/routes/auth.py, routes/recordings.py, visualizer.py, credentials.py, surveillance.py (bind host).\n";
        s += "Map exact insertion points for middleware/deps without inventing a rewrite of the topology.\n";
        return s;
    }
    if dim == "security-hardening" {
        let s = "";
        s += "DIMENSION: security-hardening. Focus on PLAN Phase 0 items 3-6: global exception handler, kill detail=str(e), ";
        s += "XSS escape in templates, rtspEncryption strict, stop printing/embedding plaintext creds, delete /paths http.server.\n";
        s += "Read: routes/recordings.py, routes/statistics.py, templates/recordings.html, templates/viewer.html, ";
        s += "config.py, utils.py, surveillance.py (search for http.server, /paths, os._exit).\n";
        return s;
    }
    if dim == "tests-and-ci" {
        let s = "";
        s += "DIMENSION: tests-and-ci. Focus on PLAN Phase 0 item 8: characterization tests with httpx TestClient, ";
        s += "auth tests, CI workflow, requirements-dev.txt (pytest, pytest-cov, pytest-asyncio, httpx, ruff).\n";
        s += "Read: video-feed/tests/, pytest.ini, requirements.txt, check for .github/workflows, ruff.toml.\n";
        s += "List which endpoints need characterization fixtures and how to boot the app without MediaMTX for unit tests.\n";
        return s;
    }
    if dim == "dashboard-and-mjpeg-auth" {
        let s = "";
        s += "DIMENSION: dashboard-and-mjpeg-auth. PLAN risk: Auth breaks MJPEG/dashboard because <img> cannot send headers.\n";
        s += "Read: templates/viewer.html, recordings.html, routes/video.py, routes/pages.py, ui/dashboard.html if present.\n";
        s += "Recommend cookie-session strategy for browser paths vs bearer for API clients. Note PLAN open Q1 (TLS/Secure cookie).\n";
        return s;
    }
    if dim == "packaging-layout" {
        let s = "";
        s += "DIMENSION: packaging-layout. Phase 1: pyproject.toml, git mv to src/spectrax/, kill setup.py/cli shim/sys.path hack.\n";
        s += "Read: video-feed/setup.py, videofeed/cli.py, videofeed/surveillance.py (sys.path), scripts/surveillance.sh, ruff.toml.\n";
        return s;
    }
    if dim == "dependency-refresh" {
        let s = "";
        s += "DIMENSION: dependency-refresh. Phase 1 tiered upgrades (web → CV → utils), lockfile, re-verify avc1 playback after OpenCV bump.\n";
        s += "Read: video-feed/requirements.txt, recorder codec usage, test_supervision_integration.py.\n";
        return s;
    }
    if dim == "import-and-cli-migration" {
        let s = "";
        s += "DIMENSION: import-and-cli-migration. Phase 1 package rename videofeed→spectrax, console scripts, import graph.\n";
        s += "Grep for videofeed imports, PYTHONPATH, scripts that hardcode paths.\n";
        return s;
    }
    if dim == "deprecation-cleanup" {
        let s = "";
        s += "DIMENSION: deprecation-cleanup. Phase 1: @app.on_event → lifespan, pydantic v2 warnings, dead .enc allowlist (PLAN Q3).\n";
        s += "Read: visualizer.py, routes/files.py allowlist, any on_event usage.\n";
        return s;
    }
    if dim == "process-inversion-lifespan" {
        let s = "";
        s += "DIMENSION: process-inversion-lifespan. Phase 2: create_app + lifespan owns detector/MediaMTX/DB; CLI becomes serve/apikey/admin/reset/doctor.\n";
        s += "Read: surveillance.py, visualizer.py startup/shutdown, MediaMTX spawn paths.\n";
        return s;
    }
    if dim == "di-routers" {
        let s = "";
        s += "DIMENSION: di-routers. Phase 2: Depends() from api/deps.py; delete every set_* setter; split visualizer.\n";
        s += "Grep set_ in routes/ and visualizer; list each router dependency.\n";
        return s;
    }
    if dim == "config-and-secrets" {
        let s = "";
        s += "DIMENSION: config-and-secrets. Phase 2: pydantic-settings, SecretsStore File/Keyring, migrate keychain.\n";
        s += "Read: config.py, credentials.py, detector_config.py, config/surveillance.yml.\n";
        return s;
    }
    if dim == "deploy-systemd-macos" {
        let s = "";
        s += "DIMENSION: deploy-systemd-macos. Phase 2 systemd units, launchd/dev docs; PLAN Q4 MediaMTX ownership.\n";
        s += "Read: scripts/surveillance.service, scripts/surveillance.sh.\n";
        return s;
    }
    if dim == "api-v1-contract" {
        let s = "";
        s += "DIMENSION: api-v1-contract. Phase 3: /api/v1 prefix, pydantic response models, OpenAPI as frozen contract.\n";
        s += "List current routes vs PLAN §3.1 endpoint groups; note auth scopes per group.\n";
        return s;
    }
    if dim == "eventbus-sse" {
        let s = "";
        s += "DIMENSION: eventbus-sse. Phase 3: events table, EventBus, SSE Last-Event-ID, retention cleanup.\n";
        s += "Read: recorder.py / api.py DB patterns for where events table should live.\n";
        return s;
    }
    if dim == "mediamtx-auth-callback" {
        let s = "";
        s += "DIMENSION: mediamtx-auth-callback. Phase 3: authMethod http, remove HLS user:pass URLs.\n";
        s += "Read: config.py MediaMTX config generation, utils.py HLS URL building.\n";
        return s;
    }
    if dim == "integration-tests" {
        let s = "";
        s += "DIMENSION: integration-tests. Phase 3: detection → event row → SSE delivery without real MediaMTX where possible.\n";
        s += "Read existing tests and recorder hooks for emission points.\n";
        return s;
    }
    if dim == "docs-rewrite" {
        let s = "";
        s += "DIMENSION: docs-rewrite. Phase 4: ARCHITECTURE, README, API from OpenAPI, CONFIGURATION_GUIDE, routes/README.\n";
        s += "Read docs/ and flag every contradiction with code.\n";
        return s;
    }
    if dim == "first-external-module" {
        let s = "";
        s += "DIMENSION: first-external-module. Phase 4: notifier consuming SSE as contract proof-of-life in separate repo design.\n";
        s += "Specify minimal module contract surface and auth.\n";
        return s;
    }
    if dim == "dashboard-api-only" {
        let s = "";
        s += "DIMENSION: dashboard-api-only. Phase 4: dashboard talks only to /api/v1.\n";
        s += "Inventory template/JS fetch paths and non-API shortcuts.\n";
        return s;
    }
    if dim == "success-criteria-audit" {
        let s = "";
        s += "DIMENSION: success-criteria-audit. Map PLAN §6 checkboxes to current code truth and remaining work.\n";
        return s;
    }
    return "DIMENSION: " + dim + ". Research thoroughly for Phase " + phase_n.to_string() + ".\n";
}

let jobs = [];
for d in dimensions {
    let p = research_base;
    p += dimension_brief(d, next_phase);
    p += "\nReturn findings with concrete path+evidence. files_touched = paths an implementer will edit. ";
    p += "test_gaps and recommendations must be actionable. Empty findings only if you read the code and found nothing.";
    jobs.push(#{
        prompt: p,
        label: "research:" + d,
        capability_mode: "read-only",
        agent_type: "explore",
        output_schema: research_schema,
    });
}
let research_results = parallel(jobs);

let research_bundle = [];
let i = 0;
for r in research_results {
    let dim_name = dimensions[i];
    if r != () && r.success && r.output != () {
        research_bundle.push(r.output);
        log("Research OK: " + dim_name);
    } else {
        log("Research FAILED (continuing): " + dim_name);
        research_bundle.push(#{
            dimension: dim_name,
            findings: [],
            files_touched: [],
            risks: ["research agent failed — treat this dimension as incomplete"],
            test_gaps: [],
            recommendations: ["Re-run research for " + dim_name],
        });
    }
    i += 1;
}

// --- Phase: Draft ------------------------------------------------------------

phase("Draft");
log("Synthesizing implementation plan");

let draft_prompt = "";
draft_prompt += "You are writing the implementation plan for SpectraX Phase ";
draft_prompt += next_phase.to_string();
draft_prompt += " — ";
draft_prompt += phase_title;
draft_prompt += ".\n\n";
draft_prompt += "You MUST re-read docs/PLAN.md for this phase and spot-check key files before writing.\n";
draft_prompt += "Do not invent files that do not exist. Prefer the CURRENT layout (video-feed/videofeed/) ";
draft_prompt += "unless this phase is the repackage (Phase 1+).\n\n";
draft_prompt += "Survey output:\n";
draft_prompt += json_encode(survey.output);
draft_prompt += "\n\nResearch bundle (one object per dimension):\n";
draft_prompt += json_encode(research_bundle);
draft_prompt += "\n\nConstraints from project rules:\n";
draft_prompt += "- Branch off main with type prefix (feat/, fix/, docs/); never commit to main.\n";
draft_prompt += "- TDD for new code; characterization tests before risky refactors.\n";
draft_prompt += "- No hardcoded secrets; validate at boundaries.\n";
draft_prompt += "- Each PR independently reviewable; Phase 0 is security on CURRENT layout (no big restructure).\n";
draft_prompt += "- PLAN open questions: decide with a recommendation, not a shrug.\n\n";
draft_prompt += "Produce a PR plan DAG: 2-6 PRs max for this phase. Each PR needs concrete tasks, files, tests, depends_on.\n";
draft_prompt += "success_criteria must be checkable. out_of_scope must explicitly exclude later phases.\n";
draft_prompt += "estimated_effort: days or 1-2 weeks matching PLAN.\n";

let draft = agent(draft_prompt, #{
    label: "draft-plan",
    capability_mode: "read-only",
    agent_type: "plan",
    output_schema: draft_schema,
});

if draft == () || !draft.success || draft.output == () {
    pause("infra", "Draft agent failed — resume to retry.");
}

// --- Phase: Challenge (optional) ---------------------------------------------

let challenge_output = #{
    verdict: "approve",
    issues: [],
    missing: [],
    over_scoped: [],
    suggested_edits: [],
};

if depth != "quick" {
    phase("Challenge");
    log("Adversarial challenge of the draft plan");

    let challenge_prompt = "";
    challenge_prompt += "You are an adversarial reviewer. Your job is to FIND problems in this Phase ";
    challenge_prompt += next_phase.to_string();
    challenge_prompt += " implementation plan — not to rubber-stamp it.\n\n";
    challenge_prompt += "Independently re-read docs/PLAN.md for this phase and the code paths the plan claims to touch.\n";
    challenge_prompt += "Use read_file/grep. Default to verdict=revise unless the plan is tight.\n\n";
    challenge_prompt += "Check specifically:\n";
    challenge_prompt += "1. Scope creep into later phases\n";
    challenge_prompt += "2. Tasks that assume files/APIs that do not exist\n";
    challenge_prompt += "3. Missing tests for the risky bits (auth on MJPEG/cookies is the classic miss)\n";
    challenge_prompt += "4. Ordering bugs in the PR DAG (depends_on wrong)\n";
    challenge_prompt += "5. Open decisions left undecided without a recommendation\n";
    challenge_prompt += "6. Security items from PLAN that were silently dropped\n\n";
    challenge_prompt += "Draft plan:\n";
    challenge_prompt += json_encode(draft.output);
    challenge_prompt += "\n\nResearch bundle:\n";
    challenge_prompt += json_encode(research_bundle);
    challenge_prompt += "\n\nFor every issue, evidence must cite a path or PLAN section you inspected. ";
    challenge_prompt += "If you cannot verify a claim in code, mark it as an issue.";

    let challenge = agent(challenge_prompt, #{
        label: "challenge",
        capability_mode: "read-only",
        agent_type: "architect",
        output_schema: challenge_schema,
    });

    if challenge != () && challenge.success && challenge.output != () {
        challenge_output = challenge.output;
        let v = challenge_output.verdict;
        if v == () { v = "unknown"; }
        log("Challenge verdict: " + v);
    } else {
        log("Challenge agent failed — finalizing with unchallenged draft");
        challenge_output = #{
            verdict: "revise",
            issues: [#{
                severity: "major",
                detail: "Challenge agent failed; plan was not adversarially reviewed",
                evidence: "workflow infrastructure",
            }],
            missing: [],
            over_scoped: [],
            suggested_edits: ["Re-run with depth=full after fixing challenge agent"],
        };
    }
} else {
    phase("Challenge");
    log("depth=quick — skipping adversarial challenge");
}

// --- Phase: Finalize ---------------------------------------------------------

phase("Finalize");
log("Writing plan artifact");

let final_prompt = "";
final_prompt += "Write the final implementation plan markdown for SpectraX Phase ";
final_prompt += next_phase.to_string();
final_prompt += " — ";
final_prompt += phase_title;
final_prompt += ".\n\n";
final_prompt += "Incorporate the challenge feedback. If verdict is revise, fix every blocker and major issue ";
final_prompt += "in the plan text (do not just list them). Nits may become footnotes.\n\n";
final_prompt += "Draft plan (JSON):\n";
final_prompt += json_encode(draft.output);
final_prompt += "\n\nChallenge (JSON):\n";
final_prompt += json_encode(challenge_output);
final_prompt += "\n\nSurvey rationale: ";
final_prompt += json_encode(survey_rationale);
final_prompt += "\nBlockers noted at survey: ";
final_prompt += json_encode(blockers);
final_prompt += "\n\nMarkdown structure (use exactly these H2 headings):\n";
final_prompt += "# Phase N — Title\n";
final_prompt += "## Summary\n";
final_prompt += "## Why this phase next\n";
final_prompt += "## Decisions (with recommendations)\n";
final_prompt += "## PR plan\n";
final_prompt += "  For each PR: goal, tasks (checkbox list), files, tests, depends on, risk\n";
final_prompt += "## Success criteria\n";
final_prompt += "## Out of scope\n";
final_prompt += "## Risks & mitigations\n";
final_prompt += "## How to start (first commit / first PR)\n";
final_prompt += "\nBe concrete: real paths under video-feed/videofeed/ (or target paths if Phase 1+).\n";
final_prompt += "No filler. No inventing APIs. Match PLAN.md intent for this phase only.\n";
final_prompt += "Return ONLY the markdown document as your final message (no JSON wrapper, no preamble).";

let final_agent = agent(final_prompt, #{
    label: "finalize",
    capability_mode: "read-only",
    agent_type: "plan",
});

let report_md = "";
if final_agent != () && final_agent.success && final_agent.output != () {
    // output may be string (no schema) — coerce carefully
    if type_of(final_agent.output) == "string" {
        report_md = final_agent.output;
    } else {
        report_md = json_encode(final_agent.output);
    }
} else {
    // Fallback: render from draft JSON
    let fb_summary = "";
    if draft.output.summary != () { fb_summary = draft.output.summary; }
    let fb_prs = [];
    if draft.output.pr_plan != () { fb_prs = draft.output.pr_plan; }
    report_md = "# Phase " + next_phase.to_string() + " — " + phase_title + "\n\n";
    report_md += "## Summary\n\n";
    report_md += fb_summary + "\n\n";
    report_md += "## PR plan\n\n";
    report_md += "```json\n" + json_encode(fb_prs) + "\n```\n\n";
    report_md += "## Challenge notes\n\n";
    report_md += "```json\n" + json_encode(challenge_output) + "\n```\n";
    log("Finalize agent failed — wrote structured fallback from draft");
}

// Header banner
let banner_verdict = "unknown";
if challenge_output.verdict != () { banner_verdict = challenge_output.verdict; }
let banner = "";
banner += "<!-- Generated by plan-next-phase workflow. Source of truth for phase intent: docs/PLAN.md -->\n";
banner += "<!-- Phase: " + next_phase.to_string() + " | Challenge: " + banner_verdict + " | Depth: " + depth + " -->\n\n";
let full_report = banner + report_md;

let path = write_scratch_file("phase-plan.md", full_report);
log("Wrote plan to " + path);

// Guard fields that may be unit under validate_only canned outputs
let pr_count = 0;
if draft.output.pr_plan != () {
    pr_count = draft.output.pr_plan.len();
}
let summary_out = "";
if draft.output.summary != () { summary_out = draft.output.summary; }
let effort_out = "";
if draft.output.estimated_effort != () { effort_out = draft.output.estimated_effort; }
let decisions_out = [];
if draft.output.open_decisions != () { decisions_out = draft.output.open_decisions; }
let verdict_out = "unknown";
if challenge_output.verdict != () { verdict_out = challenge_output.verdict; }

complete(#{
    path: path,
    next_phase: next_phase,
    phase_title: phase_title,
    challenge_verdict: verdict_out,
    pr_count: pr_count,
    summary: summary_out,
    estimated_effort: effort_out,
    open_decisions: decisions_out,
});
