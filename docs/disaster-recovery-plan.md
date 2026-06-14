# EduStream — Disaster Recovery Plan

## 1. Objectives
- **RTO (Recovery Time Objective):** 30 minutes
- **RPO (Recovery Point Objective):** 15 minutes (via RDS automated backups + S3 versioning)

## 2. Backup Strategy
| Component | Backup method | Frequency | Location |
|---|---|---|---|
| RDS PostgreSQL | Automated snapshots + multi-AZ standby | Continuous (5-min log shipping), daily snapshot | Same region + cross-region copy |
| S3 application data | Versioning + cross-region replication | Real-time | Secondary region bucket |
| Kubernetes manifests / Terraform state | Git repository + S3 remote state with versioning | On every commit | GitHub + S3 |
| Container images | Pushed to registry with immutable tags | Every build | Docker Hub / ECR |
| Vault secrets | Vault snapshot (`vault operator raft snapshot save`) | Daily | S3 (encrypted) |

## 3. Failure Scenarios & Recovery Steps

### 3.1 Pod / Application Crash
1. Kubernetes liveness probe detects failure, restarts pod automatically.
2. If repeated crash loop: `kubectl rollout undo deployment/edustream -n edustream` to revert to last known-good image.
3. Verify via `/health` endpoint and Grafana dashboard.

### 3.2 Node Failure
1. EKS node group Auto Scaling replaces the unhealthy node automatically.
2. Pods reschedule onto healthy nodes (replicas=2 minimum ensures availability).
3. CloudWatch alarm `node-cpu-high` / node-not-ready notifies the on-call engineer.

### 3.3 Database Failure (RDS)
1. Multi-AZ failover triggers automatically (typically 60–120 seconds).
2. Application reconnects using the same RDS endpoint (DNS-based failover).
3. If full region failure: restore latest automated snapshot in DR region, update `DB_HOST` secret in Vault, restart pods to pick up new secret.

### 3.4 Full Cluster / Region Failure
1. Run `terraform apply` against the DR region using the backed-up state file.
2. Restore RDS from latest cross-region snapshot.
3. Restore S3 data from replicated DR bucket.
4. Re-run Vault setup script (`vault/setup-vault.sh`) pointing to new infrastructure endpoints.
5. Apply Kubernetes manifests (`kubectl apply -f k8s/`) to the new EKS cluster.
6. Update DNS (Route 53) to point to the new ALB.
7. Run smoke tests against `/health` and `/api/stats`.

### 3.5 Secrets Compromise
1. Revoke compromised Vault token: `vault token revoke <token>`.
2. Rotate DB credentials in Vault (`vault kv put secret/edustream/db ...`) and in RDS.
3. Restart pods to re-inject fresh secrets via Vault Agent.

## 4. Validation / DR Drills
- Quarterly: restore RDS snapshot into a staging environment and verify data integrity.
- Quarterly: simulate pod deletion (`kubectl delete pod`) and confirm auto-recovery within RTO.
- Annually: full failover drill to DR region.

## 5. Communication Plan
- Incidents logged in the incident management tool with timestamps.
- Postmortem written within 48 hours covering root cause, timeline, and corrective actions (per SRE practices).
