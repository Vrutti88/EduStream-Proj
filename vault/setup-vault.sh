#!/bin/bash
# Run against a dev Vault server (vault server -dev) or your real Vault.
set -e

export VAULT_ADDR='http://127.0.0.1:8200'
export VAULT_TOKEN='root'   # dev mode only

# 1. Enable KV secrets engine v2
vault secrets enable -path=secret kv-v2 || true

# 2. Store DB credentials
vault kv put secret/edustream/db \
  username="edustream_admin" \
  password="SuperSecretPassword123!" \
  host="edustream-db.clc8o48041xi.ap-south-1.rds.amazonaws.com"

# 3. Apply the access policy
vault policy write edustream vault-policy-edustream.hcl

# 4. Enable Kubernetes auth method (for Vault Agent Injector)
vault auth enable kubernetes || true
vault write auth/kubernetes/config \
  kubernetes_host="https://kubernetes.default.svc"

# 5. Create role binding the K8s service account to the edustream policy
vault write auth/kubernetes/role/edustream \
  bound_service_account_names=edustream \
  bound_service_account_namespaces=edustream \
  policies=edustream \
  ttl=24h

echo "Vault configured for EduStream."
