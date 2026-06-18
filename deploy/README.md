# GrantLayer Deployment

## Helm Chart (Recommended)

### Prerequisites
- Kubernetes 1.25+
- Helm 3.12+
- External PostgreSQL 16 instance
- External Redis 7 instance

### k3s Quickstart

```bash
# Install k3s
curl -sfL https://get.k3s.io | sh -

# Add grantlayer namespace
kubectl create namespace grantlayer

# Create secrets (edit values first!)
kubectl apply -f deploy/k8s/secret.yaml

# Install via Helm
helm install grantlayer deploy/helm/grantlayer/ \
  --namespace grantlayer \
  --set config.runtimeMode=production \
  --set ingress.hosts[0].host=grantlayer.yourdomain.com

# Check rollout
kubectl rollout status deployment/grantlayer-grantlayer-api -n grantlayer
```

### Configuration

All sensitive values are read from a K8s Secret named `grantlayer-secrets`:

| Key | Description |
|-----|-------------|
| `GRANTLAYER_DATABASE_URL` | PostgreSQL DSN |
| `GRANTLAYER_REDIS_URL` | Redis DSN |
| `GRANTLAYER_ADMIN_TOKEN` | Admin API token (long random string) |
| `GRANTLAYER_JWT_SECRET` | JWT signing secret (HS256) or use RS256 keypair |
| `GRANTLAYER_JWT_PRIVATE_KEY` | RSA private key (RS256, optional) |

### Helm Values

See `deploy/helm/grantlayer/values.yaml` for full configuration reference.

Key values:
- `replicaCount.api` — API pod count (default: 2)
- `replicaCount.worker` — ARQ worker count (default: 1)
- `autoscaling.enabled` — Enable HPA (default: true)
- `ingress.hosts[0].host` — Ingress hostname

## Raw Kubernetes Manifests

For environments without Helm:

```bash
kubectl apply -f deploy/k8s/namespace.yaml
kubectl apply -f deploy/k8s/secret.yaml   # edit first!
kubectl apply -f deploy/k8s/deployment.yaml
```

## Docker Compose (Development)

```bash
docker compose up -d
```

See `docker-compose.yml` at the repo root for service definitions.
