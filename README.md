# Data-Pilot

An interactive, terminal-first data-science copilot powered by the `openai-agents` runtime. Data-Pilot wraps an opinionated analysis agent ("Vanessa") with a rich CLI, a curated toolbelt for filesystem, dataset, and automation tasks, and a sandboxed workspace under `./root` for reproducible experiments.

---

## Why Data-Pilot?

- **Single command workflow** – launch `main.py` and immediately chat with an agent that can plan analyses, execute Python, and summarize results.
- **Dataset-first guardrails** – the agent insists on a dataset path under `./root` before taking action, ensuring provenance and reproducibility.
- **Batteries-included tooling** – filesystem management, dataset profiling, automated baselines, and arbitrary Python execution are exposed as safe tools.
- **Beautiful terminal UX** – the Rich-powered CLI streams reasoning, tool calls, and responses with slash commands for help, history, and clearing state.
- **Extensible agent stack** – plug in new tools or handoff agents with a few lines of configuration thanks to the `my_agent` wrapper.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [Running the CLI](#running-the-cli)
6. [Working with Datasets](#working-with-datasets)
7. [Available Tools](#available-tools)
8. [Automation Workflow](#automation-workflow)
9. [Extending the Agent](#extending-the-agent)
10. [Troubleshooting](#troubleshooting)
11. [Project Roadmap](#project-roadmap)
12. [License](#license)

---

## Architecture Overview

```
Data-Pilot/
├── main.py                  # Async entrypoint that launches the CLI and agent
├── cli/
│   └── ui.py                # Rich UI, slash commands, streaming visualizer
├── config/
│   └── agent_config.py      # Version, turn limits, and environment-based config
├── my_agents/
│   ├── base_agent.py        # `my_agent` wrapper around openai-agents runtime
│   └── analysis_agent/      # Vanessa's prompt, tools, and handoff metadata
├── tools/
│   ├── data_tools.py        # Dataset overview/quality/correlation reports
│   ├── automation_tools.py  # Automated modeling pipeline + artifact logging
│   ├── filesystem_tools.py  # Sandboxed file ops within ./root
│   ├── misc_tools.py        # `execute_code` + timestamps
│   └── utils/               # Sandbox, dataset, and code-execution helpers
├── root/                    # User-editable sandbox for datasets + outputs
└── README.md
```

**Control Flow**

1. `main.py` runs `cli.ui.run_cli`, which greets the user and starts an interactive loop.
2. The CLI delegates user turns to `analysis_agent.agent`, an instance of `my_agent` configured with:
   - The Vanessa system prompt (`analysis_agent/prompt.py`).
   - Toolbelt aggregated from `misc`, `filesystem`, `data`, and `automation` modules.
   - A `LitellmModel` that bridges to the configured Cerebras/OpenAI-compatible endpoint.
3. During a run, the CLI streams reasoning tokens, tool calls, and handoffs, while enforcing `MAX_TURNS` (default: 20).
4. Any artifacts or datasets are manipulated inside `./root`, preventing accidental edits to repository code.

---

## Prerequisites

- **Python** ≥ 3.10.
- **pip** or **uv**.
- An API key that is compatible with the `openai-agents` SDK (the default config expects Cerebras).
- (Optional) `uv` 0.4+ for fast dependency syncs.

---

## Installation

> All commands assume a Windows PowerShell terminal. Adjust paths if you are on macOS/Linux.

```powershell
# Clone the repository
# git clone https://github.com/<you>/Data-Pilot.git
# cd Data-Pilot

# Create & activate a virtual environment
python -m venv .venv
.\.venv\Scripts\activate

# Install dependencies (choose one)
pip install -r requirements.txt
# or
uv sync
```

---

## Configuration

1. Copy `.env.example` to `.env`
2. Populate the variables:
   - `CEREBRAS_BASE_URL` – e.g., `https://api.cerebras.ai/v1` or another OpenAI-compatible endpoint.
   - `ANALYSIS_API_KEY` – the API token authorized to call the selected model.

At runtime `config/agent_config.py` reads these values and injects them into the `LitellmModel` wrapper.

---

## Running the CLI

```bash
python main.py
```

What you will see:

- A Rich splash screen.
- Prompted user input area. Vanessa immediately asks for:
  1. Dataset path (relative to `./root`).
  2. Business objective, target variable, success criteria, output expectations, and constraints.
- Streaming output panes showing reasoning, tool invocations, and responses.

### Slash Commands

| Command        | Aliases                | Description                          |
| -------------- | ---------------------- | ------------------------------------ |
| `/help`        | `/h`                   | Display available commands           |
| `/history`     | `/hs`                  | Show current conversation transcript |
| `/clear`       | `/c`                   | Clear the screen                     |
| `/clear_history` | `/ch`                | Erase stored conversation memory     |
| `/quit`        | `/exit`, `/q`          | Exit the program gracefully          |

Keyboard shortcut **Ctrl+X** interrupts a streaming response.

---

## Working with Datasets

- Place datasets under the repository's `root/` directory. Anything outside that sandbox is inaccessible to the agent.
- Supported formats: CSV, TSV, TXT, JSON/NDJSON, Parquet, Excel (`.xlsx/.xls`).
- Refer to files via relative paths like `data/loans.csv` (which resolves to `root/data/loans.csv`).
- Generated outputs (cleaned data, charts, models) should be written under `root/analysis_outputs/<session>` - the prompt and automation tools reinforce this convention.

### Typical Session Flow

1. **Clarify scope** – provide dataset path + business question.
2. **Planning** – Vanessa drafts an ingestion → EDA → modeling roadmap.
3. **Execution** – The agent runs Python via the `execute_code` tool, logging XML-formatted stdout/stderr for transparency.
4. **Reporting** – Insights, metrics, and saved artifacts are summarized back to you along with next steps/questions.

---

## Available Tools

| Module | Tool(s) | Highlights |
| ------ | ------- | ---------- |
| `tools.misc_tools` | `get_current_datetime`, `execute_code` | Timestamping plus sandboxed Python runner with timeout + XML result payloads. |
| `tools.filesystem_tools` | `list_files`, `read_file`, `write_file`, `create_directory`, `delete_*`, `move_file`, `copy_file`, `edit_file_section`, `append_to_file` | Guarded by a sandbox (`tools/utils/filesystem.py`) to prevent escaping `./root`. |
| `tools.data_tools` | `dataset_overview`, `dataset_quality_report`, `dataset_correlation_report` | Quick EDA snapshots: schema, missingness, cardinality, numeric/categorical stats, and correlations. |
| `tools.automation_tools` | `automated_modeling_workflow` | End-to-end baseline training (preprocessing pipelines, RandomForest/Linear/Logistic baselines, metrics, artifact logging). |

Each tool is registered with `agents.function_tool`, making it callable by the agent planner. Add new tools by defining a Python callable and appending it to the relevant tool list before constructing the agent.

---

## Automation Workflow

`automated_modeling_workflow` delivers a turnkey baseline modeling pass:

1. Loads the dataset (with optional sampling) and verifies the target column exists.
2. Splits numeric vs categorical features, imputes missing values, scales/encodes, and builds a `ColumnTransformer` pipeline.
3. Trains Logistic/Linear Regression plus Random Forest variants depending on the inferred problem type.
4. Logs metrics (accuracy, precision, recall, F1, ROC-AUC for classification; R²/MAE/RMSE for regression) into `root/analysis_outputs/<timestamp>/metrics.json`.
5. Returns a markdown summary with feature space metadata and artifact pointers.

Customize behavior through arguments like `test_size`, `random_state`, `artifact_subdir`, or by editing `tools/automation_tools.py`.

---

## Extending the Agent

1. **New tool** - implement a function, decorate with `@function_tool`, and add it to one of the tool lists (or create a new list) before instantiating the agent.
2. **New agent** - define a prompt + config under `my_agents/<name>/`, register it inside `config/agent_config.py`, and instantiate via `my_agent`.
3. **Handoffs** - call `analysis_agent.add_handoffs(other_agent)` to enable multi-agent collaboration while preserving Vanessa as the orchestrator.
4. **UI tweaks** - customize `cli/ui.py` to alter the streaming layout, add telemetry, or integrate additional slash commands.

Because `my_agent` automatically merges tools and handoff metadata into the underlying `Agent` from `openai-agents`, most changes involve minimal code.

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
| ------- | ------------ | --- |
| `dataset_overview failed: Dataset not found` | Path not under `./root` or typo | Confirm the file exists inside `root/` and reference it relatively (e.g., `data/file.csv`). |
| `Unsupported dataset format` | Extension not in the supported list | Convert the file to CSV/Parquet/Excel or extend `SUPPORTED_DATASET_EXTENSIONS`. |
| `automated_modeling_workflow failed: target column ... missing` | Wrong column name | Run `dataset_overview` to inspect columns, then rerun with the correct `target_column`. |
| `pandas is required for dataset tooling` | Pandas/pyarrow/openpyxl missing | Reinstall dependencies via `pip install -r requirements.txt` (ensure virtualenv is active). |
| CLI exits immediately with `System error` | Missing/invalid API credentials | Re-check your `.env` values and confirm the account has quota for the selected model. |

Enable verbose debugging by adding prints/logging in the relevant tool module; the CLI surfaces tracebacks directly in the streaming pane.

---

Contributions are welcome—open discussions or PRs targeting any roadmap item.

---

## License

MIT