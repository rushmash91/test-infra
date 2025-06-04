#!/usr/bin/env python3
"""
ACK Code Generation Errors and Solutions Database

This module provides a comprehensive collection of common errors encountered during 
ACK (AWS Controllers for Kubernetes) code generation and their corresponding solutions.
The errors and solutions are based on real patterns found in the ACK codebase,
including generator.yaml misconfigurations, build failures, and API model issues.

Author: Generated from ACK codebase analysis
Version: 1.0
"""

import json
import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
from enum import Enum


class ErrorCategory(Enum):
    """Categories of ACK code generation errors"""
    TAGGING = "tagging"
    PRIMARY_KEY = "primary_key"
    EXCEPTION_HANDLING = "exception_handling"
    FIELD_MAPPING = "field_mapping"
    NAMING_CONFLICT = "naming_conflict"
    BUILD_FAILURE = "build_failure"
    VALIDATION = "validation"
    API_MODEL = "api_model"


@dataclass
class ErrorSolution:
    """Represents an error and its solution"""
    error_signature: str
    error_description: str
    category: ErrorCategory
    solution_description: str
    generator_yaml_fix: Optional[str] = None
    code_example: Optional[str] = None
    prevention_tip: Optional[str] = None


class ACKErrorDatabase:
    """Database of ACK code generation errors and solutions"""
    
    def __init__(self):
        self.errors: List[ErrorSolution] = self._initialize_errors()
    
    def _initialize_errors(self) -> List[ErrorSolution]:
        """Initialize the database with known errors and solutions"""
        return [
            # TAGGING ERRORS
            ErrorSolution(
                error_signature="tag field path Tags does not exist inside [Resource] crd",
                error_description="The code-generator attempts to generate tag-handling code but cannot find a 'Tags' field in the resource CRD. This occurs when a resource that does not support tagging is not marked as such in generator.yaml.",
                category=ErrorCategory.TAGGING,
                solution_description="Mark the resource to ignore tags in generator.yaml",
                generator_yaml_fix="""resources:
  ResourceName:
    tags:
      ignore: true  # Skip tag processing for this resource""",
                prevention_tip="Always check AWS documentation to verify if a resource supports tagging before enabling tag generation."
            ),
            
            ErrorSolution(
                error_signature="error calling GetTagField: tag field path.*does not exist",
                error_description="Custom tag field path specified in generator.yaml does not exist in the resource structure",
                category=ErrorCategory.TAGGING,
                solution_description="Either correct the tag field path or use the default 'Tags' path",
                generator_yaml_fix="""resources:
  ResourceName:
    tags:
      path: Tagging.TagSet  # Correct path for S3-style tagging
      # OR remove custom path to use default 'Tags' field""",
                prevention_tip="Verify tag field paths against the AWS API model before specifying custom paths."
            ),

            # PRIMARY KEY ERRORS  
            ErrorSolution(
                error_signature="missing primary identifier|no Name or ID field|could not find field.*for primary key",
                error_description="The code-generator cannot infer a unique key for a resource that lacks a typical 'Name' or 'ID' field, or the specified primary key field doesn't exist",
                category=ErrorCategory.PRIMARY_KEY,
                solution_description="Explicitly configure the primary key in generator.yaml",
                generator_yaml_fix="""resources:
  ResourceName:
    fields:
      YourIdentifierField:
        is_primary_key: true
    # OR if the resource is identified only by ARN:
    # is_arn_primary_key: true""",
                prevention_tip="Always identify the unique identifier for each resource before starting code generation."
            ),

            ErrorSolution(
                error_signature="multiple fields are marked with is_primary_key",
                error_description="More than one field is marked as the primary key in generator.yaml configuration",
                category=ErrorCategory.PRIMARY_KEY,
                solution_description="Ensure only one field is marked as the primary key",
                generator_yaml_fix="""resources:
  ResourceName:
    fields:
      CorrectPrimaryKey:
        is_primary_key: true
      # Remove is_primary_key from other fields""",
                prevention_tip="Each resource should have exactly one primary identifier field."
            ),

            # EXCEPTION HANDLING ERRORS
            ErrorSolution(
                error_signature="ResourceNotFoundException returned as 400|exception.*400.*ResourceNotFoundException",
                error_description="Service returns HTTP 400 with ResourceNotFoundException instead of 404, misleading the generator's default logic",
                category=ErrorCategory.EXCEPTION_HANDLING,
                solution_description="Map the exception code to 404 in generator.yaml",
                generator_yaml_fix="""resources:
  ResourceName:
    exceptions:
      errors:
        404:
          code: ResourceNotFoundException  # Map this exception to 404""",
                code_example="# Example for DynamoDB tables\nresources:\n  Table:\n    exceptions:\n      errors:\n        404:\n          code: ResourceNotFoundException",
                prevention_tip="Check service documentation for non-standard error code mappings."
            ),

            ErrorSolution(
                error_signature="terminal error.*not handled|validation.*error.*terminal",
                error_description="Terminal errors that should stop reconciliation are not properly configured",
                category=ErrorCategory.EXCEPTION_HANDLING,
                solution_description="Add terminal error codes to prevent infinite retry loops",
                generator_yaml_fix="""resources:
  ResourceName:
    exceptions:
      terminal_codes:
        - InvalidParameterValue
        - MalformedPolicyDocument
        - ValidationException""",
                prevention_tip="Identify errors that indicate permanent failures vs transient issues."
            ),

            # FIELD MAPPING ERRORS
            ErrorSolution(
                error_signature="field.*has no members|unsupported.*field|empty.*struct",
                error_description="AWS API model includes fields that ACK cannot support or that result in invalid code/CRD schema",
                category=ErrorCategory.FIELD_MAPPING,
                solution_description="Exclude unsupported fields via ignore.field_paths in generator.yaml",
                generator_yaml_fix="""ignore:
  field_paths:
    - "VersioningConfiguration.MFADelete"  # Unsupported field
    - "NotificationConfiguration.EventBridgeConfiguration"  # Empty struct""",
                code_example="# Example from S3 controller\nignore:\n  field_paths:\n    - \"VersioningConfiguration.MFADelete\"\n    - \"NotificationConfiguration.EventBridgeConfiguration\"",
                prevention_tip="Review API models for empty structs or unsupported operations before generation."
            ),

            ErrorSolution(
                error_signature="field not found in Spec|field not found in Status",
                error_description="Referenced field name doesn't exist in the generated CRD structure",
                category=ErrorCategory.FIELD_MAPPING,
                solution_description="Check field naming and path configuration",
                generator_yaml_fix="""resources:
  ResourceName:
    fields:
      CorrectFieldName:  # Use exact field name from API
        from:
          operation: DescribeResource
          path: CorrectPath""",
                prevention_tip="Verify field names match exactly with AWS SDK Go v2 operation shapes."
            ),

            # NAMING CONFLICT ERRORS
            ErrorSolution(
                error_signature="Group redeclared in this block|other declaration of Group|naming conflict.*Group",
                error_description="Go naming collision when a resource name conflicts with Go package naming, specifically with IAM 'Group' resource",
                category=ErrorCategory.NAMING_CONFLICT,
                solution_description="Use updated ACK code-generator that resolves naming conflicts",
                generator_yaml_fix="""# This is resolved in ACK code-generator v1.0+
# If using older version, consider:
resources:
  Group:
    # Use custom operations or consider renaming if absolutely necessary""",
                prevention_tip="Use ACK code-generator v1.0+ which handles Go keyword conflicts automatically."
            ),

            # BUILD FAILURE ERRORS
            ErrorSolution(
                error_signature="make build-controller.*failed|build.*error.*compilation",
                error_description="General build failure during controller compilation",
                category=ErrorCategory.BUILD_FAILURE,
                solution_description="Check build logs for specific compilation errors and address them individually",
                code_example="""# Check build logs:
# make build-controller SERVICE=myservice 2>&1 | tee build.log
# Look for specific Go compilation errors and fix generator.yaml accordingly""",
                prevention_tip="Always run builds incrementally and fix errors one at a time."
            ),

            ErrorSolution(
                error_signature="undefined.*reference|import.*not found|package.*not found",
                error_description="Missing imports or package references in generated code",
                category=ErrorCategory.BUILD_FAILURE,
                solution_description="Ensure all required dependencies are properly configured",
                generator_yaml_fix="""# Check if custom hooks reference correct packages
resources:
  ResourceName:
    hooks:
      sdk_create_pre_build_request:
        template_path: hooks/resource/sdk_create_pre_build_request.go.tpl
        # Ensure template imports correct packages""",
                prevention_tip="Verify all custom templates have correct import statements."
            ),

            # VALIDATION ERRORS
            ErrorSolution(
                error_signature="required field.*missing|validation.*required",
                error_description="Required fields not properly configured in the generated CRD",
                category=ErrorCategory.VALIDATION,
                solution_description="Mark required fields appropriately in generator.yaml",
                generator_yaml_fix="""resources:
  ResourceName:
    fields:
      RequiredFieldName:
        is_required: true
        is_immutable: true  # if it cannot be changed after creation""",
                prevention_tip="Check AWS API documentation for required vs optional parameters."
            ),

            # API MODEL ERRORS
            ErrorSolution(
                error_signature="operation.*not found|shape.*not found|API.*model.*error",
                error_description="Referenced AWS API operation or shape doesn't exist in the service model",
                category=ErrorCategory.API_MODEL,
                solution_description="Verify operation names against the AWS SDK Go v2 service model",
                generator_yaml_fix="""resources:
  ResourceName:
    fields:
      FieldName:
        from:
          operation: CorrectOperationName  # e.g., DescribeTable not GetTable
          path: CorrectPath""",
                prevention_tip="Always check the AWS SDK Go v2 model files for exact operation names."
            )
        ]
    
    def find_solution(self, error_message: str) -> Optional[ErrorSolution]:
        """Find a solution for the given error message"""
        for error in self.errors:
            if re.search(error.error_signature, error_message, re.IGNORECASE):
                return error
        return None
    
    def get_errors_by_category(self, category: ErrorCategory) -> List[ErrorSolution]:
        """Get all errors for a specific category"""
        return [error for error in self.errors if error.category == category]
    
    def search_errors(self, keyword: str) -> List[ErrorSolution]:
        """Search errors by keyword in description or signature"""
        keyword_lower = keyword.lower()
        return [
            error for error in self.errors
            if keyword_lower in error.error_description.lower() 
            or keyword_lower in error.error_signature.lower()
            or keyword_lower in error.solution_description.lower()
        ]
    
    def export_as_tuples(self) -> List[Tuple[str, str]]:
        """Export errors and solutions as list of tuples for compatibility"""
        return [
            (error.error_signature, error.solution_description)
            for error in self.errors
        ]
    
    def export_as_json(self, filepath: str = None) -> str:
        """Export the database as JSON"""
        data = {
            "errors": [asdict(error) for error in self.errors],
            "categories": [cat.value for cat in ErrorCategory]
        }
        json_str = json.dumps(data, indent=2, default=str)
        
        if filepath:
            with open(filepath, 'w') as f:
                f.write(json_str)
        
        return json_str
    
    def print_summary(self):
        """Print a summary of the error database"""
        print("=== ACK Code Generation Error Database Summary ===")
        print(f"Total errors: {len(self.errors)}")
        print("\nErrors by category:")
        
        for category in ErrorCategory:
            count = len(self.get_errors_by_category(category))
            print(f"  {category.value}: {count} errors")
        
        print("\n=== Common Error Patterns ===")
        for i, error in enumerate(self.errors[:5], 1):
            print(f"\n{i}. {error.category.value.upper()}: {error.error_signature[:80]}...")
            print(f"   Solution: {error.solution_description[:100]}...")
    
    def generate_troubleshooting_guide(self) -> str:
        """Generate a formatted troubleshooting guide"""
        guide = """# ACK Code Generation Troubleshooting Guide

## Quick Error Reference

This guide contains solutions for common ACK code generation errors based on real patterns 
found in the ACK codebase.

"""
        
        for category in ErrorCategory:
            errors_in_category = self.get_errors_by_category(category)
            if not errors_in_category:
                continue
                
            guide += f"\n## {category.value.replace('_', ' ').title()} Errors\n\n"
            
            for error in errors_in_category:
                guide += f"### Error: `{error.error_signature}`\n\n"
                guide += f"**Description:** {error.error_description}\n\n"
                guide += f"**Solution:** {error.solution_description}\n\n"
                
                if error.generator_yaml_fix:
                    guide += "**Generator.yaml Fix:**\n```yaml\n"
                    guide += error.generator_yaml_fix
                    guide += "\n```\n\n"
                
                if error.code_example:
                    guide += "**Example:**\n```yaml\n"
                    guide += error.code_example
                    guide += "\n```\n\n"
                
                if error.prevention_tip:
                    guide += f"**💡 Prevention Tip:** {error.prevention_tip}\n\n"
                
                guide += "---\n\n"
        
        return guide


# Legacy compatibility - export as tuples for existing code
def get_common_errors() -> List[Tuple[str, str]]:
    """Get common errors as tuples for backward compatibility"""
    db = ACKErrorDatabase()
    return db.export_as_tuples()


# Main execution
if __name__ == "__main__":
    # Create database instance
    error_db = ACKErrorDatabase()
    
    # Print summary
    error_db.print_summary()
    
    # Generate and save troubleshooting guide
    guide = error_db.generate_troubleshooting_guide()
    with open("ack_troubleshooting_guide.md", "w") as f:
        f.write(guide)
    
    # Export as JSON
    error_db.export_as_json("ack_errors_database.json")
    
    print("\n✅ Generated files:")
    print("  - ack_troubleshooting_guide.md")
    print("  - ack_errors_database.json")
    
    # Example usage
    print("\n=== Example Usage ===")
    
    # Search for tag-related errors
    tag_errors = error_db.search_errors("tag")
    print(f"\nFound {len(tag_errors)} tag-related errors")
    
    # Find solution for a specific error
    sample_error = "tag field path Tags does not exist inside Bucket crd"
    solution = error_db.find_solution(sample_error)
    if solution:
        print(f"\n🔍 Error: {sample_error}")
        print(f"💡 Solution: {solution.solution_description}")
        if solution.generator_yaml_fix:
            print("🛠️  Fix:")
            print(solution.generator_yaml_fix) 