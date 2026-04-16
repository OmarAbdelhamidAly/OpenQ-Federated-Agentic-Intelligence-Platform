variable "project_name" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "db_instance_class" {
  type = map(number)
}

variable "tags" {
  type = map(string)
}

variable "kms_key_id" {
  description = "KMS Key ARN for database encryption"
  type        = string
}
