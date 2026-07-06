# 🙋🏼‍♀️ E-KSIEGOWA PRO (Kasia) — Autonomous AI Accounting & Logistics Agent

Capstone Project for the Kaggle **"5-Day AI Agents" Intensive** > **Track:** Agents for Business  
**Deployment:** Production-ready on Google Cloud Run  

🎥 **Demo Video:** [Watch on YouTube](https://youtube.com/shorts/zbf-DZaYZeg)

---

## 📊 Business Value & Problem Statement
In the construction, field-service, and logistics industries, mobile workforces (builders, drivers, installers) struggle with tedious daily logging of work hours, travel times, and locations. Manual data entry via web forms leads to missing records, errors, delayed payroll calculations, and friction with the back office.

**E-KSIEGOWA PRO (Kasia)** solves this by introducing an autonomous AI Accounting Agent embedded into a Telegram interface. Workers simply dictate or type their shift details in plain, natural language (e.g., *"I worked 9 hours yesterday at SWISS KRONO in Żary"*). Kasia handles the rest: parses the unstructured input, runs deterministic business validation, requests human confirmation, processes financial computations (Gross/Net split, tax adjustments for Poland's *Umowa o Pracę*, and Euro-denominated travel per diems), and securely commits the record to a relational database ledger—all within seconds.

---

## 🏗️ System Architecture & Core Requirements
The project strictly adheres to the high engineering standards of the course, leveraging a modular Python backend separated into isolated Skills, Tools, and Workflows.

```text
[Raw Input] ──> Node: Parser Skill (Gemini 1.5 Flash) 
                      │
                      ▼
                Node: Guardrails Validator
                      │
        ┌─────────────┴─────────────┐
        ▼ (Errors Found)            ▼ (Clear)
   [Halt Graph & Report]      [Freeze State (HITL Interrupt)]
                                    │
                                    ▼
                           [User Approves "Yes"]
                                    │
                                    ▼
                           Node: Database Tool ──> [PostgreSQL / Telegram Text Receipt]
```

### 1. Graph Workflow API (ADK 2.0)
The entire execution lifecycle is modeled as a stateful, directed graph utilizing `StateGraph`. This removes linear script fragility and introduces deterministic state tracking through an explicit `AgentState` object.  
* **Nodes**: `parser` (runs the LLM fact-extraction), `validator` (runs Python-native Guardrails), and `saver` (executes the final DB Tool).  
* **Conditional Edges**: The graph dynamically routes the execution flow based on validation outputs.

### 2. Human-in-the-Loop (HITL)
Payroll edits cannot happen purely autonomously without human sign-off.  
* Kasia compiles the graph with `interrupt_before=["human_review"]`.  
* Upon parsing a clear shift, the graph freezes its exact internal memory state to disk and yields execution back to the bot layer.  
* The bot presents an interactive interface to the worker with clear inline validation options. When the user taps "Confirm (Yes)", the state machine safely resumes from its checkpoint, executing the database write.

### 3. Isolated Agent Skills
* **LLM Parser Skill (`app/skills/parser.py`)**: Powered by the lightning-fast `gemini-2.5-flash` model via Google Cloud Vertex AI.
* **REST API Native Integration**: The agent communicates directly with Vertex AI using raw REST HTTP requests (`aiohttp`) secured by Application Default Credentials (ADC). This eliminates heavy SDK dependencies and API key vulnerabilities, ensuring robust, production-grade latency.
* **Temporal & Native Prompt Engineering**: The skill injects dynamic `current_date` contexts to resolve relative times ("yesterday", "today") deterministically. It incorporates strict negative constraint prompts to prevent translation or transliteration of proprietary entity names (maintaining absolute precision for strings like *SWISS KRONO* or *Żary*).

### 4. Multi-Step Guardrails
Security and data physical limits are strictly enforced inside code nodes rather than raw prompt guessing:  
* **Physics Bounds Check**: Restricts combined work and driving logs to a maximum of 24 hours per calendar date.  
* **State Invariance Check**: Cross-validates status fields. If a worker sets their status to Paid Time Off (`Urlop`) or Sick Leave (`L4`), the guardrail forces hours to zero, eliminating fraudulent overhead logging.

### 5. Managed Cloud Tooling
* **Database Tool (`app/tools/db_tool.py`)**: Wraps atomic, transactional database inputs (`upsert_work_log`) using `asyncpg` to connect with a high-performance cloud PostgreSQL cluster.  
* **Observability & Tracing**: Full integration with LangSmith via environment hooks provides profound telemetry into latency, cost analysis, token consumption, and prompt alignment right in production.

---

## 🛠️ Technical Stack
* **Language**: Python 3.11 (Explicit type hinting, asynchronous architecture)  
* **Frameworks**: Aiogram 3 (Bot Layer), LangGraph / ADK 2.0 (Orchestration Workflow)  
* **AI Engine**: Google Cloud Vertex AI REST API (`gemini-2.5-flash`)
* **Database**: PostgreSQL (Cloud instance via Neon database pooling)  
* **Telemetry**: LangSmith / Native structured logging  
* **Deployment**: Docker containerization, Google Cloud Build, Google Cloud Run (Fully serverless container scaling, Webhook event architecture)  

---

## 🚀 Local Development & Setup
### 1. Clone the Repository:
```bash
git clone https://github.com/BocxodV/Kasia.git
cd Kasia
```

### 2. Environment Configuration:
Create a `.env` file in the root folder:
```env
BOT_TOKEN=your_telegram_bot_token
GOOGLE_APPLICATION_CREDENTIALS=service_account.json
DATABASE_URL=postgresql://user:pass@host/dbname?sslmode=require
WEBHOOK_URL=https://your-cloud-run-url.run.app
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_api_key
LANGCHAIN_PROJECT=kasia-agent
```

### 3. Run Suite via Docker Container:
```bash
docker build -t kasia-agent .
docker run -d --env-file .env -p 8080:8080 kasia-agent
```

### 4. Execute Native Test Pipeline:
```bash
pip install pytest
pytest tests/
```

---

## 🏆 Capstone Compliance Checklist
- [x] ADK 2.0 Directed Graph State Machine implemented in `app/graph.py`.
- [x] Human-in-the-loop State Freezing utilizing programmatic `interrupt_before`.
- [x] Isolated LLM Skill Extraction with rigid `application/json` output gating.
- [x] Deterministic Python Guardrails node mapping against security and data anomalies.
- [x] Production deployment on Google Cloud Run using multi-stage containerization.
- [x] Telemetry metrics verified inside LangSmith.
