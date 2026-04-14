variable "project_name" {
  type = string
}

variable "tags" {
  type = map(string)
}

variable "service_names" {
  type    = list(string)
  default = [
    "api",
    "exporter",
    "governance",
    "worker-audio",
    "worker-code",
    "worker-csv",
    "worker-image",
    "worker-json",
    "worker-nexus",
    "worker-pdf",
    "worker-sql",
    "worker-video",
    "frontend"
  ]
}

resource "aws_ecr_repository" "repos" {
  for_each             = toset(var.service_names)
  name                 = "${var.project_name}-${each.value}"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = var.tags
}

output "repository_urls" {
  value = { for k, v in aws_ecr_repository.repos : k => v.repository_url }
}
