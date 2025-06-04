#!/usr/bin/env python3
"""
Ultra-Compact Dataset Generator for Bedrock Fine-Tuning

This creates ultra-compact training datasets that fit within Bedrock's 32K token limit by:
1. Using only essential metadata (service name, protocol)
2. Including only 2-3 key operations per resource 
3. Minimal shape information (just structure, not full details)
4. Focusing on the core mapping patterns

Perfect for staying within Bedrock's strict token limits.
"""

import json
import logging
import yaml
from typing import Dict, List, Any, Optional, Set
from pathlib import Path

from data_extractor import (
    FinetuningDataGenerator, 
    GeneratorConfigExtractor, 
    ModelFileExtractor
)
from utils.repo import ensure_aws_sdk_go_v2_cloned, ensure_service_repo_cloned, check_service_controller_exists

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Complete list of AWS services for ACK
ALL_AWS_SERVICES = [
    "acm", "acmpca", "apigateway", "apigatewayv2", "applicationautoscaling", 
    "athena", "batch", "bedrockagent", "cognitoidentity", "cloudfront", 
    "cloudtrail", "cloudwatch", "cloudwatchevents", "cloudwatchlogs", 
    "codeartifact", "cognitoidentityprovider", "documentdb", "dynamodb", 
    "ebs", "ec2", "ecr", "ecrpublic", "ecs", "efs", "eks", "elasticache", 
    "elbv2", "emrcontainers", "eventbridge", "globalaccelerator", "glue", 
    "iam", "kafka", "kinesis", "kms", "keyspaces", "lambda", "memorydb", 
    "mq", "networkfirewall", "opensearchservice", "opensearchserverless", 
    "organizations", "pipes", "prometheusservice", "ram", "rds", 
    "recyclebin", "route53", "route53resolver", "s3", "s3control", 
    "sagemaker", "secretsmanager", "servicecatalog", "ses", "sfn", 
    "sns", "sqs", "ssm", "transfer", "wafv2"
]

# Service mappings for ACK controllers that have different names than AWS SDK
SERVICE_MAPPINGS = {
    "acmpca": ["acm-pca"],
    "applicationautoscaling": ["application-auto-scaling"],
    "cloudwatchevents": ["cloudwatch-events", "eventbridge"],
    "cloudwatchlogs": ["cloudwatch-logs"],
    "cognitoidentity": ["cognito-identity"],
    "cognitoidentityprovider": ["cognito-identity-provider"],
    "documentdb": ["docdb"],
    "ecrpublic": ["ecr-public"],
    "elbv2": ["elastic-load-balancing-v2"],
    "emrcontainers": ["emr-containers"],
    "globalaccelerator": ["global-accelerator"],
    "networkfirewall": ["network-firewall"],
    "opensearchservice": ["elasticsearch-service", "opensearch"],
    "prometheusservice": ["amp"],
    "recyclebin": ["rbin"],
    "s3control": ["s3-control"],
    "secretsmanager": ["secrets-manager"],
    "servicecatalog": ["service-catalog"],
    "bedrockagent": ["bedrock-agent"]
}

class UltraCompactGenerator(FinetuningDataGenerator):
    """Generates ultra-compact fine-tuning datasets that fit within Bedrock's 32K token limit."""
    
    def __init__(self, output_file: str = "ultra_compact_bedrock.jsonl"):
        super().__init__(output_file, use_conversation_format=True)
        self.max_operations = 3  # Limit to 3 operations per resource
        self.max_shapes = 5      # Limit to 5 shapes per resource
        
    def extract_ultra_compact_model(self, model_data: Dict[str, Any], resource_name: str) -> Dict[str, Any]:
        """Extract an ultra-compact model that fits within token limits."""
        
        # Extract minimal service metadata
        minimal_metadata = self._extract_minimal_metadata(model_data)
        
        # Find the most relevant operations for this resource
        shapes = model_data.get("shapes", {})
        key_operations = self._find_key_operations(resource_name, shapes)
        
        # Create ultra-compact model
        compact_model = {
            "service": minimal_metadata,
            "resource": resource_name,
            "operations": key_operations,
            "note": "Ultra-compact representation for Bedrock fine-tuning"
        }
        
        return compact_model
    
    def _extract_minimal_metadata(self, model_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract only essential service metadata."""
        shapes = model_data.get("shapes", {})
        
        # Find service shape for basic info
        service_name = "unknown"
        protocol = "unknown"
        
        for shape_name, shape_data in shapes.items():
            if shape_data.get("type") == "service":
                traits = shape_data.get("traits", {})
                
                # Extract service name
                if "#" in shape_name:
                    service_name = shape_name.split("#")[-1].lower()
                    if service_name.startswith("amazon"):
                        service_name = service_name[6:]
                
                # Extract protocol (minimal)
                if "aws.protocols#restXml" in traits:
                    protocol = "rest-xml"
                elif "aws.protocols#restJson1" in traits:
                    protocol = "rest-json"
                elif "aws.protocols#awsJson1_1" in traits:
                    protocol = "json"
                break
        
        return {
            "name": service_name,
            "protocol": protocol
        }
    
    def _find_key_operations(self, resource_name: str, shapes: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find the most important operations for this resource (limited to stay under token limit)."""
        
        resource_lower = resource_name.lower()
        operation_patterns = [
            f"Create{resource_name}",
            f"Get{resource_name}",
            f"Update{resource_name}",
            f"Delete{resource_name}",
            f"Describe{resource_name}",
            f"Put{resource_name}",
            f"List{resource_name}s",
            f"List{resource_name}"
        ]
        
        found_operations = []
        
        # Look for exact pattern matches first
        for shape_name, shape_def in shapes.items():
            if shape_def.get("type") == "operation" and len(found_operations) < self.max_operations:
                op_name = shape_name.split("#")[-1] if "#" in shape_name else shape_name
                
                # Check for exact pattern matches
                if op_name in operation_patterns:
                    found_operations.append({
                        "name": op_name,
                        "type": self._determine_operation_type(op_name),
                        "input": self._get_minimal_shape_info(shape_def.get("input", {}), shapes),
                        "output": self._get_minimal_shape_info(shape_def.get("output", {}), shapes)
                    })
        
        # If we don't have enough, look for partial matches
        if len(found_operations) < self.max_operations:
            for shape_name, shape_def in shapes.items():
                if shape_def.get("type") == "operation" and len(found_operations) < self.max_operations:
                    op_name = shape_name.split("#")[-1] if "#" in shape_name else shape_name
                    
                    # Check if resource name is in operation name
                    if (resource_lower in op_name.lower() and 
                        not any(op["name"] == op_name for op in found_operations)):
                        found_operations.append({
                            "name": op_name,
                            "type": self._determine_operation_type(op_name),
                            "input": self._get_minimal_shape_info(shape_def.get("input", {}), shapes),
                            "output": self._get_minimal_shape_info(shape_def.get("output", {}), shapes)
                        })
        
        return found_operations
    
    def _determine_operation_type(self, op_name: str) -> str:
        """Determine the type of operation based on its name."""
        op_lower = op_name.lower()
        if op_lower.startswith(("create", "put")):
            return "Create"
        elif op_lower.startswith(("get", "describe", "list")):
            return "Read"
        elif op_lower.startswith(("update", "modify")):
            return "Update"
        elif op_lower.startswith("delete"):
            return "Delete"
        else:
            return "Unknown"
    
    def _get_minimal_shape_info(self, shape_ref: Dict[str, Any], all_shapes: Dict[str, Any]) -> Dict[str, Any]:
        """Get minimal information about a shape reference."""
        if not shape_ref or "target" not in shape_ref:
            return {}
        
        target = shape_ref["target"]
        if target not in all_shapes:
            return {"target": target}
        
        shape_def = all_shapes[target]
        shape_type = shape_def.get("type", "unknown")
        
        # For structures, include a few key members
        if shape_type == "structure":
            members = shape_def.get("members", {})
            key_members = {}
            
            # Include up to 3 members
            count = 0
            for member_name, member_def in members.items():
                if count >= 3:
                    break
                key_members[member_name] = {
                    "type": member_def.get("target", "unknown").split("#")[-1] if "target" in member_def else "string"
                }
                count += 1
            
            return {
                "target": target,
                "type": shape_type,
                "members": key_members
            }
        else:
            return {
                "target": target,
                "type": shape_type
            }
    
    def create_ultra_compact_entry(self, model_data: Dict[str, Any], resource_name: str, service: str, resource_config: str) -> Dict[str, Any]:
        """Create an ultra-compact training entry that fits within token limits."""
        
        # Extract ultra-compact model
        compact_model = self.extract_ultra_compact_model(model_data, resource_name)
        
        # Create compact system message
        system_message = (
            f"You are an AWS ACK generator for {service}. "
            "Generate YAML configurations from compact AWS API definitions."
        )
        
        # Create compact user message
        user_message = (
            f"Generate ACK generator.yaml for {resource_name} resource in {service}:\n\n"
            f"AWS API: {json.dumps(compact_model, indent=1)}\n\n"
            f"Generate generator.yaml for {resource_name}:"
        )
        
        # Create Claude 3 Haiku single-turn format
        entry = {
            "system": system_message,
            "messages": [
                {
                    "role": "user",
                    "content": user_message
                },
                {
                    "role": "assistant", 
                    "content": resource_config
                }
            ]
        }
        
        return entry
    
    def process_service_ultra_compact(self, service: str) -> List[Dict[str, Any]]:
        """Process a service generating ultra-compact entries for each resource."""
        entries = []
        
        try:
            repo_path = ensure_service_repo_cloned(service)
            logger.info(f"Processing service: {service}")
            
            # Load generator config
            gen_config = self.config_extractor.load_generator_config(repo_path)
            if not gen_config:
                logger.warning(f"No generator config for {service}")
                return entries
            
            # Get configured resources
            service_resources = self.config_extractor.extract_all_resources(gen_config)
            configured_resources = service_resources.configured_resources
            
            logger.info(f"Found {len(configured_resources)} configured resources in {service}")
            
            # Load full model once
            model_data = self.model_extractor.load_service_model(service, gen_config)
            if not model_data:
                logger.warning(f"No model data for {service}")
                return entries
            
            # Generate ultra-compact entry for each resource
            for resource_name in configured_resources:
                logger.info(f"Creating ultra-compact entry for {service}::{resource_name}")
                
                # Get resource configuration
                resource_config = self.config_extractor.get_resource_config_yaml(gen_config, resource_name)
                
                # Create ultra-compact training entry
                entry = self.create_ultra_compact_entry(model_data, resource_name, service, resource_config)
                entries.append(entry)
            
        except Exception as e:
            logger.error(f"Error processing service {service}: {e}")
        
        return entries
    
    def _resolve_service_name(self, service: str) -> str:
        """Resolve service name using mappings if needed."""
        if check_service_controller_exists(service):
            return service
        
        if service in SERVICE_MAPPINGS:
            for mapped_name in SERVICE_MAPPINGS[service]:
                if check_service_controller_exists(mapped_name):
                    logger.info(f"Using mapped service name: {service} -> {mapped_name}")
                    return mapped_name
        
        return service
    
    def generate_ultra_compact_dataset(self, services: Optional[List[str]] = None, max_services: int = 20) -> bool:
        """Generate ultra-compact dataset that fits within Bedrock limits."""
        if not self.initialize_aws_sdk():
            return False
        
        if services is None:
            # Use first 20 services to stay within limits
            services = ALL_AWS_SERVICES[:max_services]
        
        logger.info(f"Generating ultra-compact dataset for {len(services)} services")
        
        all_entries = []
        total_resources = 0
        
        with open(self.output_file, 'w') as output_file:
            for service in services:
                resolved_service = self._resolve_service_name(service)
                
                if not check_service_controller_exists(resolved_service):
                    logger.warning(f"Service controller {resolved_service} does not exist, skipping")
                    continue
                
                entries = self.process_service_ultra_compact(resolved_service)
                
                for entry in entries:
                    output_file.write(json.dumps(entry) + "\n")
                    all_entries.append(entry)
                    total_resources += 1
                
                logger.info(f"Added {len(entries)} ultra-compact entries for {service}")
        
        # Generate summary
        file_size = Path(self.output_file).stat().st_size / (1024 * 1024)
        
        logger.info(f"\n🎯 ULTRA-COMPACT DATASET SUMMARY:")
        logger.info(f"  Total Entries: {len(all_entries)}")
        logger.info(f"  Total Resources: {total_resources}")
        logger.info(f"  File Size: {file_size:.1f} MB")
        logger.info(f"  Approach: Ultra-compact for Bedrock 32K token limit")
        logger.info(f"  Format: Claude 3 Haiku single-turn")
        
        return True


def main():
    """Generate ultra-compact fine-tuning dataset."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate ultra-compact ACK fine-tuning dataset")
    parser.add_argument("--output", "-o", default="ultra_compact_bedrock.jsonl",
                        help="Output JSONL file path")
    parser.add_argument("--services", "-s", nargs="*", 
                        help="List of services to process")
    parser.add_argument("--max-services", type=int, default=20,
                        help="Maximum number of services to include")
    parser.add_argument("--verbose", "-v", action="store_true")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    generator = UltraCompactGenerator(output_file=args.output)
    
    success = generator.generate_ultra_compact_dataset(
        services=args.services, 
        max_services=args.max_services
    )
    
    if success:
        logger.info(f"✅ Ultra-compact dataset generated successfully: {args.output}")
    else:
        logger.error("❌ Dataset generation failed")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main()) 