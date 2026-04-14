variable "project_name" {
  type = string
}

variable "tags" {
  type = map(string)
}

resource "aws_iam_user" "cicd" {
  name = "${var.project_name}-cicd-user"
  tags = var.tags
}

resource "aws_iam_access_key" "cicd" {
  user = aws_iam_user.cicd.name
}

# Policy for ECR access
resource "aws_iam_user_policy" "ecr_policy" {
  name = "${var.project_name}-ecr-policy"
  user = aws_iam_user.cicd.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:GetRepositoryPolicy",
          "ecr:DescribeRepositories",
          "ecr:ListImages",
          "ecr:DescribeImages",
          "ecr:BatchGetImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload",
          "ecr:PutImage"
        ]
        Effect   = "Allow"
        Resource = "*"
      }
    ]
  })
}

# Policy for EKS access (describe cluster)
resource "aws_iam_user_policy" "eks_policy" {
  name = "${var.project_name}-eks-policy"
  user = aws_iam_user.cicd.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "eks:DescribeCluster"
        ]
        Effect   = "Allow"
        Resource = "*"
      }
    ]
  })
}

output "access_key_id" {
  value = aws_iam_access_key.cicd.id
}

output "secret_access_key" {
  value     = aws_iam_access_key.cicd.secret
  sensitive = true
}
