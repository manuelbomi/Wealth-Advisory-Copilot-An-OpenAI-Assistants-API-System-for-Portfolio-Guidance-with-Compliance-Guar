# Deploying to OpenShift

The manifests in `deploy/k8s/` are plain Kubernetes and work on OpenShift with a
few OpenShift-specific notes:

## 1. Security Context Constraints (SCC)

OpenShift enforces SCCs more strictly than vanilla Kubernetes. The Dockerfile
already creates and runs as a fixed non-root user (uid 1000), and
`deployment.yaml` sets `runAsNonRoot: true` / `runAsUser: 1000`, so this workload
is compatible with the default `restricted` (or `restricted-v2`) SCC without
needing `anyuid`. If your cluster assigns UIDs dynamically per-namespace, you can
instead drop `runAsUser` entirely and let OpenShift assign a UID from the
namespace's allocated range -- the app does not require a fixed UID, only
non-root.

## 2. Routes instead of Ingress

Expose the Service with an OpenShift `Route` (or `oc expose service`) instead of a
Kubernetes `Ingress`:

```bash
oc apply -f deploy/k8s/configmap.yaml
oc apply -f deploy/k8s/deployment.yaml
oc apply -f deploy/k8s/service.yaml
oc expose service wealth-advisory-copilot
oc get route wealth-advisory-copilot
```

## 3. Build strategy

Either build the image externally (as in `.github/workflows/ci.yml`) and push to
an internal registry / ImageStream, or use an OpenShift `BuildConfig` with a
Docker strategy pointed at this repo's `Dockerfile`. Either way, the resulting
image is what `deployment.yaml`'s `image:` field should reference (update it from
the local `wealth-advisory-copilot:local` tag to your registry path).

## 4. Secrets

If running in live mode, create the API key as a Secret rather than a ConfigMap
value:

```bash
oc create secret generic wealth-advisory-copilot-secrets \
  --from-literal=OPENAI_API_KEY=sk-...
```

`deployment.yaml` already references this Secret via `secretRef` with
`optional: true`, so the Deployment works with or without it -- in its absence the
app runs in offline mock mode, exactly as it does locally.

## 5. Health checks

`/healthz` and `/readyz` are already wired as the liveness/readiness probes in
`deployment.yaml`; no changes needed for OpenShift.
