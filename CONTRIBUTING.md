# Contributing to ops-platform

Thank you for your interest in contributing. This document covers the
development setup, coding standards, and pull request process.

---

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.11+ | Exporter, CDK stacks |
| Go | 1.22+ | Kubernetes operator |
| Docker | 24+ | Container builds |
| Node.js | 20+ | AWS CDK CLI |
| helm | 3.12+ | Chart linting |
| kubectl | 1.29+ | Operator local testing |
| minikube | 1.33+ | Local Kubernetes cluster |
| opa | 0.65+ | Policy testing |

## Setup

```bash
# Clone the repo
git clone https://github.com/kumarrajapuvvalla-bit/ops-platform.git
cd ops-platform

# Python setup
python -m venv .venv
source .venv/bin/activate
pip install -r exporter/requirements.txt
pip install -r infrastructure/requirements.txt

# Go setup
cd operator && go mod download && cd ..

# CDK setup
npm install -g aws-cdk

# Start local observability stack
docker-compose up -d
# Grafana: http://localhost:3000 (admin/admin)
# Prometheus: http://localhost:9090
# Exporter metrics: http://localhost:8000/metrics
```

## Running Tests

```bash
# Python unit tests
pytest exporter/tests/ -v

# CDK assertion tests
pytest infrastructure/tests/ -v

# Go tests with race detector
cd operator && go test ./... -v -race

# Helm lint
helm lint helm/ops-platform/
helm lint helm/ops-platform/ -f helm/ops-platform/values-dev.yaml

# OPA policy tests
opa test policies/ -v
```

## Commit Message Convention

This project follows [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short description>

[optional body]

[optional footer]
```

**Types:**

| Type | When to use |
|------|-------------|
| `feat` | New feature or capability |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `refactor` | Code restructure, no behaviour change |
| `test` | Adding or fixing tests |
| `ci` | CI/CD pipeline changes |
| `chore` | Dependency updates, config changes |
| `perf` | Performance improvement |

**Scopes:** `exporter`, `operator`, `infra`, `helm`, `ansible`, `obs`, `policy`, `docs`

**Examples:**
```
feat(operator): add exponential backoff to reconcile retry logic
fix(exporter): handle boto3 ClientError when ECS cluster is empty
docs(adr): add ADR-004 for Prometheus remote write configuration
ci: add Dependabot for Go module updates
```

## Pull Request Process

1. **Fork and branch** — branch from `main` using the convention `type/short-description`
   ```bash
   git checkout -b feat/operator-exponential-backoff
   ```

2. **Write tests** — all new code must have corresponding tests
   - Python: pytest in `exporter/tests/` or `infrastructure/tests/`
   - Go: `*_test.go` alongside the source file
   - Policies: OPA test files in `policies/tests/`

3. **Run all checks locally** before pushing:
   ```bash
   # Python
   pytest exporter/tests/ -v
   ruff check exporter/ --select E,F,W

   # Go
   cd operator && go vet ./... && go test ./... -race

   # Helm
   helm lint helm/ops-platform/

   # CDK
   cd infrastructure && cdk synth --context environment=dev
   ```

4. **Submit PR** with:
   - Clear title following commit convention
   - Description explaining *why*, not just *what*
   - Link to any related issue or ADR

5. **ADR for significant decisions** — if your PR introduces a significant
   architectural choice, add an ADR to `docs/adr/` as part of the same PR.

## Code Standards

### Python
- Type hints on all function signatures
- Docstrings on all classes and public methods
- `ruff` for linting (configured in `pyproject.toml`)
- `mypy` for type checking

### Go
- Standard Go formatting (`gofmt`)
- All exported functions must have godoc comments
- Use structured logging (`slog`) not `fmt.Printf`
- Use `context.Context` as first parameter on all functions that may block

### Helm
- All templates must have `{{- include "ops-platform.labels" . | nindent 4 }}`
- No hardcoded values — everything configurable via `values.yaml`
- Resource limits required on all containers

### Commit hygiene
- One logical change per commit
- No merge commits — rebase before merge
- Squash fixup commits before PR review
