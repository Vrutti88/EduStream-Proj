terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket = "edustream-storage-bucket"
    key    = "edustream/terraform.tfstate"
    region = "ap-south-1"
  }
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  default = "ap-south-1"
}

variable "project_name" {
  default = "edustream"
}

variable "cluster_version" {
  default = "1.35"
}

variable "node_instance_type" {
  default = "m7i-flex.large"
}

variable "db_username" {
  default = "edustream_admin"
}

variable "db_password" {
  description = "RDS master password"
  type        = string
  sensitive   = true
  default     = "edustream123"
}
