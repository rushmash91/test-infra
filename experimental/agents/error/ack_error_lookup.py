#!/usr/bin/env python3
"""
ACK Error Lookup Utility

A simple command-line utility for quickly finding solutions to ACK code generation errors.
"""

import sys
import argparse
from ack_code_generation_errors_and_solutions import ACKErrorDatabase, ErrorCategory


def main():
    parser = argparse.ArgumentParser(
        description="Look up solutions for ACK code generation errors",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 ack_error_lookup.py "tag field path Tags does not exist"
  python3 ack_error_lookup.py --category tagging
  python3 ack_error_lookup.py --search "primary key"
  python3 ack_error_lookup.py --list-categories
        """
    )
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("error_message", nargs="?", help="Error message to look up")
    group.add_argument("--category", choices=[cat.value for cat in ErrorCategory], 
                      help="List all errors in a category")
    group.add_argument("--search", help="Search for errors containing keyword")
    group.add_argument("--list-categories", action="store_true", 
                      help="List all available error categories")
    group.add_argument("--summary", action="store_true", 
                      help="Show database summary")
    
    args = parser.parse_args()
    
    # Initialize database
    db = ACKErrorDatabase()
    
    if args.list_categories:
        print("Available error categories:")
        for cat in ErrorCategory:
            count = len(db.get_errors_by_category(cat))
            print(f"  {cat.value}: {count} errors")
    
    elif args.summary:
        db.print_summary()
    
    elif args.category:
        category = ErrorCategory(args.category)
        errors = db.get_errors_by_category(category)
        print(f"\n=== {category.value.title()} Errors ===")
        for i, error in enumerate(errors, 1):
            print(f"\n{i}. {error.error_signature}")
            print(f"   Solution: {error.solution_description}")
    
    elif args.search:
        errors = db.search_errors(args.search)
        print(f"\n=== Search Results for '{args.search}' ===")
        if not errors:
            print("No errors found matching your search.")
        else:
            for i, error in enumerate(errors, 1):
                print(f"\n{i}. {error.error_signature}")
                print(f"   Category: {error.category.value}")
                print(f"   Solution: {error.solution_description}")
    
    elif args.error_message:
        solution = db.find_solution(args.error_message)
        if solution:
            print(f"\n🔍 Error Match Found!")
            print(f"📋 Category: {solution.category.value}")
            print(f"📝 Description: {solution.error_description}")
            print(f"💡 Solution: {solution.solution_description}")
            
            if solution.generator_yaml_fix:
                print(f"\n🛠️  Generator.yaml Fix:")
                print(solution.generator_yaml_fix)
            
            if solution.code_example:
                print(f"\n📚 Example:")
                print(solution.code_example)
            
            if solution.prevention_tip:
                print(f"\n💡 Prevention Tip: {solution.prevention_tip}")
        else:
            print(f"\n❌ No exact match found for: '{args.error_message}'")
            print("\n🔍 Trying keyword search...")
            
            # Fallback to keyword search
            words = args.error_message.split()
            for word in words:
                if len(word) > 3:  # Only search meaningful words
                    results = db.search_errors(word)
                    if results:
                        print(f"\n📋 Related errors containing '{word}':")
                        for i, error in enumerate(results[:3], 1):  # Show top 3
                            print(f"  {i}. {error.error_signature[:80]}...")
                        break
            else:
                print("\n💡 Try using --search with keywords or --category to browse by type")


if __name__ == "__main__":
    main() 