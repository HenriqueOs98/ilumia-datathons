# API Gateway REST API
resource "aws_api_gateway_rest_api" "main" {
  name        = "${var.project_name}-${var.environment}-api"
  description = "ONS Data Platform API for natural language queries"

  endpoint_configuration {
    types = ["REGIONAL"]
  }

  # Request/Response validation
  body = jsonencode({
    openapi = "3.0.1"
    info = {
      title   = "${var.project_name}-${var.environment}-api"
      version = "1.0"
    }
    paths = {
      "/query" = {
        post = {
          summary = "Process natural language query"
          requestBody = {
            required = true
            content = {
              "application/json" = {
                schema = {
                  type     = "object"
                  required = ["question"]
                  properties = {
                    question = {
                      type      = "string"
                      minLength = 1
                      maxLength = 1000
                    }
                  }
                }
              }
            }
          }
          responses = {
            "200" = {
              description = "Successful response"
              content = {
                "application/json" = {
                  schema = {
                    type = "object"
                    properties = {
                      query_id         = { type = "string" }
                      question         = { type = "string" }
                      answer           = { type = "string" }
                      confidence_score = { type = "number" }
                      sources = {
                        type = "array"
                        items = {
                          type = "object"
                          properties = {
                            document        = { type = "string" }
                            relevance_score = { type = "number" }
                            excerpt         = { type = "string" }
                          }
                        }
                      }
                      processing_time_ms = { type = "integer" }
                      timestamp          = { type = "string" }
                    }
                  }
                }
              }
            }
            "400" = {
              description = "Bad request"
            }
            "401" = {
              description = "Unauthorized"
            }
            "429" = {
              description = "Too many requests"
            }
            "500" = {
              description = "Internal server error"
            }
          }
          security = [
            {
              api_key = []
            }
          ]
          "x-amazon-apigateway-integration" = {
            type       = "aws_proxy"
            httpMethod = "POST"
            uri        = "arn:aws:apigateway:${data.aws_region.current.name}:lambda:path/2015-03-31/functions/${var.lambda_api_arn}/invocations"
            integrationResponses = {
              "200" = {
                statusCode = "200"
              }
            }
          }
        }
      }
      "/health" = {
        get = {
          summary = "Health check endpoint"
          responses = {
            "200" = {
              description = "Service is healthy"
              content = {
                "application/json" = {
                  schema = {
                    type = "object"
                    properties = {
                      status    = { type = "string" }
                      timestamp = { type = "string" }
                    }
                  }
                }
              }
            }
          }
          "x-amazon-apigateway-integration" = {
            type       = "aws_proxy"
            httpMethod = "POST"
            uri        = "arn:aws:apigateway:${data.aws_region.current.name}:lambda:path/2015-03-31/functions/${var.lambda_api_arn}/invocations"
          }
        }
      }
    }
    components = {
      securitySchemes = {
        api_key = {
          type = "apiKey"
          name = "x-api-key"
          in   = "header"
        }
      }
    }
  })
}

# Data source for current AWS region
data "aws_region" "current" {}

# API Gateway Deployment
resource "aws_api_gateway_deployment" "main" {
  depends_on = [aws_api_gateway_rest_api.main]

  rest_api_id = aws_api_gateway_rest_api.main.id

  triggers = {
    redeployment = sha1(jsonencode(aws_api_gateway_rest_api.main.body))
  }

  lifecycle {
    create_before_destroy = true
  }
}

# API Gateway Stage
resource "aws_api_gateway_stage" "prod" {
  deployment_id = aws_api_gateway_deployment.main.id
  rest_api_id   = aws_api_gateway_rest_api.main.id
  stage_name    = "prod"

  # Throttling is configured via usage plans

  # Enable logging
  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gateway.arn
    format = jsonencode({
      requestId        = "$context.requestId"
      ip               = "$context.identity.sourceIp"
      caller           = "$context.identity.caller"
      user             = "$context.identity.user"
      requestTime      = "$context.requestTime"
      httpMethod       = "$context.httpMethod"
      resourcePath     = "$context.resourcePath"
      status           = "$context.status"
      protocol         = "$context.protocol"
      responseLength   = "$context.responseLength"
      responseTime     = "$context.responseTime"
      error            = "$context.error.message"
      integrationError = "$context.integration.error"
    })
  }

  # Enable X-Ray tracing
  xray_tracing_enabled = true

  tags = var.tags
}

# CloudWatch Log Group for API Gateway
resource "aws_cloudwatch_log_group" "api_gateway" {
  name              = "/aws/apigateway/${var.project_name}-${var.environment}-api"
  retention_in_days = var.log_retention_days

  tags = var.tags
}

# API Key for authentication
resource "aws_api_gateway_api_key" "main" {
  name        = "${var.project_name}-${var.environment}-api-key"
  description = "API key for ONS Data Platform"
  enabled     = true

  tags = var.tags
}

# Usage Plan for rate limiting and quotas
resource "aws_api_gateway_usage_plan" "basic" {
  name        = "${var.project_name}-${var.environment}-basic-plan"
  description = "Basic usage plan for ONS Data Platform API"

  api_stages {
    api_id = aws_api_gateway_rest_api.main.id
    stage  = aws_api_gateway_stage.prod.stage_name
  }

  quota_settings {
    limit  = var.quota_limit
    period = "DAY"
  }

  throttle_settings {
    rate_limit  = var.throttle_rate_limit
    burst_limit = var.throttle_burst_limit
  }

  tags = var.tags
}

# Premium Usage Plan for higher limits
resource "aws_api_gateway_usage_plan" "premium" {
  name        = "${var.project_name}-${var.environment}-premium-plan"
  description = "Premium usage plan for ONS Data Platform API"

  api_stages {
    api_id = aws_api_gateway_rest_api.main.id
    stage  = aws_api_gateway_stage.prod.stage_name
  }

  quota_settings {
    limit  = var.premium_quota_limit
    period = "DAY"
  }

  throttle_settings {
    rate_limit  = var.premium_throttle_rate_limit
    burst_limit = var.premium_throttle_burst_limit
  }

  tags = var.tags
}

# Associate API key with basic usage plan
resource "aws_api_gateway_usage_plan_key" "main" {
  key_id        = aws_api_gateway_api_key.main.id
  key_type      = "API_KEY"
  usage_plan_id = aws_api_gateway_usage_plan.basic.id
}

# Lambda permission for API Gateway
resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = var.lambda_function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.main.execution_arn}/*/*"
}

# IAM role for API Gateway CloudWatch logging
resource "aws_iam_role" "api_gateway_cloudwatch" {
  name = "${var.project_name}-${var.environment}-api-gateway-cloudwatch"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "apigateway.amazonaws.com"
        }
      }
    ]
  })

  tags = var.tags
}

# IAM policy attachment for CloudWatch logging
resource "aws_iam_role_policy_attachment" "api_gateway_cloudwatch" {
  role       = aws_iam_role.api_gateway_cloudwatch.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonAPIGatewayPushToCloudWatchLogs"
}

# API Gateway account settings for CloudWatch
resource "aws_api_gateway_account" "main" {
  cloudwatch_role_arn = aws_iam_role.api_gateway_cloudwatch.arn
}

# Method settings for detailed monitoring
resource "aws_api_gateway_method_settings" "all" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  stage_name  = aws_api_gateway_stage.prod.stage_name
  method_path = "*/*"

  settings {
    metrics_enabled        = true
    logging_level          = "INFO"
    data_trace_enabled     = true
    throttling_rate_limit  = var.throttle_rate_limit
    throttling_burst_limit = var.throttle_burst_limit
  }
}