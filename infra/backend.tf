# Terraform backend configuration
# For deployment testing, using local backend
# In production, use S3 backend with proper credentials

terraform {
  backend "local" {
    path = "terraform.tfstate"
  }
}

# S3 backend configuration (commented out for local testing)
# terraform {
#   backend "s3" {
#     bucket         = "ons-data-platform-terraform-state"
#     key            = "terraform.tfstate"
#     region         = "us-east-1"
#     encrypt        = true
#     use_lockfile   = true
#     dynamodb_table = "ons-data-platform-terraform-locks"
#   }
# }