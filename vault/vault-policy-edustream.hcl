# vault-policy-edustream.hcl
# Policy granting the EduStream app read access to its own secrets

path "secret/data/edustream/*" {
  capabilities = ["read", "list"]
}
