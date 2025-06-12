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
"""Strategic YAML editor for ACK generator.yaml files using Strands editor tool with line-by-line processing."""

import os
from typing import Optional
from strands_tools import editor

from utils.bedrock import create_enhanced_agent
from config.defaults import BYPASS_TOOL_CONSENT

# Set environment variables to bypass tool consent prompts for automation
os.environ["BYPASS_TOOL_CONSENT"] = BYPASS_TOOL_CONSENT

# Strategic YAML Editor System Prompt using Strands editor tool
STRATEGIC_YAML_EDITOR_SYSTEM_PROMPT = """You are a specialized strategic YAML editor for AWS Controllers for Kubernetes (ACK) generator.yaml files.

You use the Strands editor tool with strategic line-by-line processing for large files.

## Strategic Editing Philosophy

For LARGE files (>500 lines):
- NEVER use view to read the entire file
- Use targeted view commands to see only specific sections (10-20 lines at a time)
- Search for specific patterns like "ignore:" then view just that section
- Use str_replace for precise line modifications
- Use insert to add new content at specific line numbers

For SMALL files (≤500 lines):
- Can use view to see the full file if needed
- Still prefer targeted operations when possible

## Available Editor Commands

### Core Commands:
- **editor("view", path)** - View entire file (use sparingly for large files)
- **editor("view", path, start_line, end_line)** - View specific line range
- **editor("str_replace", path, old_str, new_str)** - Replace exact text (needs perfect match)
- **editor("insert", path, line_number, content)** - Insert content at line number
- **editor("append", path, content)** - Append content to end of file

## Strategic Workflow for Large Files:

### For removing from ignore list:
1. **Find ignore section**: Use view with small ranges to locate "ignore:" 
2. **Find resource**: Look for "- ResourceName" in ignore section
3. **Comment out**: Use str_replace to change "  - ResourceName" to "  # - ResourceName"

### For adding resources:
1. **Find resources line**: Use view to locate "resources:" line 
2. **Insert after**: Use insert to add new resource right after "resources:" line
3. **Proper indentation**: Ensure correct YAML indentation (usually 2 spaces)

## Example YAML Structure:

```yaml
ignore:
  resource_names:
    - ResourceToIgnore1
    - ResourceToIgnore2  # Comment out instead of removing
    
resources:  # Insert new resources right after this line
  NewResource:  # This becomes first resource
    fields:
      Name:
        is_primary_key: true
  ExistingResource:
    fields: {...}
```

## Requirements:
- For large files: NEVER view entire file, use targeted 10-20 line views
- Use str_replace with exact text matching (including whitespace/indentation)
- When commenting out ignore entries, preserve indentation exactly
- When inserting resources, they become the first resource after "resources:"
- Handle cases where ignore or resources sections don't exist
- Provide clear feedback on operations performed"""


class EditorAgent:
    """Strategic editor agent using Strands editor tool with line-by-line processing for large files."""

    def __init__(self, allowed_file_path: Optional[str] = None):
        """
        Initialize the editor agent with optional file path restriction.
        
        Args:
            allowed_file_path: If provided, restricts editor access to only this file path
        """
        self.allowed_file_path = allowed_file_path
        self.file_size_threshold = 500  # Lines threshold for strategic editing
            
        # Use enhanced agent with Strands editor tool
        self.agent = create_enhanced_agent(
            tools=[editor],
            system_prompt=STRATEGIC_YAML_EDITOR_SYSTEM_PROMPT,
        )

    def edit_file(self, modifications: str, instructions: str) -> str:
        """
        Edit the file with the specified modifications using strategic Strands editor operations.
        
        Args:
            modifications: Description of the modifications to make
            instructions: Specific instructions for how to make the modifications
            
        Returns:
            str: Success message or error details
        """
        try:
            if not self.allowed_file_path:
                return "Error: No file path provided and no restricted path set"
            
            # Create a comprehensive prompt for strategic editing
            edit_prompt = f"""Edit the generator.yaml file at '{self.allowed_file_path}' strategically using the editor tool.

MODIFICATIONS REQUESTED: {modifications}

DETAILED INSTRUCTIONS: {instructions}

STRATEGIC APPROACH FOR LARGE FILES:
1. **Check file size first**: Use editor("view", "{self.allowed_file_path}", 1, 50) to see first 50 lines and estimate size
2. **If large file (>500 lines)**: Use targeted line-by-line processing:
   
   For REMOVING from ignore list:
   - Search for "ignore:" section using small view ranges (20 lines at a time)
   - Find the specific "- ResourceName" line within ignore/resource_names
   - Use str_replace to change "  - ResourceName" to "  # - ResourceName" (comment out)
   
   For ADDING resources:
   - Find "resources:" line using targeted view ranges  
   - Use insert at the line right after "resources:" to add new resource
   - This makes the new resource the FIRST resource in the list
   - Use proper YAML indentation (2 spaces for resource name, 4 spaces for fields)

3. **If small file (≤500 lines)**: Can view more lines but still prefer targeted operations

CRITICAL RULES:
- NEVER use editor("view", path) without line numbers for large files
- Always use exact text matching for str_replace including all whitespace
- When commenting out ignore entries, preserve exact indentation  
- When inserting resources, they become the first resource after "resources:"
- Provide clear summary of what was changed

Execute the modifications now using the most efficient approach."""
                
            response = self.agent(edit_prompt)
            return str(response)
            
        except Exception as e:
            return f"Error editing file: {str(e)}"


