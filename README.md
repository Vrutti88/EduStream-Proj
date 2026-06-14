# EduStream — Virtual Learning Platform
### DevOps Case Study: Full Application + DevOps Lifecycle

This project contains a working **Virtual Learning Platform** (EduStream) — supporting
**courses, classes, and student enrollment** — plus the complete DevOps toolchain around
it: Git, Docker, Jenkins CI/CD, Terraform (AWS), Kubernetes, Prometheus/Grafana monitoring,
ELK logging, Vault secrets management, architecture/deployment diagrams, and a disaster
recovery plan.

---

## 1. Project Structure

```
virtual-classroom/
├── app/                     # Flask web app (EduStream)
│   ├── app.py
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── .dockerignore
│   ├── tests/test_app.py
│   └── templates/index.html
├── docker-compose.yml       # Local full-stack environment
├── jenkins/Jenkinsfile      # CI/CD pipeline
├── terraform/               # AWS infra: EKS, RDS, S3, IAM, CloudWatch
├── k8s/                      # Kubernetes manifests
├── monitoring/
│   ├── prometheus/          # prometheus.yml, alerts.yml
│   └── grafana/             # datasource + dashboard JSON
├── elk/                      # Logstash + Filebeat config
├── vault/                     # Vault policy + setup script
├── diagrams/                  # Architecture & deployment SVGs
└── docs/disaster-recovery-plan.md
```

---

## 2. The Application — EduStream

A Flask + SQLite virtual learning platform with three core entities: **courses**,
**classes** (live sessions belonging to a course), and **enrollments** (students
registered to a course).

**Features:**
- Create a course (`POST /api/courses`) — title, instructor, description
- Browse the course catalog (`GET /api/courses`) — shows class count & enrolled count per course
- Schedule a class/live session under a course (`POST /api/courses/<id>/classes`)
- View a course's classes (`GET /api/courses/<id>/classes`)
- Student joins a live class, marking it "live" (`POST /api/classes/<id>/join`)
- Enroll a student in a course (`POST /api/courses/<id>/enroll`)
- View enrolled students for a course (`GET /api/courses/<id>/students`)
- Live platform stats — total courses, classes, enrollments, live sessions (`GET /api/stats`)
- Health check for Kubernetes probes (`GET /health`)
- Prometheus metrics endpoint (`/metrics`, via `prometheus-flask-exporter`)
- Professional dark-themed single-page dashboard (`templates/index.html`) with a
  course catalog, course detail view (classes + enrollment side by side), and an
  infrastructure/platform tile grid
- Unit tests covering courses, classes, enrollment, and stats (`app/tests/test_app.py`)

### Run locally
```bash
cd app
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 app.py
# Visit http://localhost:5000
```

### Try the API
```bash
# Create a course
curl -X POST http://localhost:5000/api/courses -H "Content-Type: application/json" \
  -d '{"title":"Introduction to Algebra","instructor":"Ms. Iyer","description":"Foundations of algebra"}'

# List courses
curl http://localhost:5000/api/courses

# Schedule a class under course 1
curl -X POST http://localhost:5000/api/courses/1/classes -H "Content-Type: application/json" \
  -d '{"title":"Lecture 1 - Variables","start_time":"2026-06-20T10:00"}'

# Enroll a student in course 1
curl -X POST http://localhost:5000/api/courses/1/enroll -H "Content-Type: application/json" \
  -d '{"name":"Aarav Mehta","email":"aarav@student.edu"}'

# A student joins class 1 (marks it live)
curl -X POST http://localhost:5000/api/classes/1/join -H "Content-Type: application/json" \
  -d '{"name":"Aarav Mehta"}'

# Platform stats
curl http://localhost:5000/api/stats
```

### Run unit tests
```bash
cd app
pip install pytest
PYTHONPATH=. pytest tests/ -v
```

---

## 3. Step 1 — Source Code Repository (GitHub)

```bash
cd virtual-classroom
git init
git add .
git commit -m "Initial commit: EduStream app + DevOps pipeline"
git branch -M main
git remote add origin https://github.com/<your-username>/edustream.git
git push -u origin main
```

Create a `.gitignore`:
```
venv/
__pycache__/
*.pyc
classroom.db
.terraform/
*.tfstate
*.tfstate.backup
```

---

## 4. Step 2 — Dockerize the Application

```bash
cd app
docker build -t edustream:latest .
docker run -d -p 5000:5000 --name edustream edustream:latest
curl http://localhost:5000/health
```

### Run the full local stack (app + monitoring + ELK + Vault)
```bash
cd virtual-classroom
docker-compose up -d
```
| Service | URL |
|---|---|
| EduStream app | http://localhost:5000 |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 (admin/admin) |
| Kibana | http://localhost:5601 |
| Vault | http://localhost:8200 (token: `root`) |

Push image to Docker Hub:
```bash
docker login
docker tag edustream:latest <dockerhub-username>/edustream:latest
docker push <dockerhub-username>/edustream:latest
```

---

## 5. Step 3 — Jenkins CI/CD Pipeline

The `jenkins/Jenkinsfile` defines a pipeline that:
1. Checks out source from GitHub
2. Installs deps & runs unit tests
3. Runs **Bandit** (SAST) for security scanning
4. Builds the Docker image
5. Scans the image with **Trivy**
6. Pushes the image to the registry
7. Runs `terraform apply` to provision/update AWS infra
8. Pulls DB secrets from **Vault**
9. Deploys to **Kubernetes** (rolling update)
10. Runs a smoke test against `/health`
11. Rolls back automatically on failure

### Setup
```bash
# Run Jenkins (quick start via Docker)
docker run -d --name jenkins -p 8080:8080 -p 50000:50000 \
  -v jenkins_home:/var/jenkins_home \
  -v /var/run/docker.sock:/var/run/docker.sock \
  jenkins/jenkins:lts

# Unlock Jenkins
docker exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword
```
1. Install plugins: Git, Docker Pipeline, Kubernetes CLI, Terraform, HashiCorp Vault.
2. Add credentials: `dockerhub-creds` (Docker Hub), AWS credentials, Vault AppRole.
3. Create a new Pipeline job pointing to `jenkins/Jenkinsfile` in your repo.
4. Trigger build via GitHub webhook on push to `main`.

---

## 6. Step 4 — Provision Infrastructure with Terraform (AWS)

The `terraform/` folder provisions:
- **VPC** with public/private subnets across 2 AZs
- **EKS cluster** + managed node group (2–4 nodes)
- **RDS PostgreSQL** (Multi-AZ) for classroom data
- **S3 bucket** with versioning + cross-region replication (DR)
- **IAM roles** for EKS cluster and nodes
- **CloudWatch** alarms and log groups

### Commands
```bash
cd terraform

# Configure AWS credentials
aws configure

# Create the S3 bucket for remote state first (one-time, manual)
aws s3api create-bucket --bucket edustream-terraform-state --region ap-south-1

terraform init
terraform plan -var="db_password=YourSecurePassword123!"
terraform apply -var="db_password=YourSecurePassword123!" -auto-approve

# Connect kubectl to the new EKS cluster
aws eks update-kubeconfig --region ap-south-1 --name edustream-eks
kubectl get nodes
```

To tear down:
```bash
terraform destroy -var="db_password=YourSecurePassword123!"
```

---

## 7. Step 5 — Deploy to Kubernetes

```bash
cd k8s
kubectl apply -f namespace.yaml
kubectl apply -f configmap.yaml
kubectl apply -f secret.yaml
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
kubectl apply -f hpa.yaml

# Verify
kubectl get pods -n edustream
kubectl get svc -n edustream
kubectl get hpa -n edustream

# Watch rollout
kubectl rollout status deployment/edustream -n edustream
```

Manual scaling test:
```bash
kubectl scale deployment edustream -n edustream --replicas=4
```

---

## 8. Step 6 — Monitoring (Prometheus + Grafana)

```bash
# If using Helm on the cluster:
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update

helm install prometheus prometheus-community/prometheus \
  -f monitoring/prometheus/prometheus.yml -n monitoring --create-namespace

helm install grafana grafana/grafana -n monitoring \
  --set adminPassword=admin
```

- Import `monitoring/grafana/edustream-dashboard.json` into Grafana (Dashboards → Import).
- Configure the datasource using `monitoring/grafana/datasource.yml` (Prometheus at `http://prometheus:9090`).
- Alert rules in `monitoring/prometheus/alerts.yml` cover: app down, high error rate, high latency.

Access Grafana:
```bash
kubectl port-forward svc/grafana 3000:80 -n monitoring
# http://localhost:3000
```

---

## 9. Step 7 — Logging (ELK Stack)

```bash
# Local (via docker-compose, already included):
docker-compose up -d elasticsearch logstash kibana

# Verify Elasticsearch
curl http://localhost:9200

# Open Kibana
# http://localhost:5601 → create index pattern "edustream-logs-*"
```

On Kubernetes, deploy **Filebeat** as a DaemonSet using `elk/filebeat.yml` to ship container logs to Logstash, which indexes them into Elasticsearch under `edustream-logs-*`.

---

## 10. Step 8 — Secrets Management (Vault)

```bash
# Run Vault in dev mode locally
vault server -dev

# In a new terminal:
cd vault
chmod +x setup-vault.sh
./setup-vault.sh

# Verify secret
export VAULT_ADDR='http://127.0.0.1:8200'
export VAULT_TOKEN='root'
vault kv get secret/edustream/db
```

On Kubernetes, install the **Vault Agent Injector**:
```bash
helm repo add hashicorp https://helm.releases.hashicorp.com
helm install vault hashicorp/vault -n vault --create-namespace \
  --set "server.dev.enabled=true" \
  --set "injector.enabled=true"
```
The annotations already present in `k8s/deployment.yaml` (`vault.hashicorp.com/agent-inject: "true"`) cause Vault to automatically inject DB credentials into the pod at `/vault/secrets/db-creds`.

---

## 11. Step 9 — Architecture & Deployment Diagrams

See:
- `diagrams/architecture-diagram.svg` — overall system architecture (users → ALB → EKS → app pods → RDS/S3/CloudWatch, plus monitoring & logging & Vault).
- `diagrams/deployment-pipeline-diagram.svg` — CI/CD flow from GitHub push to Kubernetes deployment.

---

## 12. Step 10 — Disaster Recovery

See `docs/disaster-recovery-plan.md` for full RTO/RPO targets, backup strategy, and
step-by-step recovery procedures for pod failure, node failure, database failure,
region failure, and secrets compromise.

To validate recovery:
```bash
# Simulate pod failure
kubectl delete pod -n edustream -l app=edustream

# Simulate rollback
kubectl rollout undo deployment/edustream -n edustream
```

---

## 13. Step 11 — Demonstration Screenshots Checklist

Capture and include screenshots of:
1. EduStream homepage (dashboard with live stats)
2. `docker ps` showing all running containers
3. Jenkins pipeline — successful build stages
4. `kubectl get pods -n edustream` — running pods
5. Grafana dashboard — live metrics
6. Kibana — application logs
7. Vault UI / CLI — secret retrieval
8. Terraform apply output — resources created
9. AWS Console — EKS cluster, RDS instance, S3 bucket

---

## 14. DORA Metrics Summary (for project documentation)

| Metric | How it's measured here |
|---|---|
| Deployment Frequency | Jenkins builds triggered per merge to `main` |
| Lead Time for Changes | Git commit timestamp → successful deploy timestamp (Jenkins) |
| Change Failure Rate | Failed pipeline runs / total runs (Jenkins build history) |
| Time to Restore Service | `kubectl rollout undo` time, tracked via Grafana/Prometheus alerts |

---

## 15. Quick End-to-End Demo (single machine, no AWS)

If you just want to demo everything locally without AWS:

```bash
cd virtual-classroom
docker-compose up -d --build
# App:        http://localhost:5000
# Prometheus: http://localhost:9090
# Grafana:    http://localhost:3000
# Kibana:     http://localhost:5601
# Vault:      http://localhost:8200
```

This satisfies the "working application + full DevOps lifecycle" requirement on a
single host, while the `terraform/` and `k8s/` folders demonstrate the production
AWS/Kubernetes design for the architecture and deployment diagrams.
