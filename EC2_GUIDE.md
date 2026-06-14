# EduStream — Running the Project via AWS EC2 (Build Host) + Local Terminal

This guide walks through using an **AWS EC2 instance as your build/control server**
(where Docker, Jenkins, Terraform, kubectl run) and your **local terminal** for
connecting to it via SSH, copying files, and viewing the app/dashboards in your browser.

---

## 0. Architecture of this setup

```
Local Terminal (your laptop)
   │  SSH
   ▼
EC2 Instance ("devops-controller")
   ├── Docker (build & run EduStream container)
   ├── Jenkins (CI/CD pipeline)
   ├── Terraform (provisions EKS/RDS/S3 on AWS)
   ├── kubectl + helm (deploys to EKS, installs monitoring/logging/vault)
   └── AWS CLI (talks to AWS APIs using IAM role / credentials)

AWS Cloud
   ├── EKS Cluster (runs EduStream pods, Prometheus, Grafana, ELK, Vault)
   ├── RDS PostgreSQL
   ├── S3 bucket
   └── ECR (Docker image registry)
```

---

## 1. Launch the EC2 Instance (from AWS Console or CLI)

### Option A — AWS Console
1. EC2 → Launch Instance
2. Name: `devops-controller`
3. AMI: **Ubuntu Server 22.04 LTS**
4. Instance type: **t3.large** (Jenkins + Docker need decent RAM; t2.micro will struggle)
5. Key pair: create new → download `edustream-key.pem`
6. Network: default VPC, auto-assign public IP = **Enable**
7. Security group — allow inbound:
   - SSH (22) from your IP
   - HTTP (80) from anywhere
   - Custom TCP 5000 (EduStream app) from your IP
   - Custom TCP 8080 (Jenkins) from your IP
   - Custom TCP 9090 (Prometheus), 3000 (Grafana), 5601 (Kibana), 8200 (Vault) from your IP
8. Storage: 30 GB
9. Launch

### Option B — AWS CLI (run this from your **local terminal**)
```bash
aws ec2 create-key-pair --key-name edustream-key --query 'KeyMaterial' --output text > edustream-key.pem
chmod 400 edustream-key.pem

aws ec2 create-security-group --group-name edustream-sg --description "EduStream DevOps controller"

SG_ID=$(aws ec2 describe-security-groups --group-names edustream-sg --query 'SecurityGroups[0].GroupId' --output text)
MY_IP=$(curl -s https://checkip.amazonaws.com)

for PORT in 22 5000 8080 9090 3000 5601 8200; do
  aws ec2 authorize-security-group-ingress --group-id $SG_ID --protocol tcp --port $PORT --cidr ${MY_IP}/32
done
aws ec2 authorize-security-group-ingress --group-id $SG_ID --protocol tcp --port 80 --cidr 0.0.0.0/0

aws ec2 run-instances \
  --image-id ami-0f5ee92e2d63afc18 \
  --count 1 \
  --instance-type t3.large \
  --key-name edustream-key \
  --security-group-ids $SG_ID \
  --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":30}}]' \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=devops-controller}]'
```
> The AMI ID is for Ubuntu 22.04 in `ap-south-1`. If your region differs, find the current AMI via:
> `aws ec2 describe-images --owners 099720109477 --filters "Name=name,Values=ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*" --query 'sort_by(Images,&CreationDate)[-1].ImageId' --output text`

Get the public IP:
```bash
aws ec2 describe-instances --filters "Name=tag:Name,Values=devops-controller" \
  --query 'Reservations[].Instances[].PublicIpAddress' --output text
```

---

## 2. Connect from Your Local Terminal to EC2 (SSH)

```bash
chmod 400 edustream-key.pem
ssh -i edustream-key.pem ubuntu@<EC2_PUBLIC_IP>
```

You're now inside the EC2 instance. **All commands in Steps 3–10 run on the EC2 instance** unless marked "local terminal".

---

## 3. Install Everything on EC2

```bash
sudo apt update && sudo apt upgrade -y

# Docker
sudo apt install -y docker.io
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
newgrp docker

# AWS CLI
sudo apt install -y unzip
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Configure AWS credentials (use an IAM user with EKS/EC2/RDS/S3/ECR/IAM/CloudWatch permissions)
aws configure
# Access Key, Secret Key, region: ap-south-1, output: json

# kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x kubectl && sudo mv kubectl /usr/local/bin/

# eksctl
curl --silent --location "https://github.com/eksctl-io/eksctl/releases/latest/download/eksctl_Linux_amd64.tar.gz" | tar xz
sudo mv eksctl /usr/local/bin

# Terraform
sudo apt install -y gnupg software-properties-common
wget -O- https://apt.releases.hashicorp.com/gpg | gpg --dearmor | sudo tee /usr/share/keyrings/hashicorp-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list
sudo apt update && sudo apt install -y terraform

# Helm
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Python (for running the app directly, optional)
sudo apt install -y python3-pip python3-venv git
```

---

## 4. Get the Project onto EC2

### Option A — clone from GitHub (recommended)
```bash
git clone https://github.com/<your-username>/edustream.git
cd edustream
```

### Option B — copy from your local machine
From your **local terminal** (new tab, not the SSH session):
```bash
scp -i edustream-key.pem -r ./virtual-classroom ubuntu@<EC2_PUBLIC_IP>:~/edustream
```
Then back on EC2:
```bash
cd ~/edustream
```

---

## 5. Run the App with Docker on EC2

```bash
cd app
docker build -t edustream:latest .
docker run -d -p 5000:5000 --name edustream edustream:latest

# Verify
curl http://localhost:5000/health
docker ps
```

### View the dashboard from your local browser
Open: `http://<EC2_PUBLIC_IP>:5000`

You should see the redesigned EduStream dashboard — dark theme, gradient hero, live system status card, session scheduler, and a platform/infrastructure tile grid.

### Push the image to ECR (so Kubernetes can pull it later)
```bash
aws ecr create-repository --repository-name edustream --region ap-south-1

export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export AWS_REGION=ap-south-1
export ECR_URL=$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_URL

docker tag edustream:latest $ECR_URL/edustream:latest
docker push $ECR_URL/edustream:latest
```

Run the full local stack (app + Prometheus + Grafana + ELK + Vault) via Compose:
```bash
cd ~/edustream
docker-compose up -d --build
docker ps
```
- App: `http://<EC2_PUBLIC_IP>:5000`
- Prometheus: `http://<EC2_PUBLIC_IP>:9090`
- Grafana: `http://<EC2_PUBLIC_IP>:3000` (admin/admin)
- Kibana: `http://<EC2_PUBLIC_IP>:5601`
- Vault: `http://<EC2_PUBLIC_IP>:8200` (token `root`)

---

## 6. Jenkins on EC2

```bash
docker run -d --name jenkins -p 8080:8080 -p 50000:50000 \
  -v jenkins_home:/var/jenkins_home \
  -v /var/run/docker.sock:/var/run/docker.sock \
  jenkins/jenkins:lts

docker exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword
```

From your **local browser**: open `http://<EC2_PUBLIC_IP>:8080`, paste the password,
install suggested plugins, then add: **Docker Pipeline**, **Amazon ECR**, **Kubernetes CLI**,
**Terraform**, **HashiCorp Vault** plugins.

Create a Pipeline job → "Pipeline script from SCM" → your GitHub repo →
script path `jenkins/Jenkinsfile`. Update `DOCKER_IMAGE` in the Jenkinsfile to
`$ECR_URL/edustream`. Click **Build Now**.

---

## 7. Provision AWS Infrastructure with Terraform (from EC2)

```bash
aws s3api create-bucket --bucket edustream-terraform-state --region ap-south-1 \
  --create-bucket-configuration LocationConstraint=ap-south-1
aws s3api put-bucket-versioning --bucket edustream-terraform-state --versioning-configuration Status=Enabled

cd ~/edustream/terraform
terraform init
terraform plan -var="db_password=YourSecurePassword123!"
terraform apply -var="db_password=YourSecurePassword123!" -auto-approve
```

This provisions VPC, EKS cluster, RDS (Multi-AZ), S3, IAM roles, CloudWatch alarms (~15 min).

```bash
terraform output
aws eks update-kubeconfig --region ap-south-1 --name edustream-eks
kubectl get nodes
```

---

## 8. Deploy to Kubernetes (from EC2)

```bash
cd ~/edustream/k8s
sed -i "s|yourdockerhub/edustream:IMAGE_TAG_PLACEHOLDER|$ECR_URL/edustream:latest|g" deployment.yaml

kubectl apply -f namespace.yaml
kubectl apply -f configmap.yaml
kubectl apply -f secret.yaml
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
kubectl apply -f hpa.yaml

kubectl get pods -n edustream
kubectl get svc -n edustream
kubectl rollout status deployment/edustream -n edustream
```

Install the ALB ingress controller and get the public URL:
```bash
helm repo add eks https://aws.github.io/eks-charts && helm repo update
helm install aws-load-balancer-controller eks/aws-load-balancer-controller \
  -n kube-system --set clusterName=edustream-eks --set serviceAccount.create=true

kubectl get ingress -n edustream
```
Once `ADDRESS` populates, open `http://<ALB-DNS-NAME>` in your local browser.

---

## 9. Monitoring, Logging, Vault (from EC2, deployed onto EKS)

```bash
# Prometheus + Grafana
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update
kubectl create namespace monitoring
helm install prometheus prometheus-community/prometheus -n monitoring -f ../monitoring/prometheus/prometheus.yml
helm install grafana grafana/grafana -n monitoring --set adminPassword=admin

# ELK
helm repo add elastic https://helm.elastic.co && helm repo update
kubectl create namespace logging
helm install elasticsearch elastic/elasticsearch -n logging --set replicas=1
helm install kibana elastic/kibana -n logging
helm install logstash elastic/logstash -n logging --set-file logstashPipeline."logstash\.conf"=../elk/logstash.conf
helm install filebeat elastic/filebeat -n logging --set-file daemonset.filebeatConfig."filebeat\.yml"=../elk/filebeat.yml

# Vault
helm repo add hashicorp https://helm.releases.hashicorp.com && helm repo update
kubectl create namespace vault
helm install vault hashicorp/vault -n vault --set "server.dev.enabled=true" --set "injector.enabled=true"
```

To view Grafana/Kibana from your **local browser**, port-forward on EC2 and SSH-tunnel from local:
```bash
# On EC2:
kubectl port-forward --address 0.0.0.0 svc/grafana 3000:80 -n monitoring &
kubectl port-forward --address 0.0.0.0 svc/kibana-kibana 5601:5601 -n logging &
```
Then open `http://<EC2_PUBLIC_IP>:3000` and `http://<EC2_PUBLIC_IP>:5601` (make sure
ports 3000/5601 are allowed in the security group, as set up in Step 1).

---

## 10. Verify Everything Together

```bash
kubectl get all -n edustream
kubectl get all -n monitoring
kubectl get all -n logging
kubectl get all -n vault
```

From your **local terminal**, hit the app's API through the ALB:
```bash
curl http://<ALB-DNS-NAME>/health
curl http://<ALB-DNS-NAME>/api/stats
```

---

## 11. Teardown (run on EC2, then terminate the instance from local)

```bash
kubectl delete namespace edustream monitoring logging vault
cd ~/edustream/terraform
terraform destroy -var="db_password=YourSecurePassword123!" -auto-approve
aws ecr delete-repository --repository-name edustream --region ap-south-1 --force
```

From your **local terminal**, terminate the EC2 instance:
```bash
aws ec2 terminate-instances --instance-ids <INSTANCE_ID>
```

---

## The application — courses, classes & enrollment

`app/app.py` implements a **Virtual Learning Platform** data model with three entities:

- **Courses** — title, instructor, description (`/api/courses`)
- **Classes** — live sessions scheduled under a course (`/api/courses/<id>/classes`)
- **Enrollments** — students registered to a course (`/api/courses/<id>/enroll`)

`app/templates/index.html` is a dark, modern SaaS-dashboard: gradient logo mark, sticky
nav with a live status pill, a hero with 4 stat cards (courses, classes, enrollments,
live sessions) and a system-health panel, a course catalog of cards, a course detail
view (classes + enrolled students side by side), and an infrastructure tile grid
showing the DevOps stack (Docker, Kubernetes, Jenkins, Terraform, Prometheus, Grafana,
ELK, Vault). `app/tests/test_app.py` covers all core flows and is run automatically by
the Jenkins pipeline.
