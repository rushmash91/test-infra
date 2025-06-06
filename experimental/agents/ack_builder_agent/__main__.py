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
"""Main entry point for the ACK agent CLI."""

import argparse
import logging
import warnings
from strands import Agent
from strands.models import BedrockModel
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
import re
import json

from ack_builder_agent.tools import (
    build_controller,
    read_build_log,
    sleep,
    verify_build_completion,
)
from ack_builder_agent.prompts import ACK_BUILDER_SYSTEM_PROMPT
from config.defaults import DEFAULT_REGION, DEFAULT_MODEL_ID, DEFAULT_TEMPERATURE

console = Console()

def configure_logging(debug=False):
    """Configure logging for the application.
    
    Args:
        debug: Whether to enable debug logging
    """
    log_level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(levelname)s | %(name)s | %(message)s"
    )
    
    # Always enable Strands debug logs if debug is enabled
    if debug:
        logging.getLogger("strands").setLevel(logging.DEBUG)
    
    # Suppress deprecation warnings from botocore about datetime.utcnow()
    warnings.filterwarnings("ignore", category=DeprecationWarning, module="botocore")

def pretty_markdown(md) -> Markdown:
    # If it's a dict, pretty-print as JSON
    if isinstance(md, dict):
        md = json.dumps(md, indent=2)
    elif not isinstance(md, str):
        md = str(md)
    clean = re.sub(r"(\n\s*){3,}", "\n\n", (md or "").strip())
    return Markdown(clean)

def run_agent_cli():
    """Run the agent CLI with command line arguments."""
    parser = argparse.ArgumentParser(
        description="ACK Controller Assistant CLI"
    )
    parser.add_argument(
        "--region", 
        type=str, 
        default=DEFAULT_REGION, 
        help="AWS region for Bedrock"
    )
    parser.add_argument(
        "--model", 
        type=str, 
        default=DEFAULT_MODEL_ID, 
        help="Model ID for Claude on Bedrock"
    )
    parser.add_argument(
        "--temperature", 
        type=float, 
        default=DEFAULT_TEMPERATURE, 
        help="Temperature for model generation"
    )
    parser.add_argument(
        "--debug", 
        action="store_true", 
        help="Enable debug logging"
    )
    
    args = parser.parse_args()
    configure_logging(args.debug)
    
    # Create model provider
    bedrock_model = BedrockModel(
        model_id=args.model,
        region_name=args.region,
        temperature=args.temperature,
    )
    
    # Create the agent with our ACK tools
    agent = Agent(
        model=bedrock_model,
        tools=[
            build_controller,
            read_build_log,
            sleep,
            verify_build_completion,
        ],
        system_prompt=ACK_BUILDER_SYSTEM_PROMPT
    )
    
    console.print("[bold green]ACK Controller Builder Agent initialized. Type 'exit' to quit.[/bold green]\n")
    
    while True:
        user_input = console.input("\n[bold cyan]Builder Agent>[/bold cyan] ").strip()
        
        if user_input.lower() in ['exit', 'quit', 'bye']:
            console.print("[bold yellow]Goodbye![/bold yellow]")
            break
        
        if not user_input:
            continue
        
        try:
            console.print("\n[bold]Processing...[/bold]")
            response = agent(user_input)
            # If response is markdown, render it as markdown
            if hasattr(response, "message"):
                console.print(pretty_markdown(response.message))
            else:
                console.print(pretty_markdown(response))
        except Exception as e:
            console.print(Panel(f"[red]Error: {e}[/red]", title="Error", style="red"))

if __name__ == "__main__":
    run_agent_cli() 