# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You may not use this file except in compliance
# with the License. A copy of the License is located at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# or in the 'license' file accompanying this file. This file is distributed on an 'AS IS' BASIS, WITHOUT WARRANTIES
# OR CONDITIONS OF ANY KIND, express or implied. See the License for the specific language governing permissions
# and limitations under the License.
"""
Data extractor for preparing fine-tuning data from AWS SDK Go V2 models and ACK generator configurations.

This module works backwards from generator.yaml files (the authoritative source) to find corresponding 
AWS SDK Go V2 model definitions, extracting comprehensive information about resources including all 
operations, detailed shapes, errors, and metadata.
"""

import json
import os
import re
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Set
import requests
from dataclasses import dataclass, field
import logging

from utils.repo import (
    ensure_service_repo_cloned,
    ensure_aws_sdk_go_v2_cloned,
    check_service_controller_exists
)
from utils.settings import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class OperationInfo:
    """Represents detailed information about an AWS API operation."""
    name: str
    operation_type: str  # Create, Delete, Update, Describe, List, etc.
    input_shape_name: Optional[str] = None
    output_shape_name: Optional[str] = None
    input_fields: Dict[str, Any] = field(default_factory=dict)
    output_fields: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    documentation: Optional[str] = None
    deprecated: bool = False
    idempotent: bool = False


@dataclass
class ShapeInfo:
    """Represents detailed information about an AWS SDK shape."""
    name: str
    type: str  # structure, string, integer, list, map, etc.
    members: Dict[str, Any] = field(default_factory=dict)
    documentation: Optional[str] = None
    required: List[str] = field(default_factory=list)
    sensitive: bool = False
    deprecated: bool = False
    enum_values: List[str] = field(default_factory=list)


@dataclass
class ResourceDefinition:
    """Represents comprehensive resource definition extracted from AWS SDK model."""
    name: str
    operations: Dict[str, OperationInfo] = field(default_factory=dict)
    shapes: Dict[str, ShapeInfo] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    service_metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_primary_operation(self) -> Optional[OperationInfo]:
        """Get the primary Create operation for this resource."""
        create_op_name = f"Create{self.name}"
        return self.operations.get(create_op_name)


@dataclass
class ResourceConfig:
    """Represents a resource configuration from generator.yaml."""
    name: str
    is_ignored: bool
    is_configured: bool
    config_yaml: Optional[str] = None


@dataclass
class ServiceResources:
    """Contains all resources found for a service from generator.yaml."""
    service_name: str
    configured_resources: Set[str]
    ignored_resources: Set[str]
    all_resources: Set[str]


# List of known ACK service controllers
# This list can be extended or dynamically fetched
SERVICE_CONTROLLERS = [
    "acmpca", "acm", "prometheusservice", "apigateway", "apigatewayv2", 
    "applicationautoscaling", "athena", "cloudfront", "cloudtrail", 
    "cloudwatchlogs", "ec2", "ecr", "ecrpublic", "ecs", "efs", "eks", 
    "emrcontainers", "elasticsearchservice", "eventbridge", "iam", 
    "kafka", "keyspaces", "kinesis", "kms", "lambda", "memorydb", "mq", 
    "networkfirewall", "opensearchservice", "organizations", "pipes", 
    "ram", "recyclebin", "rds", "route53", "route53resolver", "s3", 
    "s3control", "sagemaker", "secretsmanager", "sns", "sqs", "ssm", 
    "sfn", "wafv2"
]

# Map of service controller to AWS model file name patterns (for special cases)
MODEL_FILE_OVERRIDES = {
    "prometheusservice": "amp.2020-08-01.json",
    "acmpca": "acm-pca.2017-08-22.json", 
    "cloudwatchlogs": "logs.2014-03-28.json",
    "elasticsearchservice": "es.2015-01-01.json",
    "opensearchservice": "opensearch.2021-01-01.json",
    "ecrpublic": "ecr-public.2020-10-30.json",
    "applicationautoscaling": "application-auto-scaling.2016-02-06.json",
    "emrcontainers": "emr-containers.2020-10-01.json",
    "route53resolver": "route53resolver.2016-01-01.json",
    "secretsmanager": "secretsmanager.2017-10-17.json",
    "apigateway": "api-gateway.json",
}


class GeneratorConfigExtractor:
    """Extracts resource configurations from generator.yaml files - our authoritative source."""
    
    def load_generator_config(self, repo_path: str) -> Optional[Dict[str, Any]]:
        """Load and parse the generator.yaml file from a repository."""
        gen_path = Path(repo_path) / "generator.yaml"
        if not gen_path.exists():
            logger.warning(f"No generator.yaml found in {repo_path}")
            return None
            
        try:
            with open(gen_path, 'r') as f:
                return yaml.safe_load(f)
        except yaml.YAMLError as e:
            logger.error(f"Failed to parse generator.yaml in {repo_path}: {e}")
            return None
    
    def extract_all_resources(self, gen_config: Dict[str, Any]) -> ServiceResources:
        """Extract all resources mentioned in generator.yaml (configured, ignored, and inferred)."""
        # Get explicitly configured resources
        configured_resources = set(gen_config.get("resources", {}).keys())
        
        # Get explicitly ignored resources
        ignored_resources = set(gen_config.get("ignore", {}).get("resource_names", []))
        
        # For JSONL generation, we only want configured + default resources (NOT ignored ones)
        # All resources = what ACK knows about, but we'll filter ignored ones out during generation
        all_resources = configured_resources | ignored_resources
        
        return ServiceResources(
            service_name="",  # Will be set by caller
            configured_resources=configured_resources,
            ignored_resources=ignored_resources,
            all_resources=all_resources
        )
    
    def get_resource_config_yaml(self, config: Dict[str, Any], resource_name: str) -> str:
        """Get the YAML configuration section for a specific resource."""
        resources_config = config.get('resources', {})
        
        # Check if resource has specific configuration
        if resource_name in resources_config:
            resource_config = {resource_name: resources_config[resource_name]}
            return yaml.dump(resource_config, default_flow_style=False, sort_keys=False).strip()
        else:
            # Resource uses default configuration - return empty config to indicate defaults
            return f"# {resource_name} uses default ACK configuration (no specific overrides needed)"


class ModelFileExtractor:
    """Extracts comprehensive resource definitions from AWS SDK Go V2 model files."""
    
    def __init__(self, aws_sdk_path: str):
        self.aws_sdk_path = Path(aws_sdk_path)
        self.models_path = self.aws_sdk_path / "codegen" / "sdk-codegen" / "aws-models"
        self._model_cache = {}  # Cache loaded models
    
    def get_model_file_path(self, service: str, gen_config: Optional[Dict[str, Any]] = None) -> Optional[Path]:
        """Get the path to the model file for a given service."""
        # Check for override first
        if service in MODEL_FILE_OVERRIDES:
            filename = MODEL_FILE_OVERRIDES[service]
            model_file = self.models_path / filename
            if model_file.exists():
                return model_file
        
        # Try common patterns
        filename = f"{service}.json"
        model_file = self.models_path / filename
        if model_file.exists():
            return model_file
        
        # Try with versioned patterns for services that might have dates
        for file in self.models_path.glob(f"{service}*.json"):
            return file
        
        # If we have generator config, try using sdk_names information
        if gen_config:
            sdk_names = gen_config.get('sdk_names', {})
            if 'model_name' in sdk_names:
                model_name = sdk_names['model_name']
                logger.debug(f"Trying model_name from generator.yaml: {model_name}")
                
                # Try exact model name
                model_file = self.models_path / f"{model_name}.json"
                if model_file.exists():
                    logger.info(f"Found model file using generator.yaml model_name: {model_file}")
                    return model_file
                
                # Try with versioned patterns
                for file in self.models_path.glob(f"{model_name}*.json"):
                    logger.info(f"Found versioned model file using generator.yaml model_name: {file}")
                    return file
            
            if 'package_name' in sdk_names:
                package_name = sdk_names['package_name']
                logger.debug(f"Trying package_name from generator.yaml: {package_name}")
                
                # Try exact package name
                model_file = self.models_path / f"{package_name}.json"
                if model_file.exists():
                    logger.info(f"Found model file using generator.yaml package_name: {model_file}")
                    return model_file
                
                # Try with versioned patterns
                for file in self.models_path.glob(f"{package_name}*.json"):
                    logger.info(f"Found versioned model file using generator.yaml package_name: {file}")
                    return file
        
        logger.warning(f"Model file not found for service: {service}")
        return None
    
    def load_service_model(self, service: str, gen_config: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Load the JSON model file for a service (with caching)."""
        if service in self._model_cache:
            return self._model_cache[service]
            
        model_file = self.get_model_file_path(service, gen_config)
        if not model_file:
            return None
            
        try:
            with open(model_file, 'r') as f:
                model_data = json.load(f)
                self._model_cache[service] = model_data
                return model_data
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load model file for {service}: {e}")
            return None
    
    def _extract_shape_info(self, shape_name: str, shape_def: Dict[str, Any], all_shapes: Dict[str, Any]) -> ShapeInfo:
        """Extract detailed information about a shape."""
        shape_info = ShapeInfo(
            name=shape_name,
            type=shape_def.get("type", "others"),
            documentation=shape_def.get("documentation", ""),
            required=shape_def.get("required", []),
            sensitive=shape_def.get("sensitive", False),
            deprecated=shape_def.get("deprecated", False)
        )
        
        # Handle different shape types with comprehensive extraction
        if shape_info.type == "structure":
            members = shape_def.get("members", {})
            for member_name, member_def in members.items():
                member_info = {
                    "type": "others",
                    "documentation": member_def.get("documentation", ""),
                    "location": member_def.get("location", {}),
                    "locationName": member_def.get("locationName", ""),
                    "target": member_def.get("target", ""),
                    "deprecated": member_def.get("deprecated", False),
                    "sensitive": member_def.get("sensitive", False),
                    "streaming": member_def.get("streaming", False),
                    "xmlAttribute": member_def.get("xmlAttribute", False),
                    "xmlNamespace": member_def.get("xmlNamespace", {}),
                    "queryName": member_def.get("queryName", ""),
                    "hostLabel": member_def.get("hostLabel", False),
                    "jsonvalue": member_def.get("jsonvalue", False),
                    "timestampFormat": member_def.get("timestampFormat", ""),
                    "idempotencyToken": member_def.get("idempotencyToken", False)
                }
                
                # Resolve target type if available
                if member_def.get("target") and member_def["target"] in all_shapes:
                    target_shape = all_shapes[member_def["target"]]
                    member_info["type"] = target_shape.get("type", "others")
                    member_info["target_documentation"] = target_shape.get("documentation", "")
                    if target_shape.get("type") == "string" and "enum" in target_shape:
                        member_info["enum"] = target_shape["enum"]
                    if "min" in target_shape:
                        member_info["min"] = target_shape["min"]
                    if "max" in target_shape:
                        member_info["max"] = target_shape["max"]
                    if "pattern" in target_shape:
                        member_info["pattern"] = target_shape["pattern"]
                
                shape_info.members[member_name] = member_info
                
        elif shape_info.type == "string":
            if "enum" in shape_def:
                shape_info.enum_values = shape_def["enum"]
            # Add additional string constraints
            if "min" in shape_def:
                shape_info.members["min_length"] = shape_def["min"]
            if "max" in shape_def:
                shape_info.members["max_length"] = shape_def["max"]
            if "pattern" in shape_def:
                shape_info.members["pattern"] = shape_def["pattern"]
                
        elif shape_info.type == "list":
            if "member" in shape_def:
                shape_info.members["list_member"] = {
                    "target": shape_def["member"].get("target", ""),
                    "documentation": shape_def["member"].get("documentation", ""),
                    "locationName": shape_def["member"].get("locationName", "")
                }
            if "min" in shape_def:
                shape_info.members["min_items"] = shape_def["min"]
            if "max" in shape_def:
                shape_info.members["max_items"] = shape_def["max"]
                
        elif shape_info.type == "map":
            if "key" in shape_def:
                shape_info.members["map_key"] = {
                    "target": shape_def["key"].get("target", ""),
                    "documentation": shape_def["key"].get("documentation", ""),
                    "locationName": shape_def["key"].get("locationName", "")
                }
            if "value" in shape_def:
                shape_info.members["map_value"] = {
                    "target": shape_def["value"].get("target", ""),
                    "documentation": shape_def["value"].get("documentation", ""),
                    "locationName": shape_def["value"].get("locationName", "")
                }
                
        elif shape_info.type in ["integer", "long", "float", "double"]:
            if "min" in shape_def:
                shape_info.members["min_value"] = shape_def["min"]
            if "max" in shape_def:
                shape_info.members["max_value"] = shape_def["max"]
        
        return shape_info
    
    def _extract_operation_info(self, op_name: str, op_def: Dict[str, Any], all_shapes: Dict[str, Any]) -> OperationInfo:
        """Extract detailed information about an operation."""
        # Determine operation type from name
        operation_type = "others"
        if op_name.startswith("Create"):
            operation_type = "Create"
        elif op_name.startswith("Delete"):
            operation_type = "Delete"
        elif op_name.startswith("Update") or op_name.startswith("Modify") or op_name.startswith("Put"):
            operation_type = "Update"
        elif op_name.startswith("Describe") or op_name.startswith("Get"):
            operation_type = "Read"
        elif op_name.startswith("List"):
            operation_type = "List"
        
        op_info = OperationInfo(
            name=op_name,
            operation_type=operation_type,
            documentation=op_def.get("documentation", ""),
            deprecated=op_def.get("deprecated", False),
            idempotent=op_def.get("idempotentOperations", False)
        )
        
        # Extract comprehensive input shape information
        if "input" in op_def and "target" in op_def["input"]:
            input_shape_name = op_def["input"]["target"]
            op_info.input_shape_name = input_shape_name
            
            if input_shape_name in all_shapes:
                input_shape = all_shapes[input_shape_name]
                if input_shape.get("type") == "structure":
                    members = input_shape.get("members", {})
                    for member_name, member_def in members.items():
                        op_info.input_fields[member_name] = {
                            "documentation": member_def.get("documentation", ""),
                            "target": member_def.get("target", ""),
                            "location": member_def.get("location", {}),
                            "locationName": member_def.get("locationName", ""),
                            "required": member_name in input_shape.get("required", []),
                            "deprecated": member_def.get("deprecated", False),
                            "sensitive": member_def.get("sensitive", False),
                            "streaming": member_def.get("streaming", False),
                            "xmlAttribute": member_def.get("xmlAttribute", False),
                            "xmlNamespace": member_def.get("xmlNamespace", {}),
                            "queryName": member_def.get("queryName", ""),
                            "hostLabel": member_def.get("hostLabel", False),
                            "jsonvalue": member_def.get("jsonvalue", False),
                            "timestampFormat": member_def.get("timestampFormat", ""),
                            "idempotencyToken": member_def.get("idempotencyToken", False)
                        }
                        
                        # Add target shape information if available
                        if member_def.get("target") and member_def["target"] in all_shapes:
                            target_shape = all_shapes[member_def["target"]]
                            op_info.input_fields[member_name]["target_type"] = target_shape.get("type", "others")
                            op_info.input_fields[member_name]["target_documentation"] = target_shape.get("documentation", "")
        
        # Extract comprehensive output shape information  
        if "output" in op_def and "target" in op_def["output"]:
            output_shape_name = op_def["output"]["target"]
            op_info.output_shape_name = output_shape_name
            
            if output_shape_name in all_shapes:
                output_shape = all_shapes[output_shape_name]
                if output_shape.get("type") == "structure":
                    members = output_shape.get("members", {})
                    for member_name, member_def in members.items():
                        op_info.output_fields[member_name] = {
                            "documentation": member_def.get("documentation", ""),
                            "target": member_def.get("target", ""),
                            "location": member_def.get("location", {}),
                            "locationName": member_def.get("locationName", ""),
                            "deprecated": member_def.get("deprecated", False),
                            "sensitive": member_def.get("sensitive", False),
                            "streaming": member_def.get("streaming", False),
                            "xmlAttribute": member_def.get("xmlAttribute", False),
                            "xmlNamespace": member_def.get("xmlNamespace", {}),
                            "resultWrapper": member_def.get("resultWrapper", ""),
                            "timestampFormat": member_def.get("timestampFormat", "")
                        }
                        
                        # Add target shape information if available
                        if member_def.get("target") and member_def["target"] in all_shapes:
                            target_shape = all_shapes[member_def["target"]]
                            op_info.output_fields[member_name]["target_type"] = target_shape.get("type", "others")
                            op_info.output_fields[member_name]["target_documentation"] = target_shape.get("documentation", "")
        
        # Extract comprehensive error information
        if "errors" in op_def:
            for error in op_def["errors"]:
                if "target" in error:
                    op_info.errors.append(error["target"])
        
        return op_info
    
    def _find_resource_operations(self, resource_name: str, all_shapes: Dict[str, Any]) -> List[str]:
        """Find all operations related to a specific resource."""
        operations = []
        
        # Common operation patterns
        patterns = [
            f"Create{resource_name}",
            f"Delete{resource_name}",
            f"Update{resource_name}",
            f"Modify{resource_name}",
            f"Put{resource_name}",
            f"Describe{resource_name}",
            f"Get{resource_name}",
            f"List{resource_name}s",
            f"List{resource_name}",
            # Plural variations
            f"Describe{resource_name}s",
            f"Get{resource_name}s",
            # Action variations
            f"Start{resource_name}",
            f"Stop{resource_name}",
            f"Resume{resource_name}",
            f"Pause{resource_name}",
            f"Enable{resource_name}",
            f"Disable{resource_name}",
            f"Reset{resource_name}",
            f"Restart{resource_name}",
            f"Reboot{resource_name}",
            f"Tag{resource_name}",
            f"Untag{resource_name}",
        ]
        
        # Find operations that match patterns
        for shape_name, shape_def in all_shapes.items():
            if shape_def.get("type") == "operation":
                op_name = shape_name.split("#")[-1]  # Remove namespace
                
                # Check if this operation relates to our resource
                if any(pattern == op_name for pattern in patterns):
                    operations.append(op_name)
                elif resource_name.lower() in op_name.lower():
                    # Catch additional operations that contain the resource name
                    operations.append(op_name)
        
        return operations
    
    def find_comprehensive_resource_info(self, model_data: Dict[str, Any], resource_name: str) -> Optional[ResourceDefinition]:
        """Find comprehensive information about a specific resource in the model."""
        shapes = model_data.get("shapes", {})
        
        # Find all operations related to this resource
        related_operations = self._find_resource_operations(resource_name, shapes)
        
        if not related_operations:
            logger.debug(f"No operations found for resource: {resource_name}")
            return None
        
        resource_def = ResourceDefinition(name=resource_name)
        
        # Extract comprehensive service metadata
        metadata = model_data.get("metadata", {})
        resource_def.service_metadata = {
            "protocol": metadata.get("protocol", ""),
            "serviceAbbreviation": metadata.get("serviceAbbreviation", ""),
            "serviceFullName": metadata.get("serviceFullName", ""),
            "serviceId": metadata.get("serviceId", ""),
            "signatureVersion": metadata.get("signatureVersion", ""),
            "uid": metadata.get("uid", ""),
            "apiVersion": metadata.get("apiVersion", ""),
            "endpointPrefix": metadata.get("endpointPrefix", ""),
            "globalEndpoint": metadata.get("globalEndpoint", ""),
            "timestampFormat": metadata.get("timestampFormat", ""),
            "checksumFormat": metadata.get("checksumFormat", ""),
            "jsonVersion": metadata.get("jsonVersion", ""),
            "targetPrefix": metadata.get("targetPrefix", ""),
            "xmlNamespace": metadata.get("xmlNamespace", "")
        }
        
        # Track all referenced shapes to collect comprehensive information
        referenced_shapes = set()
        
        # Extract detailed information for each operation
        for op_name in related_operations:
            # Find the operation shape
            for shape_name, shape_def in shapes.items():
                if shape_def.get("type") == "operation" and shape_name.endswith(f"#{op_name}"):
                    op_info = self._extract_operation_info(op_name, shape_def, shapes)
                    resource_def.operations[op_name] = op_info
                    
                    # Track shapes for comprehensive extraction
                    if op_info.input_shape_name:
                        referenced_shapes.add(op_info.input_shape_name)
                    if op_info.output_shape_name:
                        referenced_shapes.add(op_info.output_shape_name)
                    referenced_shapes.update(op_info.errors)
                    break
        
        # Extract all referenced shapes and their dependencies recursively
        processed_shapes = set()
        shapes_to_process = list(referenced_shapes)
        
        while shapes_to_process:
            shape_name = shapes_to_process.pop(0)
            if shape_name in processed_shapes or shape_name not in shapes:
                continue
                
            processed_shapes.add(shape_name)
            shape_info = self._extract_shape_info(shape_name, shapes[shape_name], shapes)
            resource_def.shapes[shape_name] = shape_info
            
            # Add referenced shapes for recursive processing
            if shape_info.type == "structure":
                for member_info in shape_info.members.values():
                    if member_info.get("target") and member_info["target"] not in processed_shapes:
                        shapes_to_process.append(member_info["target"])
            elif shape_info.type == "list":
                list_member = shape_info.members.get("list_member", {})
                if list_member.get("target") and list_member["target"] not in processed_shapes:
                    shapes_to_process.append(list_member["target"])
            elif shape_info.type == "map":
                map_key = shape_info.members.get("map_key", {})
                map_value = shape_info.members.get("map_value", {})
                if map_key.get("target") and map_key["target"] not in processed_shapes:
                    shapes_to_process.append(map_key["target"])
                if map_value.get("target") and map_value["target"] not in processed_shapes:
                    shapes_to_process.append(map_value["target"])
        
        # Collect all unique errors
        all_errors = set()
        for op_info in resource_def.operations.values():
            all_errors.update(op_info.errors)
        resource_def.errors = list(all_errors)
        
        logger.debug(f"Found {len(resource_def.operations)} operations, {len(resource_def.shapes)} shapes, and {len(resource_def.errors)} errors for {resource_name}")
        return resource_def


class FinetuningDataGenerator:
    """Generates JSONL fine-tuning data by working backwards from ACK generator configs.
    
    Supports both Bedrock conversation format (recommended) and legacy prompt/completion format.
    """
    
    def __init__(self, output_file: str = "model_to_generator_mapping.jsonl", use_conversation_format: bool = True):
        self.output_file = output_file
        self.use_conversation_format = use_conversation_format
        self.model_extractor = None
        self.config_extractor = GeneratorConfigExtractor()
    
    def initialize_aws_sdk(self) -> bool:
        """Initialize AWS SDK repository and model extractor."""
        try:
            aws_sdk_path = ensure_aws_sdk_go_v2_cloned()
            self.model_extractor = ModelFileExtractor(aws_sdk_path)
            return True
        except Exception as e:
            logger.error(f"Failed to initialize AWS SDK repository: {e}")
            return False
    
    def create_bedrock_conversation_entry(self, model_data: Dict[str, Any], resource_name: str, service: str, resource_config: str) -> Dict[str, Any]:
        """Create a Bedrock fine-tuning entry using the conversation format."""
        
        # Create comprehensive system message
        system_message = (
            "You are an AWS ACK (AWS Controllers for Kubernetes) configuration generator expert. "
            f"You specialize in analyzing AWS SDK Go V2 model definitions for the {service} service "
            "and generating accurate generator.yaml configurations for ACK controllers. "
            "You understand AWS API models, resource definitions, field mappings, and ACK configuration patterns."
        )
        
        # Create user message with the model data and task
        user_message = (
            f"Given the following AWS SDK Go V2 model definition for the {service} service, "
            f"generate the ACK generator.yaml configuration for the {resource_name} resource.\n\n"
            f"AWS SDK Model:\n{json.dumps(model_data, indent=2)}\n\n"
            f"Generate the ACK generator.yaml configuration for the {resource_name} resource:"
        )
        
        # Assistant response is the actual configuration
        assistant_message = resource_config
        
        # Create the Bedrock conversation format
        entry = {
            "schemaVersion": "bedrock-conversation-2024",
            "system": [
                {
                    "text": system_message
                }
            ],
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "text": user_message
                        }
                    ]
                },
                {
                    "role": "assistant", 
                    "content": [
                        {
                            "text": assistant_message
                        }
                    ]
                }
            ]
        }
        
        return entry

    def create_bedrock_prompt(self, model_data: Dict[str, Any], resource_name: str, service: str) -> str:
        """Create a Bedrock fine-tuning prompt with full model.json content and resource name."""
        prompt_parts = [
            f"Given the following AWS SDK Go V2 model definition for the {service} service, generate the ACK generator.yaml configuration for the {resource_name} resource.",
            "",
            "AWS SDK Model:",
            json.dumps(model_data, indent=2),
            "",
            f"Generate the ACK generator.yaml configuration for the {resource_name} resource:"
        ]
        
        return "\n".join(prompt_parts)
    
    def process_service(self, service: str) -> List[Dict[str, Any]]:
        """Process a single service by starting with generator.yaml and finding corresponding models."""
        entries = []
        
        try:
            # Clone/update service repository
            repo_path = ensure_service_repo_cloned(service)
            logger.info(f"Processing service: {service}")
            
            # Load generator config (our authoritative source)
            gen_config = self.config_extractor.load_generator_config(repo_path)
            if not gen_config:
                logger.warning(f"Skipping {service} - no generator config")
                return entries
            
            # Extract all resources ACK knows about from generator.yaml
            service_resources = self.config_extractor.extract_all_resources(gen_config)
            service_resources.service_name = service
            
            # Filter out ignored resources for JSONL generation
            # Only include configured resources and those that would use default configuration
            jsonl_resources = service_resources.configured_resources
            # Note: We're excluding ignored resources from JSONL as requested
            
            logger.info(f"Found {len(service_resources.all_resources)} ACK-managed resources in {service}: "
                       f"{len(service_resources.configured_resources)} configured, "
                       f"{len(service_resources.ignored_resources)} ignored")
            logger.info(f"Generating JSONL for {len(jsonl_resources)} resources (excluding {len(service_resources.ignored_resources)} ignored resources)")
            
            if not jsonl_resources:
                logger.info(f"No configured resources found in {service} generator.yaml for JSONL generation")
                return entries
            
            # Load service model
            model_data = self.model_extractor.load_service_model(service, gen_config)
            if not model_data:
                logger.warning(f"Skipping {service} - no model data")
                return entries
            
            # For each non-ignored ACK resource, create conversation entry
            for resource_name in jsonl_resources:
                # Get the ACK configuration for this resource as completion
                completion = self.config_extractor.get_resource_config_yaml(gen_config, resource_name)
                
                # Create entry in the appropriate format
                if self.use_conversation_format:
                    # Create Bedrock conversation entry (recommended)
                    entry = self.create_bedrock_conversation_entry(model_data, resource_name, service, completion)
                    logger.debug(f"Created Bedrock conversation entry for {service}::{resource_name}")
                else:
                    # Create legacy prompt/completion entry (for compatibility)
                    prompt = self.create_bedrock_prompt(model_data, resource_name, service)
                    entry = {
                        "prompt": prompt,
                        "completion": completion
                    }
                    logger.debug(f"Created legacy prompt/completion entry for {service}::{resource_name}")
                
                entries.append(entry)
            
        except Exception as e:
            logger.error(f"Error processing service {service}: {e}")
        
        return entries
    
    def generate_training_data(self, services: Optional[List[str]] = None) -> bool:
        """Generate training data for specified services or all known services using the chosen format."""
        if not self.initialize_aws_sdk():
            return False
        
        if services is None:
            services = SERVICE_CONTROLLERS
        
        format_name = "Bedrock conversation format" if self.use_conversation_format else "legacy prompt/completion format"
        logger.info(f"Generating training data using {format_name}")
        
        all_entries = []
        
        with open(self.output_file, 'w') as output_file:
            for service in services:
                # Check if service controller exists
                if not check_service_controller_exists(service):
                    logger.warning(f"Service controller for {service} does not exist, skipping")
                    continue
                
                entries = self.process_service(service)
                
                # Write entries to file immediately
                for entry in entries:
                    output_file.write(json.dumps(entry) + "\n")
                    all_entries.append(entry)
                
                entry_type = "conversation entries" if self.use_conversation_format else "prompt/completion entries"
                logger.info(f"Added {len(entries)} {entry_type} for {service}")
        
        entry_type = "conversation training entries" if self.use_conversation_format else "prompt/completion training entries"
        logger.info(f"Generated {len(all_entries)} {entry_type} in {self.output_file}")
        return True


def main():
    """Main function to generate fine-tuning data."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate comprehensive fine-tuning data from ACK generator configs and AWS models")
    parser.add_argument("--output", "-o", default="model_to_generator_mapping.jsonl",
                        help="Output JSONL file path")
    parser.add_argument("--services", "-s", nargs="*", 
                        help="List of services to process (default: all known services)")
    parser.add_argument("--format", "-f", choices=["conversation", "legacy"], default="conversation",
                        help="Output format: 'conversation' for Bedrock conversation format (recommended), 'legacy' for prompt/completion format")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    use_conversation_format = args.format == "conversation"
    generator = FinetuningDataGenerator(output_file=args.output, use_conversation_format=use_conversation_format)
    success = generator.generate_training_data(services=args.services)
    
    format_name = "Bedrock conversation format" if use_conversation_format else "legacy prompt/completion format"
    
    if success:
        logger.info(f"Fine-tuning data generation completed successfully using {format_name}")
    else:
        logger.error("Fine-tuning data generation failed")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main()) 