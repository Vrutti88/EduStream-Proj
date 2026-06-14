# EduStream — Viva / Q&A Preparation Guide

This maps each syllabus module to **what you built** and **how to answer common
viva questions** about it. Use this alongside `PROJECT_GUIDE.md` (100-mark rubric)
and `EC2_GUIDE.md` (execution steps).

---

## Module 1–2: DevOps Fundamentals & Git/GitHub

**Q: Why did you use Git/GitHub for this project?**
A: Git gives version control — every change to `app.py`, the Jenkinsfile, Terraform
scripts, and Kubernetes manifests is tracked, can be rolled back, and is shared with
collaborators. GitHub also acts as the trigger source for the Jenkins pipeline (push
to `main` → Jenkins build).

**Q: What's in your repository structure?**
A: `app/` (Flask source + tests), `jenkins/Jenkinsfile`, `terraform/`, `k8s/`,
`monitoring/`, `elk/`, `vault/`, `diagrams/`, `docs/` — one repo, organized by
DevOps concern, matching the architecture diagram.

**Q: What does CI mean?**
A: Continuous Integration — every code change is automatically built and tested
(Jenkins `Checkout` → `Install & Unit Test` stages) so integration issues are caught
early, before deployment.

---

## Module 3: Docker & Containerization

**Q: Why Docker?**
A: "Works on my laptop, fails on the server" — Docker packages the Flask app, its
Python dependencies, and runtime into one image (`app/Dockerfile`) so it behaves
identically on a developer laptop, EC2, or inside Kubernetes.

**Q: Walk me through your Dockerfile.**
A: Base image `python:3.12-slim` → install `requirements.txt` → copy app code →
expose port 5000 → `HEALTHCHECK` hits `/health` → run with `gunicorn` (production
WSGI server, not the Flask dev server).

**Q: How do you run it?**
```bash
docker build -t edustream:latest .
docker run -d -p 5000:5000 --name edustream edustream:latest
curl http://localhost:5000/health
```

**Q: What is `docker-compose.yml` for?**
A: It spins up the entire local stack — the app plus Prometheus, Grafana,
Elasticsearch, Logstash, Kibana, and Vault — with one command, useful for local
demos before deploying to AWS.

---

## Module 4: Jenkins CI/CD

**Q: Describe your pipeline stages.**
A: Checkout (GitHub) → Install & Unit Test (pytest) → SAST (Bandit) → Build Docker
image → Trivy vulnerability scan → Push to ECR → Terraform apply (infra) → Fetch
secrets from Vault → Deploy to Kubernetes → Smoke test → automatic rollback on
failure (`kubectl rollout undo`).

**Q: What's the difference between CI and CD here?**
A: CI = build + test + scan (first 5 stages). CD = the rest — provisioning infra,
deploying to Kubernetes, and validating the live deployment.

**Q: How is the pipeline triggered?**
A: A GitHub webhook fires on every push to `main`, triggering the Jenkins job
configured with "Pipeline script from SCM" pointing at `jenkins/Jenkinsfile`.

**Q: What happens if the deployment fails?**
A: The `post { failure { ... } }` block runs `kubectl rollout undo
deployment/edustream`, automatically reverting to the last healthy ReplicaSet —
this directly satisfies the "deployment delays / failed deploys" problem statement.

---

## Module 5: Terraform / Infrastructure as Code

**Q: Why Terraform instead of clicking around the AWS console?**
A: Infrastructure as Code — repeatable, version-controlled, reviewable via pull
requests, and identical every time you `terraform apply`. No "it worked when I
clicked it differently last time."

**Q: What resources does your Terraform create?**
A: VPC with 2 public + 2 private subnets across 2 AZs (`vpc.tf`), an EKS cluster +
managed node group with IAM roles (`eks.tf`), an RDS PostgreSQL instance
(Multi-AZ, automated backups) and an S3 bucket with versioning + cross-region
replication, plus CloudWatch alarms and a log group (`rds_s3_cloudwatch.tf`).

**Q: What are `terraform init`, `plan`, and `apply`?**
A: `init` downloads providers and sets up the backend (S3 remote state); `plan`
shows what will change without applying it; `apply` actually creates/updates the
resources in AWS.

**Q: Where is your Terraform state stored, and why does that matter?**
A: In an S3 bucket (`edustream-terraform-state`) with versioning enabled — so state
isn't lost if a local machine dies, and multiple team members/CI runs can share it
safely.

---

## Module 6: Kubernetes

**Q: Why Kubernetes for this problem statement?**
A: The problem statement says "100 students works, 10,000 crashes the server."
Kubernetes solves this with the Horizontal Pod Autoscaler (`k8s/hpa.yaml`):
minReplicas 2, maxReplicas 6, scaling on CPU/memory utilization > 70%.

**Q: Explain Pod, Deployment, Service, and HPA in your project.**
A:
- **Pod** = one running container of the EduStream Flask app.
- **Deployment** (`k8s/deployment.yaml`) = keeps 2 replicas running, defines
  resource requests/limits, readiness/liveness probes against `/health`.
- **Service** (`k8s/service.yaml`) = stable internal endpoint (`ClusterIP`) + an
  Ingress (ALB) exposing it externally.
- **HPA** = watches CPU/memory and scales the Deployment's replica count between
  2 and 6 automatically.

**Q: How do readiness/liveness probes help availability?**
A: If a pod's `/health` check fails, Kubernetes stops sending traffic to it
(readiness) and restarts it if it stays unhealthy (liveness) — this is the
mechanism behind "High Availability" in the problem statement.

**Q: How are secrets and config separated?**
A: `configmap.yaml` holds non-sensitive settings (FLASK_ENV, APP_NAME); `secret.yaml`
+ Vault Agent injection annotations on the Deployment handle sensitive values
(DB credentials) — never hardcoded in the image or manifests.

---

## Module 7: Monitoring (Prometheus + Grafana)

**Q: How does Prometheus get data from your app?**
A: `prometheus-flask-exporter` exposes a `/metrics` endpoint on the Flask app
(request counts, latency histograms). `monitoring/prometheus/prometheus.yml`
scrapes it every 15 seconds, plus auto-discovers any pod in the cluster annotated
with `prometheus.io/scrape: "true"`.

**Q: What alerts have you configured?**
A: `monitoring/prometheus/alerts.yml` — `AppDown` (no scrape target for 2 min),
`HighErrorRate` (>5% 5xx responses over 5 min), `HighLatency` (95th percentile
> 1s over 5 min).

**Q: What does Grafana show?**
A: `monitoring/grafana/edustream-dashboard.json` — request rate, 95th percentile
latency, pod CPU usage, pod memory usage, and an up/down stat panel, sourced from
the Prometheus datasource (`datasource.yml`).

**Q: How does this solve "Monitoring Issues" from the problem statement?**
A: Instead of "server crashed, nobody knows why," an on-call engineer opens
Grafana, sees a CPU/latency spike or a Prometheus alert fired, and immediately
knows which pod/metric to investigate.

---

## Module 8: ELK Stack (Logging)

**Q: What's the log flow?**
A: Application/container logs → **Filebeat** (DaemonSet on every node,
`elk/filebeat.yml`) → **Logstash** (`elk/logstash.conf`, parses and tags logs) →
**Elasticsearch** (stores/indexes as `edustream-logs-*`) → **Kibana** (search/visualize).

**Q: Why not just `kubectl logs`?**
A: `kubectl logs` only shows logs for one pod, and they're lost when the pod is
deleted. ELK centralizes logs from all pods/replicas, persists them, and lets you
search across the whole platform (e.g., "find every 'login failed' error in the
last hour across all pods").

---

## Module 9: Vault (Secrets Management)

**Q: What secrets does Vault manage here?**
A: The RDS database username/password and host, stored at
`secret/edustream/db` (KV v2 engine).

**Q: How does the app get the secret without it being in the code or image?**
A: The Kubernetes Deployment has Vault Agent Injector annotations
(`vault.hashicorp.com/agent-inject: "true"`, role `edustream`). On pod startup,
the Vault Agent sidecar authenticates via the Kubernetes auth method, reads
`secret/data/edustream/db`, and writes it to a file inside the pod
(`/vault/secrets/db-creds`) — the app never sees a hardcoded password.

**Q: What's the access policy?**
A: `vault/vault-policy-edustream.hcl` grants only `read`/`list` on
`secret/data/edustream/*` — least-privilege, the app can't read other apps' secrets.

---

## Module 10: DevSecOps (SAST/DAST)

**Q: Where is security scanning in your pipeline?**
A: **SAST**: the Jenkins "Static Code Analysis" stage runs **Bandit** against the
Flask source, looking for issues like hardcoded passwords or SQL injection
patterns. **Image scanning**: **Trivy** scans the built Docker image for
HIGH/CRITICAL CVEs before it's pushed to ECR.

**Q: What's the difference between SAST and DAST?**
A: SAST analyzes source code without running it (Bandit, here). DAST tests the
*running* application (e.g., hitting live endpoints to find vulnerabilities) —
not implemented in this project but would slot in as an additional pipeline stage
against the deployed `/health`/API endpoints.

---

## Module 11: Disaster Recovery

**Q: What's your RTO/RPO?**
A: RTO (Recovery Time Objective) = 30 minutes; RPO (Recovery Point Objective) =
15 minutes, backed by RDS continuous backups/snapshots and S3 versioning + cross-
region replication. Full details: `docs/disaster-recovery-plan.md`.

**Q: Walk me through recovering from a pod crash vs. a region failure.**
A:
- **Pod crash**: Kubernetes liveness probe restarts it automatically; if it
  crash-loops, `kubectl rollout undo` reverts to the last good image.
- **Node failure**: EKS Auto Scaling replaces the node; pods reschedule
  (replicas=2 minimum keeps the app up).
- **RDS failure**: Multi-AZ automatic failover (60-120s); for a full region
  failure, restore the latest cross-region snapshot and update the Vault secret
  with the new DB host.
- **Region failure**: re-run `terraform apply` in the DR region, restore RDS/S3
  from backups, re-apply Vault config and K8s manifests, update DNS.

**Q: How did you validate recovery (not just write a plan)?**
```bash
kubectl delete pod -n edustream -l app=edustream   # simulate crash
kubectl rollout undo deployment/edustream -n edustream  # simulate rollback
aws rds describe-db-snapshots --db-instance-identifier edustream-db
```

---

## Module 12: High Availability

**Q: How is HA achieved end-to-end?**
A:
- **App tier**: 2+ pod replicas behind a Service/Ingress; HPA scales up under load.
- **Database tier**: RDS Multi-AZ — automatic standby failover.
- **Storage tier**: S3 versioning + cross-region replication.
- **Network tier**: subnets across 2 Availability Zones.

If any single component fails, users don't notice — exactly the "3 pods, 1 down,
2 still serving traffic" example from your guide.

---

## End-to-End Flow (the "elevator pitch")

> A developer pushes code to GitHub. Jenkins automatically checks it out, runs
> unit tests, scans the code (Bandit) and the Docker image (Trivy), builds and
> pushes the image to ECR, applies Terraform to keep AWS infrastructure (EKS, RDS,
> S3, IAM, CloudWatch) up to date, pulls database credentials from Vault, and
> rolls out the new version to Kubernetes with zero downtime. Once live, students
> and instructors use EduStream to create courses, schedule classes, and enroll —
> while Prometheus and Grafana watch performance, the ELK stack centralizes logs,
> and Kubernetes' HPA scales pods automatically if thousands of students join at
> once. If anything fails — a pod, a node, the database, or an entire region — the
> disaster recovery plan and Multi-AZ/HA design bring it back within the RTO/RPO
> targets.

---

## DORA Metrics (for documentation / discussion)

| Metric | How it's measured in this project |
|---|---|
| Deployment Frequency | Number of successful Jenkins pipeline runs to `main` per week |
| Lead Time for Changes | Time from `git commit` to successful `kubectl rollout status` |
| Change Failure Rate | Failed Jenkins builds ÷ total builds |
| Time to Restore Service | Time for `kubectl rollout undo` + smoke test to pass |
