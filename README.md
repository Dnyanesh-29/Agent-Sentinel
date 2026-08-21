# Agent Sentinel

**A closed-loop system for identifying, simulating, and defending against prompt injection attacks on AI payment agents built for the Mastercard Innovation Challenge 2026.**

---

## The Problem

Banks are beginning to deploy AI agents with real payment authority: agents that can approve transactions, waive fraud flags, and act on customer requests with minimal human oversight. These agents routinely read untrusted content  receipts, memos, support emails — to help them make decisions.

This creates a direct attack surface. An adversary can embed hidden instructions inside an attached document, and if the agent treats that content as authoritative rather than as data, it may execute an unauthorized action: approving a fraudulent transaction, waiving a fraud flag, or bypassing verification — without the customer or the bank ever instructing it to do so.

This is **prompt injection applied to financial AI agents**, and it is not a theoretical risk. Agent Sentinel is a full pipeline for studying this problem concretely: building an agent, attacking it, measuring how it fails, and training a classifier to defend it.

---

## System Architecture

Agent Sentinel is built around three pillars:

```
┌─────────────────────────────────────────────────────────────────┐
│  IDENTIFY       GENERATE            DEFEND                       │
│                                                                  │
│  Research  →   Mock Agent      →   DistilBERT                   │
│  attack        + Red-Team          Classifier                   │
│  vectors       Harness             (fine-tuned)                 │
└─────────────────────────────────────────────────────────────────┘
```

### Identify
Research into documented and novel prompt injection techniques: direct override instructions, authority spoofing, urgency framing, format mimicry, conversation-history poisoning, and indirect/delayed exploitation.

### Generate
A **mock payment agent** (Sentinel) is built on top of `openai/gpt-oss-120b` via the Groq API, given real tool-calling authority (`approve_transaction`, `waive_fraud_flag`, `check_balance`, `read_attached_content`), and a hardened system prompt that explicitly instructs it to treat attached content as data, not instructions.

A **red-team harness** (`backend/red_team_advanced.py`) then attacks this agent with 15 adversarial payloads across four categories, automatically detecting whether the agent was fooled into calling a sensitive tool.

### Defend
A **DistilBERT-base-uncased** classifier is fine-tuned to detect injection payloads in attached content, and wired into a FastAPI `/run-protected` endpoint that intercepts requests before they reach the agent.

---

## Dataset & Training

The classifier was trained on a synthetic dataset generated using the Groq API — the same LLM used for the agent, prompted to generate varied rewrites of hand-written seed injection patterns and benign documents.

Training was iterative, with each round driven by observed failure modes:

### v1 - Initial Dataset (~315 examples)
Seed patterns covering obvious attack types (system-override instructions, false authority claims, urgency framing, JSON-embedded commands). Fine-tuned DistilBERT for 4 epochs on a Kaggle 2×T4 GPU environment.

**Result:** 85.7% accuracy on a hand-written out-of-distribution (OOD) test set.

**Gap identified:** Recall was weak on subtle, conversational attacks — injections that sounded like plausible customer communication rather than explicit commands.

### v2 - Targeted Recall Improvement
Added targeted examples for the specific failure mode: conversational injections, indirect requests, social-engineering framing. Retrained.

**Result:** Recall improved. New gap identified: precision — the model was flagging legitimate messages that mentioned concepts like "approval" or "following up" as false positives.

### v3 - Contrastive Hard Negatives
Added "hard negative" examples: benign messages that used similar vocabulary to attacks but in genuine, non-injecting contexts. This gave the model the contrastive signal needed to distinguish surface-level similarity from actual injection intent.

**Final result:** **92.9% accuracy** on the hand-written OOD test set. Validation metrics on the held-out synthetic split: ~99% accuracy / F1 / AUC.

The gap between synthetic validation (99%) and OOD accuracy (92.9%) is expected and worth noting: the validation set was held out from the same synthetic generation process as training, so it shares the same linguistic distribution. The hand-written OOD set uses genuinely novel phrasing the model has never seen. The fact that it generalises to 92.9% on that set — rather than collapsing — suggests the iterative dataset refinement did build meaningful generalisation, not just pattern-matching on surface features. This gap is a calibration signal, not a failure to hide.

---

## Red-Team Findings

The red-team harness (`backend/red_team_advanced.py`) tests 15 attack payloads across four categories against the mock payment agent:

| Category | Description |
|---|---|
| **1 — Multi-Turn Context Poisoning** | Fabricates prior conversation history (fake policy exceptions, spoofed tool results) to make an unauthorized request seem pre-approved |
| **2 — Tool-Result Format Mimicry** | Crafts attached content that impersonates an internal system response (HTTP API output, JSON verification result) |
| **3 — Compound Layered Claims** | Combines multiple persuasion vectors: ticket ID + compliance sign-off + named authority + urgency deadline |
| **4 — Indirect / Delayed Exploitation** | Plants a false belief or redefined term in Turn 1 (via attached content); Turn 2 exploits the planted premise with a plain request |

### Results: 7 of 15 payloads successfully fooled the agent

Of those 7, **the classifier correctly blocked 5** — all payloads delivered via the attached-content channel — at 0.96+ confidence, including cases where the injection was wrapped in legitimate-looking document formatting with no explicit attack syntax.

The **2 that bypassed the classifier** (Category 1: multi-turn history poisoning) are structurally outside its scope. These attacks work by injecting fabricated turns directly into the conversation history array, with no attached document. The classifier has no surface to scan. This is documented as a known limitation, not a hidden gap.

**Classifier coverage summary:**

```
Category 2 (Format Mimicry)    : 1/1 blocked  — risk score 0.96+
Category 3 (Compound Layered)  : 2/2 blocked  — risk score 0.96+
Category 4 (Indirect/Delayed)  : 2/2 blocked  — risk score 0.96+
Category 1 (History Poisoning) : 0/2 — out of classifier scope
```

---

## Demo

The frontend (`frontend/`) provides a split-screen interface built in React:

- **Left panel:** Scenario configuration — choose from 8 pre-loaded scenarios (3 baseline + 5 confirmed red-team attacks), auto-fills the USER_CONTEXT and ATTACHED_PAYLOAD fields
- **Right panel:** Live LLM execution trace — shows the full agent reasoning, tool calls, and tool results as they stream in
- **Top bar:** Toggle between `[ MODE: UNPROTECTED ]` and `[ MODE: PROTECTED ]`
- **Defense Matrix:** Shows the classifier risk score, action taken, and (for red-team scenarios in protected mode) a one-line note explaining why the payload was flagged

The pre-loaded red-team scenarios (`04_FORMAT_MIMICRY` through `08_FALSE_PRIOR_DECISION`) use the exact payload text confirmed to succeed against the unprotected agent, so you can directly observe the before/after of the defense in the same UI.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Agent LLM | `openai/gpt-oss-120b` via Groq API |
| Backend | Python, FastAPI, Uvicorn |
| Classifier | HuggingFace Transformers (DistilBERT-base-uncased), PyTorch |
| Dataset generation | Groq API, scikit-learn (evaluation) |
| Frontend | React 19, Vite, Tailwind CSS v4, Axios |
| Training environment | Kaggle (2×T4 GPU) |

---

## Repository Structure

```
/Agent Sentinel/
├── backend/
│   ├── main.py                         # FastAPI app (/run-unprotected, /run-protected)
│   ├── mockAgent.py                    # Mock payment agent (Groq tool-calling)
│   ├── red_team_advanced.py            # Red-team harness (15 payloads, 4 categories)
│   ├── test_classifier_against_redteam.py  # Classifier coverage test
│   ├── test_injections.py              # Early-stage manual injection tests (reference)
│   ├── red_team_results.json           # Results from the last red-team run
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx                     # Main UI component
│   │   └── ...
│   ├── package.json
│   └── ...
├── scripts/
│   ├── generate_dataset_v1.py          # Initial dataset generator
│   ├── generate_dataset_v2.py          # v2: recall-targeted additions
│   ├── generate_dataset_v3.py          # v3: hard-negative contrastive additions
│   └── synthetic_dataset.jsonl        # Final merged training dataset
├── results/
│   └── agent-sentinel-classifier/     # Fine-tuned DistilBERT weights
│       ├── config.json
│       ├── model.safetensors           # ~255 MB — see Setup below
│       └── tokenizer.json
├── .env                                # Local only — never committed
├── .gitignore
├── LICENSE
└── README.md
```

---

## Setup

### Prerequisites
- Python 3.11+
- Node.js 20+
- A [Groq API key](https://console.groq.com) 

### 1. Clone the repo

```bash
git clone https://github.com/Dnyanesh-29/Agent-Sentinel.git
cd Agent-Sentinel
```

### 2. Set your API key

Create a `.env` file in the project root:

```
GROQ_API_KEY="your_groq_api_key_here"
```

The key is read from the environment it is never hardcoded in any source file.

### 3. Download the classifier

The fine-tuned model weights (`model.safetensors`, ~255 MB) are excluded from this repo via `.gitignore`. Download the file and place it at:

```
results/agent-sentinel-classifier/model.safetensors
```

> **Download link:** *(add your Kaggle output / HuggingFace Hub / Google Drive link here)*

The other files in `results/agent-sentinel-classifier/` (`config.json`, `tokenizer.json`, `tokenizer_config.json`) are small and are committed to the repo.

If the classifier is not present, the backend will warn on startup and the `/run-protected` endpoint will fall back to passing all requests through (no classification). The `/run-unprotected` endpoint always works without it.

### 4. Install backend dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 5. Run the backend

```bash
cd backend
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`. You can verify it at `http://localhost:8000/docs`.

### 6. Install and run the frontend

```bash
cd frontend
npm install
npm run dev
```

The UI will be available at `http://localhost:5173`.

---

## Known Limitations & Future Work

**Conversation-history poisoning (Category 1 attacks)**
The current classifier only scans `attached_content` — the document passed to the agent. Attacks that fabricate prior conversation turns (fake policy exceptions, spoofed tool results in message history) bypass this entirely. Defending against this would require either classifying every incoming message turn, or introducing provenance/signing mechanisms for conversation history so fabricated turns can be detected.

**Dataset scale and diversity**
The training dataset (~315 examples before hard-negative additions) is small by NLP standards. The synthetic generation process is intentionally seeded from documented injection techniques, but the coverage of real-world attack vocabulary is limited. A larger, more diverse dataset — including adversarially generated examples specifically designed to fool the trained model — would improve robustness.

**Single-classifier architecture**
The current defense is a single binary classifier applied at one point in the pipeline. An ensemble approach (multiple classifiers with different training distributions, or a classifier combined with a rule-based layer for explicit tool-call syntax detection) would be harder to fool with distribution shifts.

**Single-turn scope**
The classifier makes its decision per-request, with no memory of previous turns. A multi-turn defense that tracks behavioral patterns across a conversation (e.g., flagging a session where the agent's actions diverge from the user's explicitly stated intent) is a more complete solution.

---

## License

MIT — see [LICENSE](LICENSE).
