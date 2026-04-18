# Multi-stage Dockerfile for Self-Healing Operator
#
# Stage 1: golang:1.22 builder — compiles a statically linked binary
# Stage 2: gcr.io/distroless/static — no shell, no package manager,
#           minimal attack surface, non-root by default

# ── Stage 1: Builder ──────────────────────────────────────────────────────
FROM golang:1.26 AS builder

WORKDIR /workspace

# Cache dependencies layer separately
COPY go.mod go.mod
RUN go mod download

# Copy source and build a static binary
COPY . .
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 \
    go build \
    -ldflags="-s -w" \
    -trimpath \
    -o manager \
    .


# ── Stage 2: Distroless runtime ──────────────────────────────────────────────
# gcr.io/distroless/static: no shell, no libc, no apt, minimal CVEs
# Runs as nonroot (uid 65532) by default — no USER directive needed
FROM gcr.io/distroless/static:nonroot

WORKDIR /

# Copy only the compiled binary from the builder stage
COPY --from=builder /workspace/manager /manager

# Metrics endpoint: 8080
# Health probe endpoint: 8081
EXPOSE 8080 8081

ENTRYPOINT ["/manager"]
