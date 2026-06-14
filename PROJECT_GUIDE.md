# EduStream — Virtual Learning Platform
## Complete DevOps Project: 100-Mark Rubric + AWS Execution Guide (Step-by-Step Terminal Commands)

---

# PART A — 100 MARK BREAKDOWN

| # | Deliverable | Marks | Where it lives in this project |
|---|---|---|---|
| 1 | Working Application (Courses, Classes, Enrollment) | 15 | `app/` — Flask app, SQLite, dashboard UI, REST API |
| 2 | Source Code Repository (GitHub) | 5 | Git init/push steps below |
| 3 | Dockerfile and Docker Images | 8 | `app/Dockerfile`, `docker-compose.yml` |
| 4 | Jenkins CI/CD Pipeline | 12 | `jenkins/Jenkinsfile` |
| 5 | Terraform Infrastructure Scripts | 12 | `terraform/` (VPC, EKS, RDS, S3, IAM, CloudWatch) |
| 6 | Kubernetes Deployment Files | 10 | `k8s/` |
| 7 | Monitoring (Prometheus + Grafana) | 8 | `monitoring/` |
| 8 | Logging (ELK Stack) | 8 | `elk/` |
| 9 | Secrets Management (Vault) | 6 | `vault/` |
| 10 | Architecture Diagram | 4 | `diagrams/architecture-diagram.svg` |
| 11 | Deployment Diagram | 4 | `diagrams/deployment-pipeline-diagram.svg` |
| 12 | Disaster Recovery Plan | 4 | `docs/disaster-recovery-plan.md` |
| 13 | Demonstration Screenshots | 2 | Checklist in Part C |
| 14 | Project Documentation | 2 | This file + README.md |
| | **TOTAL** | **100** | |


**Marking logic used (so every section maps cleanly to marks):**
- Application (15) = correctness (8) + UI quality (4) + API completeness (3)
- CI/CD (12) = pipeline stages (6) + security scanning/SAST (3) + rollback handling (3)
- Terraform (12) = networking (3) + compute/EKS (4) + data/storage (3) + IAM/CloudWatch (2)
- Kubernetes (10) = deployment/service (4) + scaling/HPA (2) + config/secret separation (2) + probes (2)
- Monitoring (8) = Prometheus scrape config (4) + Grafana dashboard (4)
- Logging (8) = pipeline config (4) + working log flow demo (4)
- Vault (6) = policy + KV setup (3) + K8s integration (3)

---

# PART B — RUNNING THE ENTIRE PROJECT ON AWS (TERMINAL, STEP BY STEP)

This section assumes you have:
- An AWS account with admin access (or sufficient IAM permissions for VPC, EKS, RDS, S3, IAM, CloudWatch)
- AWS CLI v2 installed locally
- A Linux/macOS terminal (or WSL on Windows)

> All commands below are exactly what you type into your terminal. Replace placeholders like `<your-username>`, `<account-id>`, `YourSecurePassword123!` with your own values.

---

## STEP 0 — Local Tooling Setup

```bash
# Check / install AWS CLI
aws --version
# If missing (Linux):
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Configure your AWS credentials
aws configure
# AWS Access Key ID: <your access key>
# AWS Secret Access Key: <your secret key>
# Default region: ap-south-1
# Default output format: json

# Verify identity
aws sts get-caller-identity

# Install Docker
sudo apt update && sudo apt install -y docker.io
sudo systemctl enable --now docker
sudo usermod -aG docker $USER && newgrp docker

# Install kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x kubectl && sudo mv kubectl /usr/local/bin/

# Install Terraform
sudo apt install -y gnupg software-properties-common
wget -O- https://apt.releases.hashicorp.com/gpg | gpg --dearmor | sudo tee /usr/share/keyrings/hashicorp-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list
sudo apt update && sudo apt install -y terraform

# Install Helm (for Prometheus/Grafana/Vault on EKS)
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Install eksctl (optional, makes EKS easier)
curl --silent --location "https://github.com/eksctl-io/eksctl/releases/latest/download/eksctl_Linux_amd64.tar.gz" | tar xz -C /tmp
sudo mv /tmp/eksctl /usr/local/bin
```

---

## STEP 1 — Push Source Code to GitHub (5 marks)

```bash
cd virtual-classroom

cat > .gitignore << 'EOF'
venv/
__pycache__/
*.pyc
classroom.db
.terraform/
*.tfstate
*.tfstate.backup
EOF

git init
git add .
git commit -m "Initial commit: EduStream app + full DevOps pipeline"
git branch -M main
git remote add origin https://github.com/<your-username>/edustream.git
git push -u origin main
```

---

## STEP 2 — Run the App Locally to Verify It Works (part of 15 marks)

```bash
cd app
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 app.py
```
Open `http://localhost:5000` — you should see the EduStream dashboard (course
catalog, "Create a course" form, and platform/infrastructure tile grid).

Test the API:
```bash
curl http://localhost:5000/health

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

# Student joins class 1 (marks it live)
curl -X POST http://localhost:5000/api/classes/1/join -H "Content-Type: application/json" \
  -d '{"name":"Aarav Mehta"}'

curl http://localhost:5000/api/stats
```

Run the unit tests (also run automatically by Jenkins):
```bash
pip install pytest
PYTHONPATH=. pytest tests/ -v
```

Stop the app with `Ctrl+C`.

---

## STEP 3 — Build & Push Docker Image to Amazon ECR (8 marks)

```bash
# Create an ECR repository
aws ecr create-repository --repository-name edustream --region ap-south-1

# Get your AWS account ID
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export AWS_REGION=ap-south-1
export ECR_URL=$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Authenticate Docker to ECR
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_URL

# Build the image
cd app
docker build -t edustream:latest .

# Tag and push
docker tag edustream:latest $ECR_URL/edustream:latest
docker push $ECR_URL/edustream:latest

# Verify
aws ecr describe-images --repository-name edustream --region $AWS_REGION
```

### Quick local smoke test with Docker Compose
```bash
cd ..
docker-compose up -d --build
docker ps
curl http://localhost:5000/health
docker-compose down
```

---

## STEP 4 — Provision AWS Infrastructure with Terraform (12 marks)

This creates: VPC (2 public + 2 private subnets), EKS cluster + node group, RDS PostgreSQL (Multi-AZ), S3 bucket (versioned + replicated), IAM roles, CloudWatch alarms/log group.

```bash
# One-time: create the S3 bucket Terraform uses for remote state
aws s3api create-bucket \
  --bucket edustream-terraform-state \
  --region ap-south-1 \
  --create-bucket-configuration LocationConstraint=ap-south-1

aws s3api put-bucket-versioning \
  --bucket edustream-terraform-state \
  --versioning-configuration Status=Enabled

cd terraform

terraform init

terraform plan -var="db_password=YourSecurePassword123!"

terraform apply -var="db_password=YourSecurePassword123!" -auto-approve
```

This step takes **10–20 minutes** (EKS + RDS provisioning). When it finishes, Terraform prints outputs:
```bash
terraform output
# eks_cluster_endpoint = "..."
# eks_cluster_name     = "edustream-eks"
# rds_endpoint         = (sensitive)
# s3_bucket_name       = "edustream-storage-<account-id>"
```

Connect `kubectl` to the new cluster:
```bash
aws eks update-kubeconfig --region ap-south-1 --name edustream-eks
kubectl get nodes
```
You should see 2 worker nodes in `Ready` state.

Get the RDS endpoint (needed for Vault/secrets in Step 7):
```bash
terraform output -raw rds_endpoint
```

---

## STEP 5 — Deploy EduStream to Kubernetes (EKS) (10 marks)

First update the image reference to point at your ECR repo:
```bash
cd ../k8s
sed -i "s|yourdockerhub/edustream:IMAGE_TAG_PLACEHOLDER|$ECR_URL/edustream:latest|g" deployment.yaml
```

Apply all manifests:
```bash
kubectl apply -f namespace.yaml
kubectl apply -f configmap.yaml
kubectl apply -f secret.yaml
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
kubectl apply -f hpa.yaml
```

Verify everything is running:
```bash
kubectl get pods -n edustream
kubectl get svc -n edustream
kubectl get hpa -n edustream
kubectl rollout status deployment/edustream -n edustream
```

Get the load balancer URL (if using LoadBalancer/ALB service):
```bash
kubectl get ingress -n edustream
# Wait a few minutes for ADDRESS to populate, then:
curl http://<ALB-DNS-NAME>/health
```

If you don't have the ALB ingress controller installed yet, install it:
```bash
helm repo add eks https://aws.github.io/eks-charts
helm repo update
helm install aws-load-balancer-controller eks/aws-load-balancer-controller \
  -n kube-system \
  --set clusterName=edustream-eks \
  --set serviceAccount.create=true
```

Test autoscaling (generates load, watch HPA scale pods):
```bash
kubectl run -i --tty load-generator --rm --image=busybox --restart=Never -- \
  /bin/sh -c "while true; do wget -q -O- http://edustream-svc/; done"
# In another terminal:
kubectl get hpa -n edustream -w
```

---

## STEP 6 — Monitoring: Prometheus + Grafana (8 marks)

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update

kubectl create namespace monitoring

helm install prometheus prometheus-community/prometheus -n monitoring \
  -f ../monitoring/prometheus/prometheus.yml

helm install grafana grafana/grafana -n monitoring \
  --set adminPassword=admin
```

Access Grafana:
```bash
kubectl port-forward svc/grafana 3000:80 -n monitoring
# Open http://localhost:3000  → login admin/admin
```
- Add data source: Prometheus, URL `http://prometheus-server.monitoring.svc.cluster.local`
- Dashboards → Import → upload `monitoring/grafana/edustream-dashboard.json`

Apply alert rules:
```bash
kubectl create configmap prometheus-alerts -n monitoring \
  --from-file=../monitoring/prometheus/alerts.yml
```

Verify the app exposes metrics:
```bash
kubectl port-forward svc/edustream-svc 8080:80 -n edustream
curl http://localhost:8080/metrics
```

---

## STEP 7 — Logging: ELK Stack (8 marks)

```bash
helm repo add elastic https://helm.elastic.co
helm repo update

kubectl create namespace logging

helm install elasticsearch elastic/elasticsearch -n logging --set replicas=1
helm install kibana elastic/kibana -n logging
helm install logstash elastic/logstash -n logging \
  --set-file logstashPipeline."logstash\.conf"=../elk/logstash.conf

helm install filebeat elastic/filebeat -n logging \
  --set-file daemonset.filebeatConfig."filebeat\.yml"=../elk/filebeat.yml
```

Access Kibana:
```bash
kubectl port-forward svc/kibana-kibana 5601:5601 -n logging
# Open http://localhost:5601
```
- Stack Management → Index Patterns → create `edustream-logs-*`
- Discover → view live application logs flowing from Filebeat → Logstash → Elasticsearch

---

## STEP 8 — Secrets Management: Vault (6 marks)

```bash
helm repo add hashicorp https://helm.releases.hashicorp.com
helm repo update

kubectl create namespace vault

helm install vault hashicorp/vault -n vault \
  --set "server.dev.enabled=true" \
  --set "injector.enabled=true"

# Exec into the Vault pod
kubectl exec -n vault -it vault-0 -- /bin/sh
```
Inside the Vault pod shell:
```sh
export VAULT_ADDR='http://127.0.0.1:8200'
export VAULT_TOKEN='root'

vault secrets enable -path=secret kv-v2

vault kv put secret/edustream/db \
  username="edustream_admin" \
  password="YourSecurePassword123!" \
  host="<rds_endpoint_from_terraform_output>"

vault policy write edustream - << 'EOF'
path "secret/data/edustream/*" {
  capabilities = ["read", "list"]
}
EOF

vault auth enable kubernetes

vault write auth/kubernetes/config \
  kubernetes_host="https://kubernetes.default.svc"

vault write auth/kubernetes/role/edustream \
  bound_service_account_names=edustream \
  bound_service_account_namespaces=edustream \
  policies=edustream \
  ttl=24h

exit
```
The `vault.hashicorp.com/agent-inject: "true"` annotations already in `k8s/deployment.yaml` will cause Vault to inject `secret/edustream/db` into the pod automatically on the next rollout:
```bash
kubectl rollout restart deployment/edustream -n edustream
```

---

## STEP 9 — Jenkins CI/CD Pipeline (12 marks)

```bash
docker run -d --name jenkins -p 8080:8080 -p 50000:50000 \
  -v jenkins_home:/var/jenkins_home \
  -v /var/run/docker.sock:/var/run/docker.sock \
  jenkins/jenkins:lts

# Get the initial admin password
docker exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword
```
1. Open `http://localhost:8080`, paste the password, install suggested plugins.
2. Install extra plugins: **Docker Pipeline**, **Amazon ECR**, **Kubernetes CLI**, **Terraform**, **HashiCorp Vault**.
3. Add credentials:
   - AWS access key/secret (for ECR push, EKS, Terraform)
   - Vault AppRole `role_id`/`secret_id`
4. New Item → Pipeline → "EduStream-CI-CD" → Pipeline script from SCM → point to your GitHub repo, script path `jenkins/Jenkinsfile`.
5. Update the `Jenkinsfile` `DOCKER_IMAGE` variable to your ECR URL (`$ECR_URL/edustream`).
6. Click **Build Now** and watch the stages run: Checkout → Test → SAST (Bandit) → Build Docker → Trivy scan → Push to ECR → Terraform apply → Vault secrets → Deploy to EKS → Smoke test.
7. (Optional) Add a GitHub webhook so every push to `main` triggers this pipeline automatically.

---

## STEP 10 — Architecture & Deployment Diagrams (8 marks total)

Already provided as `diagrams/architecture-diagram.svg` and `diagrams/deployment-pipeline-diagram.svg`. Open in any browser or embed directly into your project report.

---

## STEP 11 — Disaster Recovery Validation (4 marks)

```bash
# Simulate pod crash and confirm auto-recovery
kubectl delete pod -n edustream -l app=edustream
kubectl get pods -n edustream -w

# Simulate bad deployment and rollback
kubectl rollout undo deployment/edustream -n edustream
kubectl rollout status deployment/edustream -n edustream

# Verify RDS automated backups exist
aws rds describe-db-snapshots --db-instance-identifier edustream-db --region ap-south-1
```
Full plan: `docs/disaster-recovery-plan.md`.

---

## STEP 12 — Demonstration Screenshots Checklist (2 marks)

Capture these for your submission:
1. EduStream dashboard in browser (homepage with live stats)
2. `docker ps` / `docker-compose ps` output
3. `aws ecr describe-images` output showing pushed image
4. `terraform apply` final output (resources created + outputs)
5. `kubectl get pods -n edustream` (Running pods)
6. `kubectl get hpa -n edustream` during load test (scaling event)
7. Grafana dashboard with live metrics
8. Kibana Discover view showing application logs
9. Vault `vault kv get secret/edustream/db` output
10. Jenkins pipeline — all green stages
11. AWS Console: EKS cluster page, RDS instance page, S3 bucket page

---

## STEP 13 — Tear Down (avoid AWS charges)

```bash
# Delete K8s resources first
kubectl delete namespace edustream monitoring logging vault

# Destroy Terraform-managed AWS infra
cd terraform
terraform destroy -var="db_password=YourSecurePassword123!" -auto-approve

# Delete ECR repo
aws ecr delete-repository --repository-name edustream --region ap-south-1 --force

# Empty and delete the Terraform state bucket
aws s3 rm s3://edustream-terraform-state --recursive
aws s3api delete-bucket --bucket edustream-terraform-state --region ap-south-1

# Stop Jenkins
docker stop jenkins && docker rm jenkins
```

---

# PART C — REPORT STRUCTURE (matches the 100-mark breakdown)

1. Title page & problem statement
2. Application overview + screenshots (15 marks)
3. Source control workflow (5 marks)
4. Docker & containerization (8 marks)
5. CI/CD pipeline with Jenkins (12 marks)
6. Infrastructure as Code with Terraform (12 marks)
7. Kubernetes deployment & scaling (10 marks)
8. Monitoring with Prometheus/Grafana (8 marks)
9. Logging with ELK (8 marks)
10. Secrets management with Vault (6 marks)
11. Architecture diagram (4 marks)
12. Deployment diagram (4 marks)
13. Disaster recovery plan (4 marks)
14. Conclusion & DORA metrics summary (2 marks)
