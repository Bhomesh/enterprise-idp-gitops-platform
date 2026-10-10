variable "aws_region" {
  type        = string
  description = "AWS deployment region for IDP host cluster"
  default     = "us-east-1"
}

variable "environment" {
  type        = string
  description = "Target environment tier (dev, staging, prod)"
  default     = "production"
}

variable "cluster_name" {
  type        = string
  description = "EKS cluster name hosting the IDP control plane"
  default     = "enterprise-idp-control-plane"
}

variable "vpc_cidr" {
  type        = string
  description = "VPC CIDR block"
  default     = "10.100.0.0/16"
}

variable "argocd_version" {
  type        = string
  description = "Argo CD Helm chart version"
  default     = "6.7.18"
}

variable "crossplane_version" {
  type        = string
  description = "Crossplane Helm chart version"
  default     = "1.15.0"
}
