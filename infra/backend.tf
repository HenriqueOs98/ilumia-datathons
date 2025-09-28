terraform {
  backend "s3" {
    bucket         = "ons-data-platform-terraform-state"
    key            = "terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "ons-data-platform-terraform-locks"
  }
}