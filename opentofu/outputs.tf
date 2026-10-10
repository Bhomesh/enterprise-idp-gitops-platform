output "vpc_id" {
  description = "ID of the provisioned VPC"
  value       = module.vpc.vpc_id
}

output "cluster_name" {
  description = "EKS cluster name"
  value       = module.kubernetes.cluster_name
}

output "cluster_endpoint" {
  description = "Kubernetes API endpoint"
  value       = module.kubernetes.endpoint
}

output "argocd_server_url" {
  description = "Argo CD UI Server endpoint"
  value       = "https://argocd.platform.corp"
}
