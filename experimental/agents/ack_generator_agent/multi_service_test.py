#!/usr/bin/env python3
"""
Multi-service test to find services with rich metadata like HTTP bindings, traits, documentation, etc.
This will help us validate that our comprehensive extraction is working across different AWS services.
"""

from tools import read_service_model
import json

def test_service_comprehensive(service: str, resource: str):
    """Test a specific service/resource combination for comprehensive features."""
    
    print(f"\n🔍 TESTING: {service.upper()} {resource}")
    print("=" * 60)
    
    try:
        result = read_service_model(service, resource)
        data = json.loads(result)
        
        # Summary statistics
        summary = data.get('summary', {})
        print(f"📊 Summary:")
        print(f"   Resource: {summary.get('resource_shape', 'N/A').split('#')[-1]}")
        print(f"   Operations: {summary.get('related_operations_count', 0)}")
        print(f"   Errors: {summary.get('error_shapes_count', 0)}")
        print(f"   Related Shapes: {summary.get('related_shapes_count', 0)}")
        print(f"   Enhanced Shapes: {summary.get('total_enhanced_shapes', 0)}")
        
        # Check for rich metadata
        rich_features = {
            'Documentation': summary.get('has_documentation', 0),
            'Traits': summary.get('shapes_with_traits', 0),
            'HTTP Bindings': summary.get('operations_with_http_bindings', 0),
            'Authentication': summary.get('operations_with_auth', 0),
            'Pagination': summary.get('paginated_operations', 0),
            'Enums': summary.get('enums_count', 0),
            'Unions': summary.get('unions_count', 0)
        }
        
        print(f"🏆 Rich Features:")
        for feature, count in rich_features.items():
            status = "✅" if count > 0 else "❌"
            print(f"   {status} {feature}: {count}")
        
        # Show sample errors if any
        error_shapes = data.get('error_shapes', {})
        if error_shapes:
            print(f"🚨 Sample Errors:")
            for error_name in list(error_shapes.keys())[:3]:
                error_short = error_name.split('#')[-1] if '#' in error_name else error_name
                print(f"   - {error_short}")
        
        # Show sample operations by type
        operations = list(data.get('related_operations', {}).keys())
        if operations:
            create_ops = [op for op in operations if 'Create' in op or 'Put' in op]
            read_ops = [op for op in operations if 'Get' in op or 'List' in op or 'Describe' in op]
            delete_ops = [op for op in operations if 'Delete' in op]
            
            print(f"🔧 Operation Types:")
            if create_ops:
                print(f"   Create: {len(create_ops)} (e.g., {create_ops[0].split('#')[-1]})")
            if read_ops:
                print(f"   Read: {len(read_ops)} (e.g., {read_ops[0].split('#')[-1]})")
            if delete_ops:
                print(f"   Delete: {len(delete_ops)} (e.g., {delete_ops[0].split('#')[-1]})")
        
        # Check for actual traits and documentation in enhanced shapes
        enhanced_shapes = data.get('enhanced_shapes', {})
        shapes_with_real_traits = 0
        shapes_with_real_docs = 0
        sample_traits = []
        sample_docs = []
        
        for shape_name, shape_info in enhanced_shapes.items():
            traits = shape_info.get('traits', {})
            docs = shape_info.get('documentation')
            
            if traits:
                shapes_with_real_traits += 1
                if len(sample_traits) < 3:
                    sample_traits.extend(list(traits.keys())[:2])
            
            if docs:
                shapes_with_real_docs += 1
                if len(sample_docs) < 2:
                    sample_docs.append(docs[:80] + "..." if len(docs) > 80 else docs)
        
        if sample_traits:
            print(f"🎯 Sample Traits Found:")
            for trait in sample_traits[:3]:
                print(f"   - {trait}")
        
        if sample_docs:
            print(f"📚 Sample Documentation Found:")
            for doc in sample_docs[:2]:
                print(f"   - {doc}")
        
        # Calculate richness score
        total_features = sum(rich_features.values())
        richness_score = min(100, (total_features / 10) * 100)  # Scale to 100
        
        print(f"💎 Richness Score: {richness_score:.1f}/100")
        
        return {
            'service': service,
            'resource': resource,
            'richness_score': richness_score,
            'features': rich_features,
            'has_traits': shapes_with_real_traits > 0,
            'has_docs': shapes_with_real_docs > 0,
            'total_operations': len(operations),
            'total_errors': len(error_shapes)
        }
        
    except Exception as e:
        print(f"❌ Error testing {service}/{resource}: {e}")
        return None

def main():
    """Test multiple services to find ones with rich metadata."""
    
    print("🌟 MULTI-SERVICE COMPREHENSIVE TEST")
    print("=" * 80)
    print("Testing multiple AWS services to find rich metadata features like:")
    print("  🎯 HTTP bindings, traits, documentation, authentication, pagination")
    print("=" * 80)
    
    # Test various service/resource combinations
    test_cases = [
        # Storage services
        ("s3", "Bucket"),
        ("s3", "Object"),
        
        # Database services
        ("dynamodb", "Table"),
        ("dynamodb", "GlobalTable"),
        ("rds", "DBCluster"),
        ("rds", "DBInstance"),
        
        # Compute services
        ("ec2", "Instance"),
        ("ec2", "VPC"),
        ("lambda", "Function"),
        
        # Security/Identity
        ("iam", "Role"),
        ("iam", "Policy"),
        
        # Management services
        ("cloudformation", "Stack"),
        ("ssm", "Parameter"),
        
        # Analytics
        ("kinesis", "Stream"),
        
        # API Gateway
        ("apigateway", "RestApi"),
        
        # Container services
        ("ecs", "Cluster"),
        ("eks", "Cluster"),
        
        # Application services
        ("sns", "Topic"),
        ("sqs", "Queue"),
    ]
    
    results = []
    
    for service, resource in test_cases:
        try:
            result = test_service_comprehensive(service, resource)
            if result:
                results.append(result)
        except Exception as e:
            print(f"❌ Failed to test {service}/{resource}: {e}")
            continue
    
    # Analyze results
    print("\n" + "=" * 80)
    print("📈 ANALYSIS RESULTS")
    print("=" * 80)
    
    if not results:
        print("❌ No successful tests completed")
        return
    
    # Sort by richness score
    results.sort(key=lambda x: x['richness_score'], reverse=True)
    
    print("🏆 TOP SERVICES BY RICHNESS:")
    for i, result in enumerate(results[:5]):
        service = result['service']
        resource = result['resource']
        score = result['richness_score']
        ops = result['total_operations']
        errors = result['total_errors']
        
        print(f"   {i+1}. {service.upper()}/{resource} - Score: {score:.1f}/100")
        print(f"      Operations: {ops}, Errors: {errors}")
        
        # Show which features this service has
        features_found = [name for name, count in result['features'].items() if count > 0]
        if features_found:
            print(f"      Features: {', '.join(features_found[:4])}")
        print()
    
    # Find services with specific features
    services_with_traits = [r for r in results if r['has_traits']]
    services_with_docs = [r for r in results if r['has_docs']]
    services_with_auth = [r for r in results if r['features']['Authentication'] > 0]
    services_with_pagination = [r for r in results if r['features']['Pagination'] > 0]
    services_with_http = [r for r in results if r['features']['HTTP Bindings'] > 0]
    
    print("🎯 FEATURE ANALYSIS:")
    print(f"   Services with Traits: {len(services_with_traits)}")
    print(f"   Services with Documentation: {len(services_with_docs)}")
    print(f"   Services with Authentication: {len(services_with_auth)}")
    print(f"   Services with Pagination: {len(services_with_pagination)}")
    print(f"   Services with HTTP Bindings: {len(services_with_http)}")
    
    if services_with_traits:
        print(f"\n✅ SERVICES WITH TRAITS:")
        for result in services_with_traits[:3]:
            print(f"   - {result['service'].upper()}/{result['resource']}")
    
    if services_with_docs:
        print(f"\n✅ SERVICES WITH DOCUMENTATION:")
        for result in services_with_docs[:3]:
            print(f"   - {result['service'].upper()}/{result['resource']}")
    
    if not any([services_with_traits, services_with_docs, services_with_auth, services_with_pagination, services_with_http]):
        print("\n⚠️  NO SERVICES FOUND WITH ADVANCED FEATURES")
        print("This might indicate that our trait/documentation extraction needs improvement")
        print("or that the Smithy models use different trait naming conventions.")
    
    print("\n" + "=" * 80)
    print(f"✅ Tested {len(results)} services successfully")
    print("🔍 This helps identify which services have the richest metadata for ACK generation")
    print("=" * 80)

if __name__ == "__main__":
    main() 