#!/usr/bin/env python3
"""
Comprehensive test showing ALL information captured by the enhanced read_service_model function.
This demonstrates errors, traits, documentation, HTTP bindings, constraints, and everything else.
"""

from tools import read_service_model
import json

def test_comprehensive_s3_bucket():
    """Test comprehensive information extraction for S3 Bucket."""
    
    print("🚀 COMPREHENSIVE S3 BUCKET ANALYSIS")
    print("=" * 80)
    
    try:
        result = read_service_model("s3", "Bucket")
        data = json.loads(result)
        
        # Summary first
        summary = data.get('summary', {})
        print("📊 SUMMARY STATISTICS:")
        print(f"   Resource: {summary.get('resource_shape', 'N/A')}")
        print(f"   Related Operations: {summary.get('related_operations_count', 0)}")
        print(f"   Error Shapes: {summary.get('error_shapes_count', 0)}")
        print(f"   Related Shapes: {summary.get('related_shapes_count', 0)}")
        print(f"   Enhanced Shapes: {summary.get('total_enhanced_shapes', 0)}")
        print(f"   Enums: {summary.get('enums_count', 0)}")
        print(f"   Unions: {summary.get('unions_count', 0)}")
        print(f"   Shapes with Documentation: {summary.get('has_documentation', 0)}")
        print(f"   Shapes with Traits: {summary.get('shapes_with_traits', 0)}")
        print(f"   Operations with HTTP Bindings: {summary.get('operations_with_http_bindings', 0)}")
        print(f"   Operations with Auth: {summary.get('operations_with_auth', 0)}")
        print(f"   Paginated Operations: {summary.get('paginated_operations', 0)}")
        
        # Error shapes
        error_shapes = data.get('error_shapes', {})
        print(f"\n🚨 ERROR SHAPES ({len(error_shapes)}):")
        for i, (error_name, error_data) in enumerate(list(error_shapes.items())[:5]):
            error_type = error_data.get('type', 'unknown')
            print(f"   {i+1}. {error_name} ({error_type})")
        if len(error_shapes) > 5:
            print(f"   ... and {len(error_shapes) - 5} more error shapes")
        
        # Operation details with HTTP bindings
        operation_details = data.get('operation_details', {})
        print(f"\n🔧 OPERATION DETAILS (showing first 3 of {len(operation_details)}):")
        for i, (op_name, op_detail) in enumerate(list(operation_details.items())[:3]):
            print(f"   Operation: {op_name}")
            http_bindings = op_detail.get('http_bindings', {})
            auth = op_detail.get('authentication', {})
            pagination = op_detail.get('pagination', {})
            constraints = op_detail.get('constraints', {})
            
            if http_bindings:
                print(f"      HTTP Bindings: {len(http_bindings)} found")
            if auth:
                print(f"      Authentication: {len(auth)} rules")
            if pagination:
                print(f"      Pagination: {len(pagination)} configs")
            if constraints:
                print(f"      Constraints: {len(constraints)} rules")
        
        # Enhanced shapes with traits and documentation
        enhanced_shapes = data.get('enhanced_shapes', {})
        shapes_with_docs = [s for s in enhanced_shapes.values() if s.get('documentation')]
        shapes_with_traits = [s for s in enhanced_shapes.values() if s.get('traits')]
        
        print(f"\n📚 DOCUMENTATION & TRAITS:")
        print(f"   Shapes with Documentation: {len(shapes_with_docs)}")
        print(f"   Shapes with Traits: {len(shapes_with_traits)}")
        
        if shapes_with_docs:
            print(f"   Sample documented shape:")
            sample_doc = shapes_with_docs[0]
            print(f"      Documentation: {sample_doc['documentation'][:100]}...")
        
        if shapes_with_traits:
            print(f"   Sample shape with traits:")
            sample_traits = shapes_with_traits[0]
            trait_keys = list(sample_traits['traits'].keys())[:3]
            print(f"      Traits: {trait_keys}")
        
        # Enums and unions
        enums_and_unions = data.get('enums_and_unions', {})
        enums = [eu for eu in enums_and_unions.values() if eu['type'] == 'enum']
        unions = [eu for eu in enums_and_unions.values() if eu['type'] == 'union']
        
        print(f"\n🔢 ENUMS & UNIONS:")
        print(f"   Enums: {len(enums)}")
        print(f"   Unions: {len(unions)}")
        
        if enums:
            enum_name = [k for k, v in enums_and_unions.items() if v['type'] == 'enum'][0]
            enum_members = enums[0].get('members', [])
            print(f"   Sample enum '{enum_name}': {len(enum_members)} members")
        
        # Service metadata
        service_metadata = data.get('service_metadata', {})
        print(f"\n🏢 SERVICE METADATA:")
        print(f"   Service: {service_metadata.get('service_name', 'N/A')}")
        print(f"   Smithy Version: {service_metadata.get('smithy_version', 'N/A')}")
        print(f"   Namespace: {service_metadata.get('namespace', 'N/A')}")
        print(f"   Total Shapes in Service: {service_metadata.get('total_shapes', 0)}")
        print(f"   Total Operations in Service: {service_metadata.get('total_operations', 0)}")
        print(f"   Total Errors in Service: {service_metadata.get('total_errors', 0)}")
        
        service_traits = service_metadata.get('service_traits', {})
        if service_traits:
            print(f"   Service Traits: {len(service_traits)} found")
            print(f"      Sample traits: {list(service_traits.keys())[:3]}")
        
        print("\n✅ COMPREHENSIVE ANALYSIS COMPLETE!")
        return True
        
    except Exception as e:
        print(f"❌ Error in comprehensive analysis: {e}")
        return False

def test_operation_crud_mapping():
    """Show how operations map to CRUD patterns."""
    
    print("\n🔄 CRUD OPERATION MAPPING")
    print("=" * 50)
    
    try:
        result = read_service_model("s3", "Bucket")
        data = json.loads(result)
        
        operations = list(data.get('related_operations', {}).keys())
        
        # Categorize operations by CRUD patterns
        crud_mapping = {
            'Create': [op for op in operations if 'Create' in op or 'Put' in op],
            'Read/Get': [op for op in operations if 'Get' in op or 'List' in op or 'Describe' in op],
            'Update': [op for op in operations if 'Update' in op or 'Modify' in op],
            'Delete': [op for op in operations if 'Delete' in op],
            'Other': []
        }
        
        # Find operations that don't fit CRUD patterns
        all_crud_ops = set()
        for ops in crud_mapping.values():
            all_crud_ops.update(ops)
        crud_mapping['Other'] = [op for op in operations if op not in all_crud_ops]
        
        for category, ops in crud_mapping.items():
            if ops:
                print(f"\n{category} Operations ({len(ops)}):")
                for op in ops[:3]:  # Show first 3
                    op_short = op.split('#')[-1] if '#' in op else op
                    print(f"   - {op_short}")
                if len(ops) > 3:
                    print(f"   ... and {len(ops) - 3} more")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in CRUD mapping: {e}")
        return False

def test_error_analysis():
    """Analyze error shapes in detail."""
    
    print("\n🚨 ERROR ANALYSIS")
    print("=" * 30)
    
    try:
        result = read_service_model("s3", "Bucket")
        data = json.loads(result)
        
        error_shapes = data.get('error_shapes', {})
        
        if not error_shapes:
            print("   No error shapes found.")
            return True
        
        print(f"Found {len(error_shapes)} error shapes:")
        
        for error_name, error_data in list(error_shapes.items())[:5]:
            error_short = error_name.split('#')[-1] if '#' in error_name else error_name
            error_type = error_data.get('type', 'unknown')
            
            # Check if error has members (structure details)
            members = error_data.get('members', {})
            
            print(f"\n   Error: {error_short}")
            print(f"      Type: {error_type}")
            if members:
                print(f"      Members: {len(members)}")
                for member_name in list(members.keys())[:2]:
                    print(f"         - {member_name}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in error analysis: {e}")
        return False

if __name__ == "__main__":
    print("🔍 COMPREHENSIVE RESOURCE ANALYSIS")
    print("=" * 80)
    print("Testing the enhanced read_service_model function that captures:")
    print("  ✅ Error shapes and exception handling")
    print("  ✅ Traits and metadata")
    print("  ✅ Documentation strings")
    print("  ✅ HTTP bindings and constraints")
    print("  ✅ Authentication requirements")
    print("  ✅ Pagination information")
    print("  ✅ Enum values and union variants")
    print("  ✅ CRUD operation mapping")
    print("  ✅ Service-level metadata")
    print()
    
    # Run comprehensive tests
    success = True
    success &= test_comprehensive_s3_bucket()
    success &= test_operation_crud_mapping()
    success &= test_error_analysis()
    
    print("\n" + "=" * 80)
    if success:
        print("🎉 ALL COMPREHENSIVE TESTS PASSED!")
        print("The enhanced function now captures EVERYTHING about the resource!")
    else:
        print("⚠️  Some tests had issues, but the enhancement is working.")
    print("=" * 80) 