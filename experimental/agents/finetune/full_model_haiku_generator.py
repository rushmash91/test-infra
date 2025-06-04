#!/usr/bin/env python3
"""
Full Model Claude Haiku Dataset Generator for Bedrock Fine-Tuning

This creates training datasets using the FULL model.json approach by:
1. Taking the complete AWS SDK model.json (entire file, not trimmed)
2. Taking a resource name as the specific request
3. Using the full model + resource name as input
4. Using the complete generator.yaml resource configuration as output
5. Formatting in Claude 3 Haiku single-turn format for Bedrock

This is different from the resource_focused_generator which creates trimmed models.
This approach provides the full context of the entire AWS service model.
"""

import json
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path

from data_extractor import (
    FinetuningDataGenerator, 
    GeneratorConfigExtractor, 
    ModelFileExtractor, 
    SERVICE_CONTROLLERS
)
from utils.repo import ensure_aws_sdk_go_v2_cloned, ensure_service_repo_cloned, check_service_controller_exists

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

class FullModelHaikuGenerator(FinetuningDataGenerator):
    """Generates Claude 3 Haiku format datasets using full model.json files."""
    
    def __init__(self, output_file: str = "full_model_haiku_bedrock.jsonl"):
        super().__init__(output_file, use_conversation_format=True)
        
    def create_haiku_training_entry(self, model_data: Dict[str, Any], resource_name: str, service: str, resource_config: str) -> Dict[str, Any]:
        """Create a Claude 3 Haiku single-turn format training entry with full model.json."""
        
        # Create comprehensive system message
        system_message = (
            "You are an AWS ACK (AWS Controllers for Kubernetes) configuration generator. "
            f"You analyze complete AWS SDK model definitions for the {service} service "
            "and generate accurate generator.yaml configurations for ACK controllers. "
            "You understand AWS API models, resource operations, field mappings, and ACK patterns."
        )
        
        # Create user message with full model and specific resource request
        user_message = (
            f"Given the following complete AWS SDK model definition for the {service} service, "
            f"generate the ACK generator.yaml configuration for the {resource_name} resource.\n\n"
            f"AWS SDK Model (Complete):\n{json.dumps(model_data, indent=2)}\n\n"
            f"Generate the ACK generator.yaml configuration for the {resource_name} resource:"
        )
        
        # Create Claude 3 Haiku single-turn format (no schemaVersion)
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
    
    def process_service_full_model(self, service: str) -> List[Dict[str, Any]]:
        """Process a service generating entries with full model.json for each resource."""
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
            
            # Load FULL model once
            model_data = self.model_extractor.load_service_model(service, gen_config)
            if not model_data:
                logger.warning(f"No model data for {service}")
                return entries
            
            # Calculate model size for tracking
            model_size_mb = len(json.dumps(model_data)) / (1024 * 1024)
            operations_count = len([s for s in model_data.get("shapes", {}).values() if s.get("type") == "operation"])
            shapes_count = len([s for s in model_data.get("shapes", {}).values() if s.get("type") != "operation"])
            
            logger.info(f"Using full model for {service}: {model_size_mb:.1f}MB, {operations_count} operations, {shapes_count} shapes")
            
            # Generate entry for each resource using the FULL model
            for resource_name in configured_resources:
                logger.info(f"Creating full-model entry for {service}::{resource_name}")
                
                # Get resource configuration
                resource_config = self.config_extractor.get_resource_config_yaml(gen_config, resource_name)
                
                # Create training entry with full model
                entry = self.create_haiku_training_entry(model_data, resource_name, service, resource_config)
                entries.append(entry)
                
                logger.debug(f"Created full-model entry for {service}::{resource_name}")
            
        except Exception as e:
            logger.error(f"Error processing service {service}: {e}")
        
        return entries
    
    def generate_full_model_dataset(self, services: Optional[List[str]] = None) -> bool:
        """Generate a dataset using full model.json files for each resource."""
        if not self.initialize_aws_sdk():
            return False
        
        if services is None:
            # Default to key services
            services = ["s3", "lambda", "rds", "ec2", "iam"]
        
        logger.info(f"Generating full-model dataset for {len(services)} services")
        
        all_entries = []
        total_resources = 0
        
        with open(self.output_file, 'w') as output_file:
            for service in services:
                if not check_service_controller_exists(service):
                    logger.warning(f"Service controller {service} does not exist, skipping")
                    continue
                
                entries = self.process_service_full_model(service)
                
                for entry in entries:
                    output_file.write(json.dumps(entry) + "\n")
                    all_entries.append(entry)
                    total_resources += 1
                
                logger.info(f"Added {len(entries)} full-model entries for {service}")
        
        # Generate summary
        file_size = Path(self.output_file).stat().st_size / (1024 * 1024)
        
        logger.info(f"\n📊 FULL MODEL DATASET SUMMARY:")
        logger.info(f"  Total Entries: {len(all_entries)}")
        logger.info(f"  Total Resources: {total_resources}")
        logger.info(f"  File Size: {file_size:.1f} MB")
        logger.info(f"  Approach: Full model.json with resource-specific requests")
        logger.info(f"  Format: Claude 3 Haiku single-turn")
        
        return True
    
    def _resolve_service_name(self, service: str) -> str:
        """Resolve service name using mappings if needed."""
        # First try the service name as-is
        if check_service_controller_exists(service):
            return service
        
        # Try mapped names if available
        if service in SERVICE_MAPPINGS:
            for mapped_name in SERVICE_MAPPINGS[service]:
                if check_service_controller_exists(mapped_name):
                    logger.info(f"Using mapped service name: {service} -> {mapped_name}")
                    return mapped_name
        
        # Return original if no mapping works
        return service
    
    def generate_all_services_full_model_dataset(self, output_file: str = "all_services_full_model_haiku.jsonl") -> bool:
        """Generate full-model dataset for all AWS services."""
        if not self.initialize_aws_sdk():
            return False
        
        logger.info(f"Generating full-model dataset for {len(ALL_AWS_SERVICES)} AWS services")
        
        all_entries = []
        total_resources = 0
        services_processed = 0
        services_failed = 0
        
        with open(output_file, 'w') as output_file_handle:
            for i, service in enumerate(ALL_AWS_SERVICES, 1):
                logger.info(f"Processing service {i}/{len(ALL_AWS_SERVICES)}: {service}")
                
                try:
                    # Resolve service name using mappings
                    resolved_service = self._resolve_service_name(service)
                    
                    if not check_service_controller_exists(resolved_service):
                        logger.warning(f"Service controller {resolved_service} does not exist, skipping")
                        services_failed += 1
                        continue
                    
                    entries = self.process_service_full_model(resolved_service)
                    
                    if not entries:
                        logger.warning(f"No entries generated for service {service}")
                        services_failed += 1
                        continue
                    
                    for entry in entries:
                        output_file_handle.write(json.dumps(entry) + "\n")
                        all_entries.append(entry)
                        total_resources += 1
                    
                    services_processed += 1
                    logger.info(f"✅ {service}: Added {len(entries)} full-model entries")
                    
                except Exception as e:
                    logger.error(f"❌ Failed to process service {service}: {e}")
                    services_failed += 1
                    continue
        
        # Generate comprehensive summary
        file_size = Path(output_file).stat().st_size / (1024 * 1024)
        
        logger.info(f"\n🎯 COMPREHENSIVE FULL MODEL DATASET SUMMARY:")
        logger.info(f"  Services Attempted: {len(ALL_AWS_SERVICES)}")
        logger.info(f"  Services Processed: {services_processed}")
        logger.info(f"  Services Failed: {services_failed}")
        logger.info(f"  Total Entries: {len(all_entries)}")
        logger.info(f"  Total Resources: {total_resources}")
        logger.info(f"  File Size: {file_size:.1f} MB")
        logger.info(f"  Success Rate: {(services_processed/len(ALL_AWS_SERVICES)*100):.1f}%")
        logger.info(f"  Approach: Full model.json with resource-specific requests")
        logger.info(f"  Format: Claude 3 Haiku single-turn")
        
        return services_processed > 0


def main():
    """Generate full-model fine-tuning dataset in Claude 3 Haiku format."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate full-model ACK fine-tuning dataset in Claude 3 Haiku format")
    parser.add_argument("--output", "-o", default="full_model_haiku_bedrock.jsonl",
                        help="Output JSONL file path")
    parser.add_argument("--services", "-s", nargs="*", 
                        help="List of services to process")
    parser.add_argument("--all-services", action="store_true",
                        help="Process all AWS services listed in the configuration")
    parser.add_argument("--verbose", "-v", action="store_true")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    generator = FullModelHaikuGenerator(output_file=args.output)
    
    if args.all_services:
        # Generate for all AWS services
        logger.info("🚀 Generating comprehensive full-model dataset for all AWS services...")
        success = generator.generate_all_services_full_model_dataset(output_file=args.output)
    else:
        # Generate for specified services or defaults
        success = generator.generate_full_model_dataset(services=args.services)
    
    if success:
        logger.info(f"✅ Full-model dataset generated successfully: {args.output}")
    else:
        logger.error("❌ Dataset generation failed")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main()) 