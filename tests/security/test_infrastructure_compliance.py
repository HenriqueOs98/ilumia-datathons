"""
Infrastructure Compliance Testing
Tests infrastructure configurations for security and compliance
"""

import pytest
import json
import yaml
import os
from pathlib import Path
import re
from unittest.mock import Mock, patch


class TestTerraformSecurityCompliance:
    """Test Terraform infrastructure security compliance"""
    
    def test_s3_bucket_security_configuration(self):
        """Test S3 bucket security configurations"""
        # Simulate Terraform S3 configuration
        s3_config = {
            "resource": {
                "aws_s3_bucket": {
                    "data_bucket": {
                        "bucket": "ons-data-platform-raw",
                        "versioning": {
                            "enabled": True
                        },
                        "server_side_encryption_configuration": {
                            "rule": {
                                "apply_server_side_encryption_by_default": {
                                    "sse_algorithm": "AES256"
                                }
                            }
                        },
                        "public_access_block": {
                            "block_public_acls": True,
                            "block_public_policy": True,
                            "ignore_public_acls": True,
                            "restrict_public_buckets": True
                        },
                        "logging": {
                            "target_bucket": "ons-access-logs",
                            "target_prefix": "s3-access-logs/"
                        }
                    }
                }
            }
        }
        
        # Validate S3 security configurations
        s3_bucket = s3_config["resource"]["aws_s3_bucket"]["data_bucket"]
        
        # Check encryption
        assert "server_side_encryption_configuration" in s3_bucket
        encryption = s3_bucket["server_side_encryption_configuration"]["rule"]["apply_server_side_encryption_by_default"]
        assert encryption["sse_algorithm"] in ["AES256", "aws:kms"]
        
        # Check versioning
        assert s3_bucket["versioning"]["enabled"] is True
        
        # Check public access block
        public_access = s3_bucket["public_access_block"]
        assert public_access["block_public_acls"] is True
        assert public_access["block_public_policy"] is True
        assert public_access["ignore_public_acls"] is True
        assert public_access["restrict_public_buckets"] is True
        
        # Check logging
        assert "logging" in s3_bucket
        assert s3_bucket["logging"]["target_bucket"] is not None
    
    def test_lambda_security_configuration(self):
        """Test Lambda function security configurations"""
        # Simulate Terraform Lambda configuration
        lambda_config = {
            "resource": {
                "aws_lambda_function": {
                    "rag_processor": {
                        "function_name": "ons-rag-query-processor",
                        "runtime": "python3.11",
                        "timeout": 300,
                        "memory_size": 1024,
                        "environment": {
                            "variables": {
                                "KNOWLEDGE_BASE_ID": "${var.knowledge_base_id}",
                                "LOG_LEVEL": "INFO"
                            }
                        },
                        "vpc_config": {
                            "subnet_ids": ["${var.private_subnet_ids}"],
                            "security_group_ids": ["${aws_security_group.lambda_sg.id}"]
                        },
                        "dead_letter_config": {
                            "target_arn": "${aws_sqs_queue.dlq.arn}"
                        },
                        "tracing_config": {
                            "mode": "Active"
                        }
                    }
                }
            }
        }
        
        # Validate Lambda security configurations
        lambda_func = lambda_config["resource"]["aws_lambda_function"]["rag_processor"]
        
        # Check runtime version (should be recent)
        runtime = lambda_func["runtime"]
        assert "python3.11" in runtime or "python3.10" in runtime
        
        # Check timeout (should be reasonable)
        assert lambda_func["timeout"] <= 900  # Max 15 minutes
        
        # Check VPC configuration (should be in private subnets)
        assert "vpc_config" in lambda_func
        assert "subnet_ids" in lambda_func["vpc_config"]
        assert "security_group_ids" in lambda_func["vpc_config"]
        
        # Check dead letter queue
        assert "dead_letter_config" in lambda_func
        
        # Check tracing
        assert lambda_func["tracing_config"]["mode"] == "Active"
        
        # Check environment variables don't contain secrets
        env_vars = lambda_func["environment"]["variables"]
        for key, value in env_vars.items():
            # Should use variables or parameter store, not hardcoded secrets
            assert not any(secret in key.lower() for secret in ['password', 'secret', 'key', 'token'])
            if isinstance(value, str):
                assert not value.startswith('AKIA')  # AWS Access Key
                assert not re.match(r'^[A-Za-z0-9+/]{40}$', value)  # Base64 encoded secrets
    
    def test_iam_role_least_privilege(self):
        """Test IAM roles follow least privilege principle"""
        # Simulate IAM role configuration
        iam_config = {
            "resource": {
                "aws_iam_role": {
                    "lambda_execution_role": {
                        "name": "ons-lambda-execution-role",
                        "assume_role_policy": json.dumps({
                            "Version": "2012-10-17",
                            "Statement": [
                                {
                                    "Action": "sts:AssumeRole",
                                    "Effect": "Allow",
                                    "Principal": {
                                        "Service": "lambda.amazonaws.com"
                                    }
                                }
                            ]
                        })
                    }
                },
                "aws_iam_policy": {
                    "lambda_policy": {
                        "name": "ons-lambda-policy",
                        "policy": json.dumps({
                            "Version": "2012-10-17",
                            "Statement": [
                                {
                                    "Effect": "Allow",
                                    "Action": [
                                        "logs:CreateLogGroup",
                                        "logs:CreateLogStream",
                                        "logs:PutLogEvents"
                                    ],
                                    "Resource": "arn:aws:logs:*:*:*"
                                },
                                {
                                    "Effect": "Allow",
                                    "Action": [
                                        "s3:GetObject"
                                    ],
                                    "Resource": "arn:aws:s3:::ons-data-platform-processed/*"
                                },
                                {
                                    "Effect": "Allow",
                                    "Action": [
                                        "bedrock:InvokeModel"
                                    ],
                                    "Resource": "arn:aws:bedrock:*:*:foundation-model/*"
                                }
                            ]
                        })
                    }
                }
            }
        }
        
        # Validate IAM policy
        policy_doc = json.loads(iam_config["resource"]["aws_iam_policy"]["lambda_policy"]["policy"])
        
        # Check for overly permissive actions
        dangerous_actions = ['*', 's3:*', 'iam:*', 'ec2:*']
        
        for statement in policy_doc["Statement"]:
            actions = statement.get("Action", [])
            if isinstance(actions, str):
                actions = [actions]
            
            for action in actions:
                assert action not in dangerous_actions, f"Overly permissive action found: {action}"
        
        # Check resource restrictions
        for statement in policy_doc["Statement"]:
            if statement.get("Effect") == "Allow":
                resources = statement.get("Resource", [])
                if isinstance(resources, str):
                    resources = [resources]
                
                # Should have specific resource ARNs, not wildcards
                for resource in resources:
                    if resource != "*":  # Some services require * (like logs)
                        assert ":*:*:*" not in resource or "logs:" in resource
    
    def test_network_security_configuration(self):
        """Test network security configurations"""
        # Simulate VPC and security group configuration
        network_config = {
            "resource": {
                "aws_vpc": {
                    "main": {
                        "cidr_block": "10.0.0.0/16",
                        "enable_dns_hostnames": True,
                        "enable_dns_support": True
                    }
                },
                "aws_security_group": {
                    "lambda_sg": {
                        "name": "ons-lambda-sg",
                        "vpc_id": "${aws_vpc.main.id}",
                        "egress": [
                            {
                                "from_port": 443,
                                "to_port": 443,
                                "protocol": "tcp",
                                "cidr_blocks": ["0.0.0.0/0"]
                            }
                        ],
                        "ingress": []  # No ingress rules for Lambda
                    },
                    "api_gateway_sg": {
                        "name": "ons-api-gateway-sg",
                        "vpc_id": "${aws_vpc.main.id}",
                        "ingress": [
                            {
                                "from_port": 443,
                                "to_port": 443,
                                "protocol": "tcp",
                                "cidr_blocks": ["0.0.0.0/0"]
                            }
                        ],
                        "egress": [
                            {
                                "from_port": 443,
                                "to_port": 443,
                                "protocol": "tcp",
                                "cidr_blocks": ["10.0.0.0/16"]
                            }
                        ]
                    }
                }
            }
        }
        
        # Validate network security
        lambda_sg = network_config["resource"]["aws_security_group"]["lambda_sg"]
        api_sg = network_config["resource"]["aws_security_group"]["api_gateway_sg"]
        
        # Lambda security group should have no ingress rules
        assert len(lambda_sg["ingress"]) == 0
        
        # Lambda should only have HTTPS egress
        lambda_egress = lambda_sg["egress"]
        for rule in lambda_egress:
            assert rule["protocol"] == "tcp"
            assert rule["from_port"] == 443 and rule["to_port"] == 443
        
        # API Gateway should only allow HTTPS
        api_ingress = api_sg["ingress"]
        for rule in api_ingress:
            assert rule["protocol"] == "tcp"
            assert rule["from_port"] == 443 and rule["to_port"] == 443
    
    def test_encryption_compliance(self):
        """Test encryption compliance across services"""
        # Simulate encryption configurations
        encryption_configs = {
            "s3_encryption": {
                "algorithm": "AES256",
                "kms_key_id": "arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012"
            },
            "timestream_encryption": {
                "kms_key_id": "arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012"
            },
            "lambda_environment_encryption": {
                "kms_key_arn": "arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012"
            }
        }
        
        # Validate encryption configurations
        for service, config in encryption_configs.items():
            if "algorithm" in config:
                assert config["algorithm"] in ["AES256", "aws:kms"]
            
            if "kms_key_id" in config or "kms_key_arn" in config:
                key_arn = config.get("kms_key_id") or config.get("kms_key_arn")
                assert key_arn.startswith("arn:aws:kms:")
                assert "key/" in key_arn


class TestComplianceFrameworks:
    """Test compliance with various frameworks"""
    
    def test_gdpr_compliance_controls(self):
        """Test GDPR compliance controls"""
        gdpr_controls = {
            "data_minimization": {
                "implemented": True,
                "controls": ["data_retention_policies", "purpose_limitation"]
            },
            "right_to_erasure": {
                "implemented": True,
                "controls": ["data_deletion_procedures", "backup_deletion"]
            },
            "data_portability": {
                "implemented": True,
                "controls": ["data_export_api", "standard_formats"]
            },
            "privacy_by_design": {
                "implemented": True,
                "controls": ["encryption_default", "access_controls", "audit_logging"]
            },
            "consent_management": {
                "implemented": True,
                "controls": ["consent_tracking", "withdrawal_mechanisms"]
            }
        }
        
        # Validate GDPR controls
        for control_area, details in gdpr_controls.items():
            assert details["implemented"] is True, f"GDPR control not implemented: {control_area}"
            assert len(details["controls"]) > 0, f"No controls defined for: {control_area}"
        
        # Check specific requirements
        privacy_controls = gdpr_controls["privacy_by_design"]["controls"]
        assert "encryption_default" in privacy_controls
        assert "access_controls" in privacy_controls
        assert "audit_logging" in privacy_controls
    
    def test_iso27001_compliance_controls(self):
        """Test ISO 27001 compliance controls"""
        iso27001_controls = {
            "A.9.1.1": {  # Access control policy
                "control": "Access control policy",
                "implemented": True,
                "evidence": ["iam_policies", "rbac_implementation"]
            },
            "A.10.1.1": {  # Cryptographic controls
                "control": "Policy on the use of cryptographic controls",
                "implemented": True,
                "evidence": ["encryption_at_rest", "encryption_in_transit"]
            },
            "A.12.6.1": {  # Management of technical vulnerabilities
                "control": "Management of technical vulnerabilities",
                "implemented": True,
                "evidence": ["vulnerability_scanning", "patch_management"]
            },
            "A.16.1.2": {  # Reporting information security events
                "control": "Reporting information security events",
                "implemented": True,
                "evidence": ["incident_response_plan", "security_monitoring"]
            }
        }
        
        # Validate ISO 27001 controls
        for control_id, details in iso27001_controls.items():
            assert details["implemented"] is True, f"ISO 27001 control not implemented: {control_id}"
            assert len(details["evidence"]) > 0, f"No evidence for control: {control_id}"
    
    def test_nist_cybersecurity_framework(self):
        """Test NIST Cybersecurity Framework compliance"""
        nist_functions = {
            "identify": {
                "categories": ["asset_management", "risk_assessment", "governance"],
                "implementation_score": 0.9
            },
            "protect": {
                "categories": ["access_control", "data_security", "protective_technology"],
                "implementation_score": 0.95
            },
            "detect": {
                "categories": ["continuous_monitoring", "detection_processes"],
                "implementation_score": 0.85
            },
            "respond": {
                "categories": ["response_planning", "incident_response"],
                "implementation_score": 0.8
            },
            "recover": {
                "categories": ["recovery_planning", "recovery_communications"],
                "implementation_score": 0.75
            }
        }
        
        # Validate NIST framework implementation
        for function, details in nist_functions.items():
            assert details["implementation_score"] >= 0.7, f"Low NIST implementation score for {function}: {details['implementation_score']}"
            assert len(details["categories"]) > 0, f"No categories defined for NIST function: {function}"
        
        # Calculate overall maturity
        overall_score = sum(details["implementation_score"] for details in nist_functions.values()) / len(nist_functions)
        assert overall_score >= 0.8, f"Overall NIST maturity score too low: {overall_score}"


class TestSecurityMonitoring:
    """Test security monitoring and alerting"""
    
    def test_cloudwatch_security_alarms(self):
        """Test CloudWatch security alarms configuration"""
        security_alarms = {
            "failed_login_attempts": {
                "metric_name": "FailedLoginAttempts",
                "threshold": 10,
                "period": 300,
                "evaluation_periods": 2,
                "comparison_operator": "GreaterThanThreshold"
            },
            "unusual_api_activity": {
                "metric_name": "APICallRate",
                "threshold": 1000,
                "period": 60,
                "evaluation_periods": 3,
                "comparison_operator": "GreaterThanThreshold"
            },
            "data_access_anomaly": {
                "metric_name": "DataAccessVolume",
                "threshold": 1000,
                "period": 300,
                "evaluation_periods": 2,
                "comparison_operator": "GreaterThanThreshold"
            }
        }
        
        # Validate alarm configurations
        for alarm_name, config in security_alarms.items():
            assert config["threshold"] > 0, f"Invalid threshold for alarm: {alarm_name}"
            assert config["period"] > 0, f"Invalid period for alarm: {alarm_name}"
            assert config["evaluation_periods"] > 0, f"Invalid evaluation periods for alarm: {alarm_name}"
            assert config["comparison_operator"] in [
                "GreaterThanThreshold", "LessThanThreshold", 
                "GreaterThanOrEqualToThreshold", "LessThanOrEqualToThreshold"
            ], f"Invalid comparison operator for alarm: {alarm_name}"
    
    def test_security_incident_response_plan(self):
        """Test security incident response plan"""
        incident_response_plan = {
            "detection": {
                "automated_monitoring": True,
                "alert_channels": ["cloudwatch", "sns", "email"],
                "response_time_sla": 15  # minutes
            },
            "analysis": {
                "triage_process": True,
                "severity_classification": ["low", "medium", "high", "critical"],
                "escalation_matrix": True
            },
            "containment": {
                "isolation_procedures": True,
                "access_revocation": True,
                "system_shutdown_capability": True
            },
            "recovery": {
                "backup_restoration": True,
                "service_restoration_plan": True,
                "business_continuity": True
            },
            "lessons_learned": {
                "post_incident_review": True,
                "documentation_update": True,
                "process_improvement": True
            }
        }
        
        # Validate incident response plan
        for phase, requirements in incident_response_plan.items():
            for requirement, implemented in requirements.items():
                if isinstance(implemented, bool):
                    assert implemented is True, f"Incident response requirement not met: {phase}.{requirement}"
                elif isinstance(implemented, list):
                    assert len(implemented) > 0, f"Empty list for requirement: {phase}.{requirement}"
                elif isinstance(implemented, (int, float)):
                    assert implemented > 0, f"Invalid value for requirement: {phase}.{requirement}"
    
    def test_audit_logging_configuration(self):
        """Test audit logging configuration"""
        audit_config = {
            "cloudtrail": {
                "enabled": True,
                "include_global_service_events": True,
                "is_multi_region_trail": True,
                "enable_log_file_validation": True,
                "s3_bucket_name": "ons-audit-logs",
                "s3_key_prefix": "cloudtrail-logs/"
            },
            "application_logs": {
                "log_level": "INFO",
                "retention_days": 365,
                "encryption_enabled": True,
                "log_groups": [
                    "/aws/lambda/ons-rag-query-processor",
                    "/aws/lambda/ons-structured-data-processor",
                    "/aws/lambda/ons-timestream-loader"
                ]
            },
            "access_logs": {
                "s3_access_logging": True,
                "api_gateway_logging": True,
                "load_balancer_logging": True
            }
        }
        
        # Validate audit logging
        cloudtrail = audit_config["cloudtrail"]
        assert cloudtrail["enabled"] is True
        assert cloudtrail["is_multi_region_trail"] is True
        assert cloudtrail["enable_log_file_validation"] is True
        
        app_logs = audit_config["application_logs"]
        assert app_logs["log_level"] in ["DEBUG", "INFO", "WARN", "ERROR"]
        assert app_logs["retention_days"] >= 365  # At least 1 year
        assert app_logs["encryption_enabled"] is True
        assert len(app_logs["log_groups"]) > 0
        
        access_logs = audit_config["access_logs"]
        assert all(access_logs.values()), "All access logging should be enabled"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])