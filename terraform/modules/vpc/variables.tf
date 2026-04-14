variable "project_name" {
  type = string
}

variable "vpc_cidr" {
  type = string
}

variable "aws_region" {
  type = string
}

variable "tags" {
  type = map(string)
}
