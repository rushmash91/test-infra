#!/usr/bin/env python3
"""
Deep investigation of traits, documentation, and metadata in AWS Smithy models.
This will help us understand what kinds of metadata are actually available.
"""

from tools import read_service_model
import json

def investigate_traits_deeply(service: str, resource: str):
    """Investigate what traits and metadata we can actually find."""
    
    print(f"\n🔬 DEEP TRAIT INVESTIGATION: {service.upper()} {resource}")
    print("=" * 70)
    
    try:
        result = read_service_model(service, resource)
        data = json.loads(result)
        
        enhanced_shapes = data.get('enhanced_shapes', {})
        
        print(f"📊 Found {len(enhanced_shapes)} enhanced shapes")
        
        # Analyze each shape type
        trait_examples = {}
        doc_examples = {}
        shape_type_counts = {}
        
        for shape_name, shape_info in enhanced_shapes.items():
            shape_type = shape_info.get('type', 'unknown')
            shape_type_counts[shape_type] = shape_type_counts.get(shape_type, 0) + 1
            
            # Look at traits
            traits = shape_info.get('traits', {})
            if traits:
                for trait_key, trait_value in traits.items():
                    if trait_key not in trait_examples:
                        trait_examples[trait_key] = []
                    if len(trait_examples[trait_key]) < 3:
                        trait_examples[trait_key].append({
                            'shape': shape_name.split('#')[-1],
                            'value': trait_value,
                            'type': shape_type
                        })
            
            # Look at documentation
            docs = shape_info.get('documentation')
            if docs and len(doc_examples) < 5:
                doc_examples[shape_name.split('#')[-1]] = docs[:200] + "..." if len(docs) > 200 else docs
        
        # Show shape type distribution
        print(f"\n📈 Shape Type Distribution:")
        for shape_type, count in sorted(shape_type_counts.items()):
            print(f"   {shape_type}: {count}")
        
        # Show trait examples
        print(f"\n🎯 Trait Analysis ({len(trait_examples)} unique traits found):")
        for trait_key, examples in trait_examples.items():
            print(f"\n   Trait: '{trait_key}'")
            print(f"   Found in {len(examples)} shapes:")
            for example in examples:
                shape_name = example['shape']
                value = example['value']
                shape_type = example['type']
                
                # Show a preview of the value
                if isinstance(value, dict):
                    value_preview = f"Dict with {len(value)} keys: {list(value.keys())[:3]}"
                elif isinstance(value, list):
                    value_preview = f"List with {len(value)} items"
                elif isinstance(value, str) and len(value) > 50:
                    value_preview = f"'{value[:50]}...'"
                else:
                    value_preview = f"'{value}'"
                
                print(f"     - {shape_name} ({shape_type}): {value_preview}")
        
        # Show documentation examples
        if doc_examples:
            print(f"\n📚 Documentation Examples ({len(doc_examples)} found):")
            for shape_name, doc_text in doc_examples.items():
                print(f"\n   {shape_name}:")
                print(f"     {doc_text}")
        else:
            print(f"\n📚 Documentation: None found")
        
        # Let's also look at the raw shape data to see what we might be missing
        print(f"\n🔍 Raw Shape Data Analysis:")
        
        # Pick a few interesting shapes to examine
        sample_shapes = list(enhanced_shapes.items())[:3]
        for shape_name, shape_info in sample_shapes:
            print(f"\n   Shape: {shape_name.split('#')[-1]}")
            shape_data = shape_info.get('shape_data', {})
            
            print(f"   Raw keys: {list(shape_data.keys())}")
            
            # Look for any keys that might be traits we're missing
            potential_traits = []
            for key, value in shape_data.items():
                if key not in ['type', 'members', 'target', 'member', 'key', 'value']:
                    potential_traits.append(f"{key}: {type(value).__name__}")
            
            if potential_traits:
                print(f"   Potential traits: {potential_traits}")
            else:
                print(f"   No additional traits found")
        
        return {
            'trait_count': len(trait_examples),
            'doc_count': len(doc_examples),
            'shape_types': shape_type_counts,
            'trait_examples': trait_examples
        }
        
    except Exception as e:
        print(f"❌ Error in deep investigation: {e}")
        return None

def investigate_operations_and_errors(service: str, resource: str):
    """Look at what's in operations and error shapes."""
    
    print(f"\n🔧 OPERATION & ERROR INVESTIGATION: {service.upper()} {resource}")
    print("=" * 70)
    
    try:
        result = read_service_model(service, resource)
        data = json.loads(result)
        
        # Investigate operations
        related_operations = data.get('related_operations', {})
        print(f"\n📋 Operations Analysis ({len(related_operations)} operations):")
        
        for i, (op_name, op_data) in enumerate(list(related_operations.items())[:3]):
            op_short = op_name.split('#')[-1]
            print(f"\n   Operation {i+1}: {op_short}")
            print(f"   Keys: {list(op_data.keys())}")
            
            # Look for interesting data
            input_info = op_data.get('input', {})
            output_info = op_data.get('output', {})
            errors = op_data.get('errors', [])
            
            if input_info:
                print(f"   Input: {input_info}")
            if output_info:
                print(f"   Output: {output_info}")
            if errors:
                print(f"   Errors: {len(errors)} error types")
        
        # Investigate error shapes
        error_shapes = data.get('error_shapes', {})
        print(f"\n🚨 Error Shapes Analysis ({len(error_shapes)} errors):")
        
        for error_name, error_data in list(error_shapes.items())[:3]:
            error_short = error_name.split('#')[-1]
            print(f"\n   Error: {error_short}")
            print(f"   Type: {error_data.get('type', 'unknown')}")
            
            members = error_data.get('members', {})
            if members:
                print(f"   Members: {list(members.keys())}")
            
            # Look for any error-specific traits
            error_traits = []
            for key, value in error_data.items():
                if key not in ['type', 'members']:
                    error_traits.append(f"{key}: {type(value).__name__}")
            
            if error_traits:
                print(f"   Additional data: {error_traits}")
        
    except Exception as e:
        print(f"❌ Error in operation investigation: {e}")

def main():
    """Run comprehensive trait and metadata investigation."""
    
    print("🔬 COMPREHENSIVE TRAIT & METADATA INVESTIGATION")
    print("=" * 80)
    print("This will show us exactly what kinds of traits, documentation,")
    print("and metadata are actually present in AWS Smithy models.")
    print("=" * 80)
    
    # Test a few different services
    test_cases = [
        ("s3", "Bucket"),
        ("dynamodb", "Table"),
        ("lambda", "Function"),
        ("iam", "Role")
    ]
    
    all_results = []
    
    for service, resource in test_cases:
        try:
            result = investigate_traits_deeply(service, resource)
            if result:
                all_results.append({
                    'service': service,
                    'resource': resource,
                    'result': result
                })
            
            investigate_operations_and_errors(service, resource)
            
        except Exception as e:
            print(f"❌ Failed to investigate {service}/{resource}: {e}")
    
    # Summary analysis
    print("\n" + "=" * 80)
    print("📊 SUMMARY ANALYSIS")
    print("=" * 80)
    
    if all_results:
        total_traits = sum(r['result']['trait_count'] for r in all_results)
        total_docs = sum(r['result']['doc_count'] for r in all_results)
        
        print(f"✅ Across {len(all_results)} services:")
        print(f"   Total unique trait types found: {total_traits}")
        print(f"   Total shapes with documentation: {total_docs}")
        
        # Show all unique traits found
        all_traits = set()
        for result in all_results:
            all_traits.update(result['result']['trait_examples'].keys())
        
        if all_traits:
            print(f"\n🎯 All Trait Types Found:")
            for trait in sorted(all_traits):
                print(f"   - {trait}")
        
        # Show common shape types
        all_shape_types = {}
        for result in all_results:
            for shape_type, count in result['result']['shape_types'].items():
                all_shape_types[shape_type] = all_shape_types.get(shape_type, 0) + count
        
        print(f"\n📈 All Shape Types Across Services:")
        for shape_type, count in sorted(all_shape_types.items(), key=lambda x: x[1], reverse=True):
            print(f"   {shape_type}: {count}")
    
    print("\n" + "=" * 80)
    print("🔍 This investigation helps us understand what metadata is")
    print("   actually available in AWS Smithy models vs. what's in the SDK.")
    print("=" * 80)

if __name__ == "__main__":
    main() 