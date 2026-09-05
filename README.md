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

---

# 📁 Project Structure

```text
ResearchPilot-AI/
│
├── ai/
│   └── AI-related components and experiments
│
├── backend/
│   ├── app/
│   │   ├── analysis/
│   │   ├── api/
│   │   ├── models/
│   │   ├── repositories/
│   │   ├── schemas/
│   │   └── services/
│   │
│   └── tests/
│
├── frontend/
│   └── src/
│       ├── features/
│       ├── components/
│       └── pages/
│
├── database/
│   └── database configuration and migrations
│
├── docs/
│   └── project documentation
│
├── infrastructure/
│   └── deployment and infrastructure configuration
│
├── scripts/
│   └── utility and development scripts
│
├── assets/
│   └── project assets
│
├── .github/
│   └── GitHub configuration
│
├── .gitignore
└── README.md
🛠️ Technology Stack
Frontend
React
TypeScript
Vite
Tailwind CSS
React Router
Backend
Python
FastAPI
SQLAlchemy
Database
PostgreSQL
Research Data
OpenAlex API
Testing
Pytest
Frontend automated tests
TypeScript/build validation
Linting
🚀 Getting Started
Prerequisites

Make sure the following are installed:

Python 3.11+
Node.js
npm
PostgreSQL
Git
1. Clone the repository
git clone https://github.com/Mubarak1712/ResearchPilot-AI.git
cd ResearchPilot-AI
2. Backend setup
cd backend

Create and activate a virtual environment:

Windows
python -m venv .venv
.\.venv\Scripts\Activate.ps1

Install dependencies:

pip install -r requirements.txt

Create your environment file:

backend/.env

Configure the required database and application settings according to the project's environment configuration.

Start the FastAPI backend:

uvicorn app.main:app --reload
3. Frontend setup

Open another terminal:

cd frontend
npm install
npm run dev

The frontend will normally be available at:

http://127.0.0.1:5173
🔎 How ResearchPilot AI Works

The current workflow is:

Search Academic Papers
        ↓
Explore Paper Metadata
        ↓
Select Research Papers
        ↓
Create Research Analysis
        ↓
Persist Paper Identity
        ↓
Extract Evidence
        ↓
Classify Evidence
        ↓
Compare Selected Papers
        ↓
Evaluate Corpus Coherence
        ↓
Check Contradictions
        ↓
Assess Possible Research Gap
        ↓
Generate Conservative Conclusion
📖 Analysis Methodology

The current analysis engine uses a deterministic methodology:

5C-5E-deterministic-v1

The system prioritizes:

Traceability
Reproducibility
Conservative interpretation
Source-grounded evidence
Paper identity consistency
Explicit separation between evidence and conclusions

The system does not treat keyword matches as scientific conclusions.

For example:

Detected signal
      ↓
Source evidence
      ↓
Evidence category
      ↓
Cross-paper comparison
      ↓
Confidence / comparability check
      ↓
Research-gap assessment

A research gap is reported only when the available evidence supports a defensible conclusion.

📊 Current Analysis Capabilities

ResearchPilot AI can currently analyze selected papers for:

Research topics
Methodologies
Datasets / populations
Outcomes
Reported findings
Limitations
Future work
Topic coherence
Cross-paper relationships
Contradictions
Candidate research gaps

The system can also explain why a particular research-gap conclusion was reached through its reasoning trail.

📌 Example Analysis

For a selected corpus, the system may produce a conclusion such as:

No defensible research gap established

This means that the selected papers did not provide sufficiently comparable evidence for the system to responsibly identify a shared unresolved research question.

This is an intentional design choice.

ResearchPilot AI prefers:

Evidence-based uncertainty over unsupported conclusions.

🧪 Testing

The project includes automated backend and frontend validation.

Backend tests:

cd backend
pytest -q

Frontend tests:

cd frontend
npm test

Frontend build:

npm run build

Frontend lint:

npm run lint

The current implementation has been validated with automated tests covering research search, analysis APIs, evidence extraction, paper identity, persistence, and frontend behavior.

⚠️ Current Limitations

The current version is intentionally conservative.

Current limitations include:

Evidence extraction is primarily deterministic.
Keyword/topic matching is not equivalent to semantic understanding.
Missing extracted evidence does not prove that information is absent from a paper.
Research-gap detection depends on the selected corpus.
The current system does not perform a comprehensive literature review automatically.
Semantic similarity and deeper scientific reasoning are not yet foundational components.
Analysis quality depends on the amount and quality of available paper text.

Therefore, ResearchPilot AI should be considered a research-support tool, not a replacement for expert literature review.

🔮 Future Roadmap

The current deterministic foundation is designed to support future development.

Planned improvements include:

🔎 Advanced Paper Discovery
Search papers by publication year
Filter recent papers
Filter older foundational papers
Sort by citation count
Compare highly cited and recent research
Filter by research field
Filter by publication type
Improve relevance ranking
📊 Research Comparison

Future versions can provide quantitative comparisons such as:

Citation comparison
Publication-year comparison
Methodology comparison
Dataset comparison
Evaluation-metric comparison
Finding/outcome comparison
Research-trend analysis
🧠 Semantic Research Analysis

Future development may introduce:

Semantic similarity
Embedding-based paper comparison
Research-question extraction
Methodology similarity
Semantic contradiction detection
Deeper cross-paper synthesis
LLM-assisted interpretation with evidence grounding
🎯 Advanced Research-Gap Detection

Future versions may investigate:

Missing methodological combinations
Under-studied populations
Unexplored datasets
Conflicting findings
Temporal research gaps
Under-explored research questions
Opportunities suggested by multiple papers
📈 Research Intelligence

Future versions may also provide:

Research trend visualization
Citation trends
Topic evolution
Emerging research areas
Recent-vs-foundational paper comparison
Research landscape visualization
🔐 Security & Privacy

ResearchPilot AI is designed to keep user-specific research data separated through authenticated workflows and ownership boundaries.

Sensitive configuration values such as:

Database credentials
API keys
Authentication secrets
Environment variables

should never be committed to the repository.

Environment files are excluded through .gitignore.

🤝 Contributing

ResearchPilot AI is currently under active development.

Future contributions may include:

Improved evidence extraction
Better semantic analysis
Research visualization
Search improvements
Testing
Documentation
Performance improvements
📄 License

This project is currently intended as a personal academic/software project.

License information will be added when the project is formally released under an open-source license.

👨‍💻 Author

Mubarak Khan

B.Tech Computer Science Engineering (AI)

ResearchPilot AI is developed as an academic and engineering project exploring how AI-assisted tools can support academic research, literature discovery, evidence extraction, and research-gap analysis.

⭐ Project Status

Current Status: Active Development

The current release provides a working foundation for:

Academic paper discovery
Persistent research corpus creation
Deterministic evidence extraction
Cross-paper analysis
Conservative research-gap assessment
Traceable evidence
Authenticated research workflows

The architecture is designed to evolve toward more advanced semantic and AI-assisted research intelligence.

**And yes — later you absolutely can put screenshots in the README.** In fact, for your project I recommend **3–5 screenshots** showing the actual workflow: Search → Selected papers → Analysis → Evidence → Gap conclusion. GitHub supports relative image paths in README files. :contentReference[oaicite:1]{index=1}

But **don't add the screenshots yet** if you're still preparing the repository. First get the code pushed cleanly; then we can make a `docs/screenshots/` folder and add the visuals neatly.
