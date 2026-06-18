# EduStream – Virtual Classroom Platform

## Overview

EduStream is a cloud-native Virtual Classroom Platform developed to demonstrate a complete end-to-end DevOps lifecycle implementation. The platform enables administrators, teachers, and students to manage online learning activities while showcasing modern DevOps practices such as CI/CD, Infrastructure as Code, Containerization, Kubernetes orchestration, Monitoring, Logging, Security, and Disaster Recovery.

## Features

### Administrator

* Manage users and platform configurations
* Monitor system activity
* View all courses and sessions
* Manage teachers and students

### Teacher

* Create and manage courses
* Schedule virtual classroom sessions
* Generate meeting links
* Publish announcements
* Track student attendance

### Student

* Browse available courses
* Enroll in courses
* View announcements
* Join live sessions
* Automatic attendance marking

---

## DevOps Implementation

### Source Control

* Git
* GitHub

### Containerization

* Docker
* Docker Compose

### CI/CD

* Jenkins Pipeline

### Infrastructure as Code

* Terraform

### Container Orchestration

* Kubernetes (Amazon EKS)

### Monitoring

* Prometheus
* Grafana

### Logging

* ELK Stack (Elasticsearch, Logstash, Kibana)

### Secret Management

* HashiCorp Vault

### Cloud Platform

* AWS

---

## Technology Stack

| Layer            | Technology            |
| ---------------- | --------------------- |
| Frontend         | HTML, CSS, JavaScript |
| Backend          | Flask (Python)        |
| Database         | MySQL (Amazon RDS)    |
| Containerization | Docker                |
| CI/CD            | Jenkins               |
| Infrastructure   | Terraform             |
| Orchestration    | Kubernetes (EKS)      |
| Monitoring       | Prometheus & Grafana  |
| Logging          | ELK Stack             |
| Secrets          | HashiCorp Vault       |
| Cloud            | AWS                   |

---

## Project Architecture

```text
Users
   │
   ▼
Application Load Balancer
   │
   ▼
Amazon EKS Cluster
   │
 ┌─┴─────────────┐
 │               │
EduStream Pods   Vault
 │
 ├── Prometheus
 ├── Grafana
 └── ELK Stack
 │
 ▼
Amazon RDS MySQL
 │
 ▼
Amazon S3
```

---

## Repository Structure

```text
EduStream/
│
├── app/
├── terraform/
├── k8s/
├── monitoring/
├── elk/
├── vault/
├── jenkins/
├── docs/
└── README.md
```

---

## CI/CD Pipeline

1. Source Code Checkout
2. Unit Testing
3. Security Scanning
4. Docker Image Build
5. Docker Image Push
6. Terraform Infrastructure Provisioning
7. Vault Secret Retrieval
8. Kubernetes Deployment
9. Smoke Testing
10. Rollback on Failure

---

## AWS Infrastructure

* Amazon EKS
* Amazon RDS MySQL
* Amazon S3
* Amazon IAM
* Amazon CloudWatch
* Amazon ECR
* Amazon VPC
* Public & Private Subnets
* Internet Gateway
* NAT Gateway
* Security Groups

---

## Monitoring & Logging

### Monitoring

* Prometheus collects metrics
* Grafana visualizes metrics and alerts

### Logging

* Filebeat collects logs
* Logstash processes logs
* Elasticsearch stores logs
* Kibana visualizes logs

---

## Disaster Recovery

### Backup Strategy

* Automated RDS Snapshots
* Docker Images stored in ECR
* Terraform scripts stored in GitHub

### Recovery Strategy

* Kubernetes self-healing and pod recreation
* EKS workload rescheduling
* Database restoration from snapshots
* Infrastructure recreation using Terraform

---

## Project Outcomes

* Automated Deployments
* Infrastructure Automation
* Container Orchestration
* Centralized Logging
* Secret Management
* Monitoring and Alerting
* Disaster Recovery Implementation

---

## Future Enhancements

* Multi-region deployment
* Real-time video conferencing
* AI-powered analytics
* Service Mesh Implementation
* Advanced Security Scanning

---

## Author

**Vrutti Patil**

GitHub: https://github.com/Vrutti88/EduStream-Proj
