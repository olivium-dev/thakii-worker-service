#!/usr/bin/env python3
"""
Centralized Authentication Manager for Thakii Worker Service
Provides unified authentication status, monitoring, and health checks
"""

import os
import json
import datetime
from typing import Dict, Any, List
from dotenv import load_dotenv
import logging

# Import secure clients
from .secure_firestore_client import secure_firestore_client
from .secure_s3_client import secure_s3_client

# Load environment variables
load_dotenv()

# Setup logging
logger = logging.getLogger(__name__)

class AuthenticationManager:
    """Centralized authentication management and monitoring"""
    
    def __init__(self):
        self.firebase_client = secure_firestore_client
        self.s3_client = secure_s3_client
        self._start_time = datetime.datetime.now()
        
        logger.info("🔐 Authentication Manager initialized")
    
    def get_authentication_status(self) -> Dict[str, Any]:
        """Get comprehensive authentication status"""
        status = {
            "timestamp": datetime.datetime.now().isoformat(),
            "manager_uptime_seconds": (datetime.datetime.now() - self._start_time).total_seconds(),
            "firebase": self.firebase_client.get_credential_info(),
            "s3": self.s3_client.get_credential_info(),
            "overall_status": "unknown"
        }
        
        # Determine overall status
        firebase_ok = status["firebase"]["available"]
        s3_ok = status["s3"]["available"]
        
        if firebase_ok and s3_ok:
            status["overall_status"] = "healthy"
        elif firebase_ok or s3_ok:
            status["overall_status"] = "partial"
        else:
            status["overall_status"] = "failed"
        
        return status
    
    def perform_health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check of all authentication systems"""
        logger.info("🔍 Starting comprehensive authentication health check")
        
        health_check = {
            "timestamp": datetime.datetime.now().isoformat(),
            "manager_info": {
                "uptime_seconds": (datetime.datetime.now() - self._start_time).total_seconds(),
                "environment_variables": self._check_environment_variables()
            },
            "firebase": self.firebase_client.health_check(),
            "s3": self.s3_client.health_check(),
            "overall_health": "unknown"
        }
        
        # Determine overall health
        firebase_healthy = health_check["firebase"]["firestore_available"]
        s3_healthy = health_check["s3"]["s3_available"]
        
        if firebase_healthy and s3_healthy:
            health_check["overall_health"] = "healthy"
            logger.info("✅ All authentication systems healthy")
        elif firebase_healthy or s3_healthy:
            health_check["overall_health"] = "partial"
            logger.warning("⚠️ Some authentication systems unavailable")
        else:
            health_check["overall_health"] = "failed"
            logger.error("❌ All authentication systems failed")
        
        return health_check
    
    def _check_environment_variables(self) -> Dict[str, Any]:
        """Check status of required environment variables"""
        env_status = {
            "firebase": {},
            "aws": {},
            "general": {}
        }
        
        # Firebase environment variables
        firebase_vars = [
            'FIREBASE_SERVICE_ACCOUNT_KEY',
            'FIREBASE_SERVICE_ACCOUNT_B64',
            'GOOGLE_APPLICATION_CREDENTIALS'
        ]
        
        for var in firebase_vars:
            value = os.getenv(var)
            env_status["firebase"][var] = {
                "set": value is not None,
                "length": len(value) if value else 0,
                "type": "file_path" if var.endswith('_KEY') else "base64" if var.endswith('_B64') else "credentials"
            }
        
        # AWS environment variables
        aws_vars = [
            'AWS_ACCESS_KEY_ID',
            'AWS_SECRET_ACCESS_KEY',
            'AWS_DEFAULT_REGION',
            'S3_BUCKET_NAME'
        ]
        
        for var in aws_vars:
            value = os.getenv(var)
            env_status["aws"][var] = {
                "set": value is not None,
                "length": len(value) if value else 0,
                "valid_format": self._validate_aws_var_format(var, value)
            }
        
        # General environment variables
        general_vars = [
            'WORKER_POLL_INTERVAL',
            'MAX_CONCURRENT_TASKS',
            'DEBUG_MODE'
        ]
        
        for var in general_vars:
            value = os.getenv(var)
            env_status["general"][var] = {
                "set": value is not None,
                "value": value
            }
        
        return env_status
    
    def _validate_aws_var_format(self, var_name: str, value: str) -> bool:
        """Validate AWS environment variable formats"""
        if not value:
            return False
        
        if var_name == 'AWS_ACCESS_KEY_ID':
            return value.startswith('AKIA') or value.startswith('ASIA')
        elif var_name == 'AWS_SECRET_ACCESS_KEY':
            return len(value) >= 40  # AWS secret keys are typically 40+ characters
        elif var_name == 'AWS_DEFAULT_REGION':
            return len(value) >= 9 and '-' in value  # e.g., us-east-1
        elif var_name == 'S3_BUCKET_NAME':
            return len(value) >= 3 and len(value) <= 63  # S3 bucket name limits
        
        return True
    
    def get_security_recommendations(self) -> List[Dict[str, Any]]:
        """Get security recommendations based on current configuration"""
        recommendations = []
        
        # Check Firebase security
        firebase_info = self.firebase_client.get_credential_info()
        if firebase_info["credential_source"] == "service_account_file":
            recommendations.append({
                "category": "firebase",
                "severity": "medium",
                "title": "Service Account File Usage",
                "description": "Using service account file instead of base64 encoded credentials",
                "recommendation": "Consider using FIREBASE_SERVICE_ACCOUNT_B64 for better security"
            })
        
        # Check AWS security
        s3_info = self.s3_client.get_credential_info()
        if s3_info["credential_source"] == "environment_variables":
            recommendations.append({
                "category": "aws",
                "severity": "low",
                "title": "Environment Variable Credentials",
                "description": "Using AWS credentials from environment variables",
                "recommendation": "Consider using IAM roles for production deployment"
            })
        
        # Check environment variable security
        env_status = self._check_environment_variables()
        
        # Check for missing critical variables
        if not any(env_status["firebase"][var]["set"] for var in env_status["firebase"]):
            recommendations.append({
                "category": "firebase",
                "severity": "high",
                "title": "No Firebase Credentials",
                "description": "No Firebase authentication credentials configured",
                "recommendation": "Set FIREBASE_SERVICE_ACCOUNT_B64 or FIREBASE_SERVICE_ACCOUNT_KEY"
            })
        
        if not env_status["aws"]["AWS_ACCESS_KEY_ID"]["set"]:
            recommendations.append({
                "category": "aws",
                "severity": "high",
                "title": "No AWS Credentials",
                "description": "No AWS authentication credentials configured",
                "recommendation": "Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY or configure IAM role"
            })
        
        return recommendations
    
    def generate_security_report(self) -> Dict[str, Any]:
        """Generate comprehensive security report"""
        logger.info("📊 Generating security report")
        
        report = {
            "timestamp": datetime.datetime.now().isoformat(),
            "report_version": "1.0",
            "authentication_status": self.get_authentication_status(),
            "health_check": self.perform_health_check(),
            "security_recommendations": self.get_security_recommendations(),
            "summary": {}
        }
        
        # Generate summary
        auth_status = report["authentication_status"]["overall_status"]
        health_status = report["health_check"]["overall_health"]
        recommendations_count = len(report["security_recommendations"])
        
        high_severity_count = sum(1 for rec in report["security_recommendations"] if rec["severity"] == "high")
        
        report["summary"] = {
            "authentication_status": auth_status,
            "health_status": health_status,
            "total_recommendations": recommendations_count,
            "high_severity_issues": high_severity_count,
            "security_score": self._calculate_security_score(report),
            "overall_assessment": self._get_overall_assessment(auth_status, health_status, high_severity_count)
        }
        
        logger.info(f"📊 Security report generated - Score: {report['summary']['security_score']}/10")
        
        return report
    
    def _calculate_security_score(self, report: Dict[str, Any]) -> int:
        """Calculate security score from 0-10"""
        score = 10
        
        # Deduct for authentication issues
        if report["authentication_status"]["overall_status"] == "failed":
            score -= 5
        elif report["authentication_status"]["overall_status"] == "partial":
            score -= 2
        
        # Deduct for health issues
        if report["health_check"]["overall_health"] == "failed":
            score -= 3
        elif report["health_check"]["overall_health"] == "partial":
            score -= 1
        
        # Deduct for security recommendations
        for rec in report["security_recommendations"]:
            if rec["severity"] == "high":
                score -= 2
            elif rec["severity"] == "medium":
                score -= 1
        
        return max(0, score)
    
    def _get_overall_assessment(self, auth_status: str, health_status: str, high_severity_count: int) -> str:
        """Get overall security assessment"""
        if auth_status == "healthy" and health_status == "healthy" and high_severity_count == 0:
            return "excellent"
        elif auth_status in ["healthy", "partial"] and health_status in ["healthy", "partial"] and high_severity_count <= 1:
            return "good"
        elif auth_status != "failed" and health_status != "failed":
            return "needs_improvement"
        else:
            return "critical"

# Create global instance
auth_manager = AuthenticationManager()
