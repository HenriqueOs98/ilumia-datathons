import {
  to = module.appconfig.aws_appconfig_application.main
  id = "5e4sizt"
}

import {
  to = module.appconfig.aws_iam_role.appconfig_service_role
  id = "ons-data-platform-appconfig-service-role"
}

import {
  to = module.codedeploy.aws_codedeploy_app.lambda_app
  id = "ons-data-platform-lambda-app"
}

import {
  to = module.codedeploy.aws_iam_role.codedeploy_service_role
  id = "ons-data-platform-codedeploy-service-role"
}

import {
  to = module.codedeploy.aws_sns_topic.deployment_alerts
  id = "arn:aws:sns:us-east-1:957734434559:ons-data-platform-deployment-alerts"
}

import {
  to = module.lambda_functions.aws_iam_role.influxdb_lambda_role
  id = "ons-data-platform-dev-influxdb-lambda-role"
}

import {
  to = module.timestream_influxdb.aws_cloudwatch_log_group.influxdb_lambda_logs
  id = "/aws/lambda/ons-data-platform-dev-influxdb-loader"
}
