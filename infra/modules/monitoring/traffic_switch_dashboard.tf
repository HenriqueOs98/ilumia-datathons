# CloudWatch Dashboard for Traffic Switching Monitoring

resource "aws_cloudwatch_dashboard" "traffic_switching" {
  dashboard_name = "${var.project_name}-${var.environment}-traffic-switching"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["ONS/TrafficSwitching", "ResponseTime", "Backend", "influxdb", "Environment", var.environment],
            [".", ".", ".", "timestream", ".", "."],
          ]
          view    = "timeSeries"
          stacked = false
          region  = data.aws_region.current.name
          title   = "Response Time by Backend"
          period  = 300
          stat    = "Average"
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["ONS/TrafficSwitching", "ErrorRate", "Backend", "influxdb", "Environment", var.environment],
            [".", ".", ".", "timestream", ".", "."],
          ]
          view    = "timeSeries"
          stacked = false
          region  = data.aws_region.current.name
          title   = "Error Rate by Backend"
          period  = 300
          stat    = "Average"
          yAxis = {
            left = {
              min = 0
              max = 0.1
            }
          }
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["ONS/TrafficSwitching", "RequestCount", "Backend", "influxdb", "Environment", var.environment],
            [".", ".", ".", "timestream", ".", "."],
          ]
          view    = "timeSeries"
          stacked = false
          region  = data.aws_region.current.name
          title   = "Request Count by Backend"
          period  = 300
          stat    = "Sum"
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 6
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["ONS/TrafficSwitching", "ConnectionFailures", "Environment", var.environment],
          ]
          view    = "timeSeries"
          stacked = false
          region  = data.aws_region.current.name
          title   = "InfluxDB Connection Failures"
          period  = 300
          stat    = "Sum"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 12
        width  = 8
        height = 6

        properties = {
          metrics = [
            ["AWS/Lambda", "Duration", "FunctionName", "${var.project_name}-${var.environment}-rag-query-processor"],
            [".", ".", ".", "${var.project_name}-${var.environment}-timeseries-query-processor"],
          ]
          view    = "timeSeries"
          stacked = false
          region  = data.aws_region.current.name
          title   = "Lambda Function Duration"
          period  = 300
          stat    = "Average"
        }
      },
      {
        type   = "metric"
        x      = 8
        y      = 12
        width  = 8
        height = 6

        properties = {
          metrics = [
            ["AWS/Lambda", "Errors", "FunctionName", "${var.project_name}-${var.environment}-rag-query-processor"],
            [".", ".", ".", "${var.project_name}-${var.environment}-timeseries-query-processor"],
          ]
          view    = "timeSeries"
          stacked = false
          region  = data.aws_region.current.name
          title   = "Lambda Function Errors"
          period  = 300
          stat    = "Sum"
        }
      },
      {
        type   = "metric"
        x      = 16
        y      = 12
        width  = 8
        height = 6

        properties = {
          metrics = [
            ["AWS/Lambda", "Invocations", "FunctionName", "${var.project_name}-${var.environment}-rag-query-processor"],
            [".", ".", ".", "${var.project_name}-${var.environment}-timeseries-query-processor"],
          ]
          view    = "timeSeries"
          stacked = false
          region  = data.aws_region.current.name
          title   = "Lambda Function Invocations"
          period  = 300
          stat    = "Sum"
        }
      },
      {
        type   = "log"
        x      = 0
        y      = 18
        width  = 24
        height = 6

        properties = {
          query  = "SOURCE '/aws/lambda/${var.project_name}-${var.environment}-rag-query-processor' | fields @timestamp, @message | filter @message like /ERROR/ | sort @timestamp desc | limit 20"
          region = data.aws_region.current.name
          title  = "Recent Errors from RAG Query Processor"
          view   = "table"
        }
      },
      {
        type   = "log"
        x      = 0
        y      = 24
        width  = 24
        height = 6

        properties = {
          query  = "SOURCE '/aws/lambda/${var.project_name}-${var.environment}-timeseries-query-processor' | fields @timestamp, @message | filter @message like /ERROR/ | sort @timestamp desc | limit 20"
          region = data.aws_region.current.name
          title  = "Recent Errors from Timeseries Query Processor"
          view   = "table"
        }
      }
    ]
  })


}

# Custom Metrics for Traffic Switching Performance
resource "aws_cloudwatch_metric_alarm" "traffic_switch_success_rate" {
  alarm_name          = "${var.project_name}-${var.environment}-traffic-switch-success-rate"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "3"
  metric_name         = "SuccessRate"
  namespace           = "ONS/TrafficSwitching"
  period              = "300"
  statistic           = "Average"
  threshold           = "0.95" # 95% success rate
  alarm_description   = "Traffic switching success rate below threshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    Environment = var.environment
  }
  alarm_actions = [aws_sns_topic.critical_alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "influxdb_vs_timestream_latency" {
  alarm_name          = "${var.project_name}-${var.environment}-influxdb-latency-comparison"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"

  metric_query {
    id = "m1"
    metric {
      metric_name = "ResponseTime"
      namespace   = "ONS/TrafficSwitching"
      period      = 300
      stat        = "Average"
      dimensions = {
        Backend     = "influxdb"
        Environment = var.environment
      }
    }
  }

  metric_query {
    id = "m2"
    metric {
      metric_name = "ResponseTime"
      namespace   = "ONS/TrafficSwitching"
      period      = 300
      stat        = "Average"
      dimensions = {
        Backend     = "timestream"
        Environment = var.environment
      }
    }
  }

  metric_query {
    id          = "e1"
    expression  = "m1 - m2"
    label       = "InfluxDB vs Timestream Latency Difference"
    return_data = true
  }

  threshold          = 5000 # 5 seconds difference
  alarm_description  = "InfluxDB response time significantly higher than Timestream"
  treat_missing_data = "notBreaching"

  alarm_actions = [aws_sns_topic.critical_alerts.arn]
}

# Data source for current region
data "aws_region" "current" {}