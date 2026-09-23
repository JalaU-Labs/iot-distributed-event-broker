# Notebooks

Jupyter notebooks used for experimentation, analysis, and evidence
collection during the lab. Notebooks are not part of the production
package: they are excluded from coverage, linting, and the Docker images.

## Available notebooks

| Notebook                                                     | Purpose                                                                                                                                               |
|--------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------|
| [`01_mqtt_flow_evidence.ipynb`](01_mqtt_flow_evidence.ipynb) | Captures runtime evidence of the MQTT publish/subscribe flow: broker connectivity, `SensorReading` round-trip, QoS comparison, and retained messages. |

## Running the notebooks

### Prerequisites

1. The local MQTT broker must be running:
   ```bash
   make up
   ```
2. The EMQX dashboard should be reachable at <http://localhost:18083>
   (user `admin`, password `public`) to capture visual evidence.

### Starting Jupyter

The project ships `ipykernel` as a development dependency. To launch
Jupyter without polluting the production environment:

```bash
uv run jupyter lab notebooks/
```

Or, if you prefer Jupyter Notebook:

```bash
uv run jupyter notebook notebooks/
```

### Executing a notebook

1. Open the notebook in the browser.
2. Run the cells in order (`Run All Cells` or `Shift+Enter` per cell).
3. The notebook uses top-level `await` and relies on the running event
   loop provided by the Jupyter kernel. Do not call `asyncio.run()` from
   a cell: the kernel already owns the loop.

## Adding a new notebook

1. Create the file under `notebooks/` with a numeric prefix
   (`02_...`, `03_...`) so the execution order is obvious.
2. Keep the first cell as Markdown documenting the objective and the
   prerequisites.
3. Clear all outputs before committing (`Cell` → `All Output` →
   `Clear`) to keep the diff readable.
4. Update the table above with the new entry.

## Why notebooks are excluded from CI

Notebooks are exploratory by nature: they contain a mix of code,
narrative, and generated output. Linting them in CI would either
require ignoring most rules or forbid the exploratory patterns that
make notebooks useful. Instead:

- The **reusable logic** lives in `src/iot_system/` and is covered by
  the test suite.
- The **notebook only orchestrates** that logic and captures evidence.
- The CI pipeline never runs the notebooks; they are a manual
  complement for the lab report.

## Evidence for the lab report

The notebooks in this directory are the primary source of screenshots
and runtime logs used in the lab report. When running them:

1. Capture the EMQX dashboard (Connections, Topics, Messages tabs).
2. Capture the notebook cells with their outputs.
3. Attach the resulting figures or tables to the corresponding section
   of the report.