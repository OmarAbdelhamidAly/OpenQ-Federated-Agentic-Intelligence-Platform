variable "project_name" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "cluster_name" {
  type = string
}

variable "node_instance_type" {
  type = string
}

variable "tags" {
  type = map(string)
}
