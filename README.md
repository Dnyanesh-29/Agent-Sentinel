<div align="center">

# 🛡️ Agent Sentinel

**Identify. Simulate. Defend.**

A closed-loop system for studying and defending against prompt injection attacks on AI payment agents — built for the **Mastercard Innovation Challenge 2026**.

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![React](https://img.shields.io/badge/React-19-61DAFB?style=flat&logo=react&logoColor=black)](https://react.dev)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![HuggingFace](https://img.shields.io/badge/🤗%20HuggingFace-DistilBERT-FFD21E?style=flat)](https://huggingface.co/Dnyanesh29)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=flat)](LICENSE)

</div>

---

## The Problem

Banks are deploying AI agents with real payment authority — agents that can approve transactions, waive fraud flags, and act on customer requests with minimal human oversight. These agents routinely read untrusted content: receipts, memos, support emails.

This creates a direct attack surface. An adversary can embed hidden instructions inside an attached document. If the agent treats that content as authoritative rather than as data, it may execute an unauthorized action — approving a fraudulent transaction, waiving a fraud flag, bypassing verification — **without the customer or bank ever instructing it to do so.**

This is **prompt injection applied to financial AI agents.** Agent Sentinel is a full pipeline for studying this concretely: build an agent, attack it, measure how it fails, and train a classifier to defend it.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│   IDENTIFY              GENERATE              DEFEND             │
│                                                                  │
│  Research          Mock Payment Agent      DistilBERT            │
│  attack        →   + Red-Team         →    Classifier            │
│  vectors           Harness                 (fine-tuned)          │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 🔍 Identify
Research into documented and novel prompt injection techniques: direct override instructions, authority spoofing, urgency framing, format mimicry, conversation-history poisoning, and indirect/delayed exploitation.

### ⚔️ Generate
A **mock payment agent** (Sentinel) is built on `openai/gpt-oss-120b` via the Groq API with real tool-calling authority:

| Tool | Purpose |
|---|---|
| `approve_transaction` | Approve a payment |
| `waive_fraud_flag` | Dismiss a fraud alert |
| `check_balance` | Read account balance |
| `read_attached_content` | Parse an attached document |

The agent's system prompt explicitly instructs it to treat attached content as data, not instructions. A **red-team harness** (`backend/red_team_advanced.py`) then attacks it with 15 adversarial payloads across four categories, automatically detecting whether the agent was fooled.

### 🛡️ Defend
A **DistilBERT-base-uncased** classifier is fine-tuned to detect injection payloads in attached content and wired into a FastAPI `/run-protected` endpoint that intercepts requests before they reach the agent.

---

## Classifier Training

The classifier was trained on a synthetic dataset generated via the Groq API — prompted to produce varied rewrites of hand-written seed injection patterns and benign documents. Training was iterative, driven by observed failure modes.

### v1 — Initial Dataset (~315 examples)
Seed patterns covering obvious attack types: system-override instructions, false authority claims, urgency framing, JSON-embedded commands.

> **Result:** 85.7% OOD accuracy
> **Gap:** Weak recall on subtle, conversational attacks — injections that sounded like plausible customer communication.

### v2 — Targeted Recall Improvement
Added targeted examples for the observed failure mode: conversational injections, indirect requests, social-engineering framing.

> **Result:** Improved recall
> **New gap:** Precision — the model flagged legitimate messages mentioning "approval" or "following up" as false positives.

### v3 — Contrastive Hard Negatives
Added "hard negative" examples: benign messages using similar vocabulary to attacks but in genuinely non-injecting contexts, giving the model the contrastive signal to distinguish surface similarity from actual injection intent.

> **Final result: 92.9% OOD accuracy**

> **Note on the synthetic vs. OOD gap:** Validation metrics on the held-out synthetic split reach ~99% accuracy / F1 / AUC. The gap down to 92.9% on the hand-written OOD set is expected — the synthetic val set shares the same linguistic distribution as training. The OOD set uses genuinely novel phrasing never seen during training. That the model generalises to 92.9% rather than collapsing is the signal that iterative dataset refinement built real generalisation, not surface-feature pattern-matching. This gap is a calibration signal, not a gap to hide.

---

## Red-Team Results

The harness tests 15 payloads across four attack categories:

| Category | Description |
|---|---|
| **1 — Multi-Turn History Poisoning** | Fabricates prior conversation turns (fake policy exceptions, spoofed tool results) to make an unauthorized request look pre-approved |
| **2 — Tool-Result Format Mimicry** | Crafts attached content that impersonates an internal system response (HTTP API output, JSON verification result) |
| **3 — Compound Layered Claims** | Combines multiple persuasion vectors: ticket ID + compliance sign-off + named authority + urgency deadline |
| **4 — Indirect / Delayed Exploitation** | Plants a false belief or redefined term in Turn 1 via attached content; Turn 2 exploits the planted premise with a plain request |

**7 of 15 payloads successfully fooled the unprotected agent.**

Of those 7, the classifier correctly blocked 5 — all payloads delivered via the attached-content channel — at **0.96+ confidence**, including cases where the injection was wrapped in legitimate-looking document formatting with no explicit attack syntax.

### Classifier Coverage

```
Category 2 — Format Mimicry       ✅  1/1 blocked   (risk score 0.96+)
Category 3 — Compound Layered     ✅  2/2 blocked   (risk score 0.96+)
Category 4 — Indirect / Delayed   ✅  2/2 blocked   (risk score 0.96+)
Category 1 — History Poisoning    ⚠️  0/2 — outside classifier scope
```

The 2 bypasses (Category 1) are structurally outside the classifier's scope. These attacks inject fabricated turns directly into the conversation history array — there is no attached document to scan. This is a documented limitation, not a hidden gap.

---

## Demo

The frontend provides a split-screen interface:

- **Left panel** — Choose from 8 pre-loaded scenarios (3 baseline + 5 confirmed red-team attacks); auto-fills `USER_CONTEXT` and `ATTACHED_PAYLOAD`
- **Right panel** — Live LLM execution trace: full agent reasoning, tool calls, and tool results as they stream in
- **Top bar** — Toggle between `[ MODE: UNPROTECTED ]` and `[ MODE: PROTECTED ]`
- **Defense Matrix** — Classifier risk score, action taken, and (for red-team scenarios in protected mode) a one-line note explaining why the payload was flagged

The pre-loaded red-team scenarios (`04_FORMAT_MIMICRY` → `08_FALSE_PRIOR_DECISION`) use the exact payload text confirmed to succeed against the unprotected agent — so you can directly observe the before/after in the same UI.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Agent LLM | `openai/gpt-oss-120b` via Groq API |
| Backend | Python · FastAPI · Uvicorn |
| Classifier | HuggingFace Transformers (DistilBERT-base-uncased) · PyTorch |
| Dataset generation | Groq API · scikit-learn |
| Frontend | React 19 · Vite · Tailwind CSS v4 · Axios |
| Training environment | Kaggle (2×T4 GPU) |

---

## Repository Structure

```
Agent-Sentinel/
├── backend/
│   ├── main.py                             # FastAPI app (/run-unprotected, /run-protected)
│   ├── mockAgent.py                        # Mock payment agent (Groq tool-calling)
│   ├── red_team_advanced.py                # Red-team harness (15 payloads, 4 categories)
│   ├── test_classifier_against_redteam.py  # Classifier coverage test
│   ├── test_injections.py                  # Early-stage manual injection tests
│   ├── red_team_results.json               # Results from the last red-team run
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx                         # Main UI component
│   │   └── ...
│   └── package.json
├── scripts/
│   ├── generate_dataset_v1.py              # Initial dataset generator
│   ├── generate_dataset_v2.py              # v2: recall-targeted additions
│   ├── generate_dataset_v3.py              # v3: hard-negative contrastive additions
│   └── synthetic_dataset.jsonl             # Final merged training dataset
├── results/
│   └── agent-sentinel-classifier/          # Fine-tuned DistilBERT weights
│       ├── config.json
│       ├── model.safetensors               # ~255 MB — see Setup
│       └── tokenizer.json
├── .env                                    # Local only — never committed
├── .gitignore
├── LICENSE
└── README.md
```

---

## Setup

### Prerequisites
- Python 3.11+
- Node.js 20+
- [Groq API key](https://console.groq.com)

### 1. Clone the repo

```bash
git clone https://github.com/Dnyanesh-29/Agent-Sentinel.git
cd Agent-Sentinel
```

### 2. Set your API key

```bash
# Create .env in the project root
echo 'GROQ_API_KEY="your_groq_api_key_here"' > .env
```

The key is read from the environment — never hardcoded in any source file.

### 3. Download the classifier

The fine-tuned model weights (`model.safetensors`, ~255 MB) are excluded from this repo. Download and place the file at:

```
results/agent-sentinel-classifier/model.safetensors
```

> **Download:** *https://www.kaggle.com/models/dnyaneshbharambe/agent-sentinal-classifier*

The remaining files in `results/agent-sentinel-classifier/` (`config.json`, `tokenizer.json`, `tokenizer_config.json`) are committed to the repo.

> If the classifier is not present, the backend will warn on startup and `/run-protected` will fall back to passing all requests through. `/run-unprotected` always works without it.

### 4. Install backend dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 5. Run the backend

```bash
uvicorn main:app --reload
# API available at http://localhost:8000
# Docs at http://localhost:8000/docs
```

### 6. Install and run the frontend

```bash
cd frontend
npm install
npm run dev
# UI available at http://localhost:5173
```

---

## Known Limitations & Future Work

**Conversation-history poisoning**
The classifier only scans `attached_content`. Attacks that fabricate prior conversation turns bypass it entirely — there is no document surface to scan. Defending against this requires either classifying every incoming message turn or introducing provenance/signing mechanisms so fabricated turns can be detected.

**Dataset scale**
~315 training examples is small by NLP standards. Coverage of real-world attack vocabulary is limited to what the synthetic generation process can reach from its seed patterns. A larger, adversarially-generated dataset would improve robustness.

**Single-classifier architecture**
One binary classifier applied at one pipeline point is a single point of failure. An ensemble (multiple classifiers with different training distributions, or a classifier + rule-based layer for explicit tool-call syntax) would be harder to fool with distribution shift.

**Single-turn scope**
The classifier makes per-request decisions with no memory of prior turns. A multi-turn defense tracking behavioral patterns across a session — flagging cases where the agent's actions diverge from the user's stated intent — is a more complete solution.

---

## License

MIT — see [LICENSE](LICENSE).
