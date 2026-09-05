# ResearchPilot AI

### AI-Assisted Research Paper Discovery, Evidence Extraction & Research Gap Analysis

ResearchPilot AI is a research-support platform designed to help researchers discover academic papers, build a selected research corpus, extract structured evidence from papers, and perform conservative cross-paper analysis to identify possible research gaps.

The current version focuses on **deterministic, traceable evidence extraction and conservative research-gap assessment**, while the architecture is designed to support future semantic/AI-assisted analysis.

---

## 🚀 Overview

Finding a research gap manually often requires reading many papers, comparing their topics, methodologies, datasets, findings, limitations, and future-work statements.

ResearchPilot AI simplifies this workflow by providing a structured research workspace where users can:

- Search for academic papers.
- Explore papers and their metadata.
- Select papers for analysis.
- Persist selected papers for reliable analysis.
- Extract structured evidence from available paper text.
- Identify topics, methodologies, datasets, outcomes, findings, limitations, and future work.
- Compare selected papers conservatively.
- Detect possible contradictions.
- Assess whether a defensible shared research gap exists.
- Trace conclusions back to source evidence.

> **Important:** ResearchPilot AI does not claim that the absence of an extracted signal means the paper does not contain that information. The current analysis is intentionally conservative and evidence-grounded.

---

## ✨ Current Features

### 🔎 Research Paper Search

- Search academic literature using OpenAlex.
- Retrieve paper metadata such as:
  - Title
  - Authors
  - Publication year
  - DOI
  - OpenAlex ID
  - Abstract
  - Source URL
- Normalize research results before displaying them.
- Persist paper records for later analysis.

### 📚 Research Workspace

Users can select multiple papers and create a research analysis corpus.

The selected corpus becomes the basis for:

- Evidence extraction
- Cross-paper comparison
- Topic coherence assessment
- Contradiction detection
- Research-gap assessment

### 🧠 Deterministic Evidence Extraction

The current analysis engine extracts evidence using deterministic rules rather than presenting unsupported AI-generated claims.

Evidence categories include:

- Topic
- Methodology
- Dataset / population
- Outcome
- Finding
- Limitation
- Future work

Each extracted item maintains a relationship with its source paper.

### 📊 Cross-Paper Analysis

ResearchPilot AI evaluates the selected corpus for:

- Lexical/topic coherence
- Evidence coverage
- Recurring themes
- Comparable methodologies
- Reported findings
- Contradictions
- Potential research gaps

When papers are not sufficiently comparable, the system deliberately avoids inventing a research gap.

### 🔬 Conservative Research-Gap Detection

The system distinguishes between:

- Evidence signals
- Reported findings
- Candidate gaps
- Defensible research-gap conclusions

If the selected papers do not provide enough comparable evidence, the system reports:

> **No defensible research gap established**

rather than generating a speculative gap.

### 🔗 Traceable Evidence

Analysis results can be traced back to the source paper and extracted evidence.

The system displays:

- Source paper
- Evidence category
- Extracted claim
- Source excerpt
- Extraction confidence

This helps prevent unsupported conclusions.

### 🛡️ Identity & Persistence

ResearchPilot AI maintains persistent paper identity using identifiers such as:

- Internal database ID
- OpenAlex ID
- DOI

Paper Details can be loaded from persisted records rather than depending only on temporary frontend navigation state.

### 🔐 Authentication & Ownership

The application includes authenticated research workflows and ownership boundaries for user-specific research data.

---

# 🏗️ Architecture

ResearchPilot AI follows a frontend/backend architecture.

```text
┌──────────────────────────────┐
│          Frontend            │
│                              │
│ React + TypeScript + Vite    │
│ Tailwind CSS                 │
│ React Router                 │
└──────────────┬───────────────┘
               │
               │ REST API
               ▼
┌──────────────────────────────┐
│           Backend            │
│                              │
│ FastAPI                      │
│ Python                       │
│ SQLAlchemy                   │
│ Analysis Engine              │
└──────────────┬───────────────┘
               │
       ┌───────┴────────┐
       ▼                ▼
┌──────────────┐  ┌──────────────┐
│ PostgreSQL   │  │   OpenAlex   │
│              │  │              │
│ Persistent   │  │ Academic     │
│ paper data   │  │ literature   │
└──────────────┘  └──────────────┘
