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
"""ACK Generator tools for Strands agents."""

import os
from strands import tool, Agent

import json
from rich.console import Console
from ack_builder_agent.tools import build_controller, read_build_log, sleep, verify_build_completion
from config.prompts import ACK_BUILDER_SYSTEM_PROMPT
from utils.settings import settings
from utils.repo import (
    ensure_ack_directories,
    ensure_service_repo_cloned,
    ensure_aws_sdk_go_v2_cloned,
)

from utils.memory_agent import MemoryAgent
from utils.knowledge_base import retrieve_from_knowledge_base
from utils.docs_agent import DocsAgent

console = Console()
memory_agent = MemoryAgent()
docs_agent = DocsAgent()

@tool
def read_service_generator_config(service: str) -> str:
    """Reads the generator.yaml file from a service controller directory.

    Args:
        service: Name of the AWS service (e.g., 's3', 'dynamodb')

    Returns:
        str: Content of the generator.yaml file or an error message.
    """
    try:
        ensure_ack_directories()
        service_path = ensure_service_repo_cloned(service)

        generator_config_path = os.path.join(service_path, "generator.yaml")

        if not os.path.exists(generator_config_path):
            return f"Error: generator.yaml not found in {service_path}"

        with open(generator_config_path, 'r') as f:
            content = f.read()
        return content
    except Exception as e:
        return f"Error reading generator.yaml for {service}: {str(e)}"

@tool
def read_service_model(service: str, resource: str) -> str:
    """Reads comprehensive resource-specific information from the AWS service model JSON file.

    Args:
        service: Name of the AWS service (e.g., 's3', 'dynamodb')
        resource: Name of the specific resource (e.g., 'Bucket', 'Table', 'Cluster')

    Returns:
        str: Comprehensive resource-specific content from the service model or an error message.
    """
    try:
        # Make sure AWS SDK is cloned
        ensure_ack_directories()
        ensure_aws_sdk_go_v2_cloned()
        
        # Get the model file path from settings
        model_path = settings.get_aws_service_model_path(service)
        
        console.log(f"Looking for model at: {model_path}")
        
        if not os.path.exists(model_path):
            return f"Error: Model file not found for service '{service}' at {model_path}"
            
        with open(model_path, 'r') as f:
            content = f.read()
            
        # Parse the model JSON
        try:
            data = json.loads(content)
        except Exception as e:
            console.log(f"Error parsing model JSON: {str(e)}")
            return f"Error parsing model JSON for {service}: {str(e)}"
        
        # Extract comprehensive resource information
        resource_info = {}
        
        # Find the resource in shapes (handle Smithy format)
        shapes = data.get('shapes', {})
        if not shapes:
            return f"Error: No shapes found in service model for {service}"
        
        resource_shape = None
        resource_candidates = []
        
        # Build namespace prefix for this service
        service_namespace = f"com.amazonaws.{service}#"
        
        # Look for resource shapes with various strategies
        for shape_name, shape_data in shapes.items():
            shape_type = shape_data.get('type', '')
            
            # Strategy 1: Exact match with namespace
            full_resource_name = f"{service_namespace}{resource}"
            if shape_name == full_resource_name:
                resource_shape = shape_name
                break
                
            # Strategy 2: Case-insensitive match with namespace
            if shape_name.lower() == full_resource_name.lower():
                resource_shape = shape_name
                break
                
            # Strategy 3: Contains resource name (for structures/operations)
            if (resource.lower() in shape_name.lower() and 
                shape_type in ['structure', 'operation'] and
                service_namespace in shape_name):
                resource_candidates.append((shape_name, shape_data, shape_type))
        
        # If no exact match, find the best candidate
        if not resource_shape and resource_candidates:
            # Prefer structure types over operations for main resources
            structure_candidates = [c for c in resource_candidates if c[2] == 'structure']
            if structure_candidates:
                # Look for the most likely main resource (shortest name, no prefixes like Create/Delete)
                best_candidate = min(structure_candidates, 
                                   key=lambda x: (len(x[0]), 
                                                'Create' in x[0] or 'Delete' in x[0] or 'List' in x[0]))
                resource_shape = best_candidate[0]
            else:
                resource_shape = resource_candidates[0][0]
        
        if not resource_shape:
            available_shapes = [name for name in shapes.keys() 
                             if service_namespace in name and 
                             shapes[name].get('type') in ['structure', 'operation']][:20]
            return f"Error: Resource '{resource}' not found in service model for {service}. Available resource shapes include: {available_shapes}..."
        
        # Collect all resource-related information
        resource_info['resource_name'] = resource_shape
        resource_info['shape_definition'] = shapes[resource_shape]
        
        # Find operations related to this resource
        operations = {}
        related_operations = {}
        
        # Collect all operations first
        for shape_name, shape_data in shapes.items():
            if shape_data.get('type') == 'operation':
                operations[shape_name] = shape_data
        
        # Find operations related to this resource
        resource_base_name = resource_shape.split('#')[-1] if '#' in resource_shape else resource_shape
        
        for op_name, op_data in operations.items():
            op_base_name = op_name.split('#')[-1] if '#' in op_name else op_name
            
            # Check if operation is related to this resource
            is_related = False
            
            # Strategy 1: Operation name contains resource name
            if resource_base_name.lower() in op_base_name.lower():
                is_related = True
            
            # Strategy 2: Check input/output shapes
            input_shape = op_data.get('input', {}).get('target', '')
            output_shape = op_data.get('output', {}).get('target', '')
            
            if input_shape:
                input_base = input_shape.split('#')[-1] if '#' in input_shape else input_shape
                if resource_base_name.lower() in input_base.lower():
                    is_related = True
                    
            if output_shape:
                output_base = output_shape.split('#')[-1] if '#' in output_shape else output_shape
                if resource_base_name.lower() in output_base.lower():
                    is_related = True
            
            # Strategy 3: Common CRUD patterns
            crud_patterns = ['Create', 'Delete', 'Update', 'Get', 'List', 'Describe', 'Put']
            for pattern in crud_patterns:
                if (f"{pattern}{resource_base_name}" in op_base_name or 
                    f"{pattern}{resource}" in op_base_name):
                    is_related = True
                    break
            
            if is_related:
                related_operations[op_name] = op_data
        
        resource_info['related_operations'] = related_operations
        
        # Find related shapes (referenced by the main resource and operations)
        related_shapes = {}
        
        def collect_referenced_shapes(shape_data, collected, visited=None):
            if visited is None:
                visited = set()
                
            if isinstance(shape_data, dict):
                if 'target' in shape_data:
                    shape_ref = shape_data['target']
                    if shape_ref in shapes and shape_ref not in collected and shape_ref not in visited:
                        visited.add(shape_ref)
                        collected[shape_ref] = shapes[shape_ref]
                        collect_referenced_shapes(shapes[shape_ref], collected, visited)
                elif 'member' in shape_data:
                    collect_referenced_shapes(shape_data['member'], collected, visited)
                elif 'key' in shape_data:
                    collect_referenced_shapes(shape_data['key'], collected, visited)
                elif 'value' in shape_data:
                    collect_referenced_shapes(shape_data['value'], collected, visited)
                else:
                    for value in shape_data.values():
                        if isinstance(value, (dict, list)):
                            collect_referenced_shapes(value, collected, visited)
            elif isinstance(shape_data, list):
                for item in shape_data:
                    collect_referenced_shapes(item, collected, visited)
        
        # Collect shapes from main resource
        collect_referenced_shapes(shapes[resource_shape], related_shapes)
        
        # Collect shapes from related operations
        for op_data in related_operations.values():
            collect_referenced_shapes(op_data, related_shapes)
        
        resource_info['related_shapes'] = related_shapes
        
        # Find error shapes for related operations
        error_shapes = {}
        for op_name, op_data in related_operations.items():
            errors = op_data.get('errors', [])
            for error in errors:
                error_target = error.get('target', '') if isinstance(error, dict) else error
                if error_target and error_target in shapes:
                    error_shapes[error_target] = shapes[error_target]
        
        resource_info['error_shapes'] = error_shapes
        
        # Extract traits and documentation for all shapes
        def extract_traits_and_docs(shape_data):
            """Extract traits and documentation from a shape."""
            traits = {}
            documentation = None
            
            if isinstance(shape_data, dict):
                # First, check for a 'traits' dictionary (Smithy format)
                if 'traits' in shape_data:
                    traits_dict = shape_data['traits']
                    if isinstance(traits_dict, dict):
                        # Extract all traits from the traits dictionary
                        for trait_key, trait_value in traits_dict.items():
                            traits[trait_key] = trait_value
                            
                            # Check for documentation specifically
                            if trait_key == 'smithy.api#documentation':
                                documentation = trait_value
                
                # Also check for direct trait-like keys at the top level
                for key, value in shape_data.items():
                    # Look for actual trait patterns
                    if (key.startswith('smithy.api#') or 
                        key.startswith('aws.api#') or
                        key.startswith('aws.protocols#') or
                        key.startswith('aws.auth#') or
                        key.startswith('com.amazonaws') and '#' in key):
                        traits[key] = value
                    elif key == 'documentation':
                        documentation = value
                    # Also check for trait-like patterns
                    elif key in ['deprecated', 'sensitive', 'required', 'idempotent', 'readonly']:
                        traits[key] = value
                        
            return traits, documentation
        
        # Add comprehensive metadata for all shapes
        enhanced_shapes = {}
        all_shapes_to_process = {
            **{resource_shape: shapes[resource_shape]},
            **related_operations,
            **error_shapes,
            **related_shapes
        }
        
        for shape_name, shape_data in all_shapes_to_process.items():
            traits, docs = extract_traits_and_docs(shape_data)
            enhanced_shapes[shape_name] = {
                'shape_data': shape_data,
                'traits': traits,
                'documentation': docs,
                'type': shape_data.get('type', 'unknown')
            }
        
        resource_info['enhanced_shapes'] = enhanced_shapes
        
        # Extract HTTP bindings and constraints for operations
        operation_details = {}
        for op_name, op_data in related_operations.items():
            op_details = {
                'operation_data': op_data,
                'http_bindings': {},
                'authentication': {},
                'pagination': {},
                'constraints': {}
            }
            
            # Extract traits from the operation
            op_traits, _ = extract_traits_and_docs(op_data)
            
            # Categorize traits by type
            for trait_key, trait_value in op_traits.items():
                if ('http' in trait_key.lower() or 
                    trait_key.startswith('smithy.api#http') or
                    trait_key.startswith('aws.protocols')):
                    op_details['http_bindings'][trait_key] = trait_value
                elif ('auth' in trait_key.lower() or
                      trait_key.startswith('aws.auth') or
                      trait_key.startswith('smithy.api#auth')):
                    op_details['authentication'][trait_key] = trait_value
                elif ('paginated' in trait_key.lower() or 
                      'pagination' in trait_key.lower() or
                      trait_key.startswith('aws.api#paginated')):
                    op_details['pagination'][trait_key] = trait_value
                elif ('constraint' in trait_key.lower() or 
                      'validation' in trait_key.lower() or
                      'required' in trait_key.lower()):
                    op_details['constraints'][trait_key] = trait_value
                    
            operation_details[op_name] = op_details
        
        resource_info['operation_details'] = operation_details
        
        # Extract enum values and union variants
        enums_and_unions = {}
        for shape_name, shape_data in all_shapes_to_process.items():
            if shape_data.get('type') == 'enum':
                enums_and_unions[shape_name] = {
                    'type': 'enum',
                    'members': shape_data.get('members', [])
                }
            elif shape_data.get('type') == 'union':
                enums_and_unions[shape_name] = {
                    'type': 'union',
                    'members': shape_data.get('members', {})
                }
        
        resource_info['enums_and_unions'] = enums_and_unions
        
        # Extract service metadata (handle Smithy format)
        service_shape_name = f"com.amazonaws.{service}#{service.upper()}"
        service_shape = shapes.get(service_shape_name, {})
        
        # Try alternative service shape names
        if not service_shape:
            for shape_name, shape_data in shapes.items():
                if shape_data.get('type') == 'service' and service in shape_name.lower():
                    service_shape = shape_data
                    service_shape_name = shape_name
                    break
        
        # Extract service-level traits
        service_traits = {}
        if service_shape:
            service_traits, _ = extract_traits_and_docs(service_shape)
        
        resource_info['service_metadata'] = {
            'service_name': service,
            'smithy_version': data.get('smithy', ''),
            'service_shape': service_shape_name if service_shape else None,
            'service_traits': service_traits,
            'total_shapes': len(shapes),
            'total_operations': len(operations),
            'total_errors': len(error_shapes),
            'namespace': service_namespace.rstrip('#'),
            'metadata': data.get('metadata', {}),
            'note': 'HTTP bindings, authentication middleware, and pagination are implemented in the generated Go SDK code, not in the Smithy model file. Use read_resource_api() to see the actual implementation details.'
        }
        
        # Add summary statistics
        resource_info['summary'] = {
            'resource_shape': resource_shape,
            'related_operations_count': len(related_operations),
            'error_shapes_count': len(error_shapes),
            'related_shapes_count': len(related_shapes),
            'total_enhanced_shapes': len(enhanced_shapes),
            'enums_count': len([s for s in enums_and_unions.values() if s['type'] == 'enum']),
            'unions_count': len([s for s in enums_and_unions.values() if s['type'] == 'union']),
            'has_documentation': len([s for s in enhanced_shapes.values() if s['documentation']]),
            'shapes_with_traits': len([s for s in enhanced_shapes.values() if s['traits']]),
            'operations_with_http_bindings': len([op for op in operation_details.values() if op['http_bindings']]),
            'operations_with_auth': len([op for op in operation_details.values() if op['authentication']]),
            'paginated_operations': len([op for op in operation_details.values() if op['pagination']])
        }
        
        return json.dumps(resource_info, indent=2)
            
    except Exception as e:
        return f"Error reading service model for {service}/{resource}: {str(e)}"

@tool
def build_controller_agent(service: str) -> str:
    """
    Delegate the controller build process to the specialized builder agent.

    Args:
        service: Name of the AWS service (e.g., 's3', 'dynamodb')

    Returns:
        str: The builder agent's response (build status, logs, etc.)
    """
    try:
        builder_agent = Agent(
            system_prompt=ACK_BUILDER_SYSTEM_PROMPT,
            tools=[build_controller, read_build_log, sleep, verify_build_completion]
        )
        response = builder_agent(service)
        return str(response)
    except Exception as e:
        return f"Error in build_controller_agent: {str(e)}"


# TODO(rushmash91): This is a temporary tool to update the generator.yaml file.
# this will need a lot of checks and possibly a generator.yaml validator tool too
@tool
def update_service_generator_config(service: str, new_generator_yaml: str) -> str:
    """
    Replace the generator.yaml file for a given service controller with new content.

    Args:
        service: Name of the AWS service (e.g., 's3', 'dynamodb')
        new_generator_yaml: The full new content for generator.yaml

    Returns:
        str: Success or error message
    """
    try:
        ensure_ack_directories()
        service_path = ensure_service_repo_cloned(service)
        generator_config_path = os.path.join(service_path, "generator.yaml")

        # Remove the old generator.yaml if it exists
        if os.path.exists(generator_config_path):
            os.remove(generator_config_path)

        # Write the new generator.yaml
        with open(generator_config_path, 'w') as f:
            f.write(new_generator_yaml)

        return f"Successfully updated generator.yaml for {service} at {generator_config_path}"
    except Exception as e:
        return f"Error updating generator.yaml for {service}: {str(e)}" 
    

# Use the dedicated memory agent for error/solution management
@tool
def error_lookup(error_message: str) -> str:
    """
    Look up the error message in the agent's memory and return the corresponding solution.
    
    Args:
        error_message: The error message to look up
        
    Returns:
        str: Previously known solution or None if not found
    """
    return memory_agent.lookup_error_solution(error_message)


@tool
def add_memory(content: str, metadata: dict = None) -> str:
    """
    Manually add a memory to the agent's memory store.
    
    Args:
        content: The content/information to store in memory
        metadata: Optional metadata dictionary to associate with the memory
        
    Returns:
        str: Success or error message
    """
    return memory_agent.add_knowledge(content, metadata)


@tool
def search_memories(query: str, limit: int = 5, min_score: float = 0.5) -> str:
    """
    Search through stored memories using a query.
    
    Args:
        query: The search query to find relevant memories
        limit: Maximum number of memories to return (default: 5)
        min_score: Minimum relevance score for results (default: 0.5)
        
    Returns:
        str: Found memories or message if none found
    """
    return memory_agent.search_memories(query, limit)


@tool
def list_all_memories() -> str:
    """
    List all stored memories in the agent's memory.
    
    Returns:
        str: All stored memories with metadata
    """
    return memory_agent.list_all_memories()


# TODO(rushmash91): This is lookup to look up code-generator configs/ if we have a validator might not be needed
@tool
def lookup_code_generator_config(service: str, resource: str) -> str:
    """
    Look up the code-generator config for a given service and resource.
    """
    return f""

@tool
def save_error_solution(error_message: str, solution: str) -> str:
    """
    Save an error message and its solution to the agent's memory.
    
    Args:
        error_message: The error message to save
        solution: The solution for this error
        
    Returns:
        str: Success or error message
    """
    return memory_agent.store_error_solution(error_message, solution)


@tool
def search_codegen_knowledge(query: str, numberOfResults: int = 5) -> str:
    """
    Search for code generation related information in the knowledge base.
    
    This is a specialized version of retrieve_from_knowledge_base that's optimized
    for searching code generation patterns, configurations, and best practices.
    
    Args:
        query: The search query focused on code generation topics
        numberOfResults: Maximum number of results to return (default: 5)
        
    Returns:
        str: Code generation related information or error message
    """
    
    return retrieve_from_knowledge_base(
        text=query,
        numberOfResults=numberOfResults,
        score=0.6,  # Higher threshold for more relevant results
        knowledgeBaseId=""
    )

@tool
def search_aws_documentation(query: str, max_results: int = 5) -> str:
    """
    Search AWS documentation using the AWS documentation MCP server.
    
    This tool provides access to comprehensive AWS service documentation,
    API references, user guides, and best practices.
    
    Args:
        query: Search query for AWS documentation (e.g., "S3 bucket configuration", "DynamoDB table creation")
        max_results: Maximum number of documentation results to return (default: 5)
        
    Returns:
        str: AWS documentation search results or error message
    """
    return docs_agent.search_documentation(query, max_results)


@tool
def read_aws_documentation(url: str, max_length: int = 5000, start_index: int = 0) -> str:
    """
    Read specific AWS documentation page content.
    
    Args:
        url: AWS documentation URL (must be from docs.aws.amazon.com)
        max_length: Maximum number of characters to return (default: 5000)
        start_index: Starting character index for partial reads (default: 0)
        
    Returns:
        str: AWS documentation page content in markdown format or error message
    """
    return docs_agent.read_documentation_page(url, max_length, start_index)


@tool
def get_aws_documentation_recommendations(url: str) -> str:
    """
    Get content recommendations for an AWS documentation page.
    
    This tool provides recommendations for related AWS documentation pages
    including highly rated, new, similar, and commonly viewed next pages.
    
    Args:
        url: AWS documentation URL to get recommendations for
        
    Returns:
        str: List of recommended documentation pages with URLs, titles, and context
    """
    return docs_agent.get_documentation_recommendations(url)


@tool
def find_service_documentation(service: str, resource: str = None) -> str:
    """
    Find AWS service documentation specifically for ACK controller generation.
    
    This tool searches for AWS service API documentation, user guides, and best practices
    that are relevant for generating Kubernetes controllers.
    
    Args:
        service: AWS service name (e.g., 's3', 'dynamodb', 'rds')
        resource: Optional specific resource name (e.g., 'bucket', 'table', 'cluster')
        
    Returns:
        str: Relevant AWS documentation for the service/resource or error message
    """
    return docs_agent.find_service_documentation(service, resource)
