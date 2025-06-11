#!/usr/bin/env -S uv run
# /// script
# dependencies = [
#   "openai>=1.0.0",
#   "requests>=2.31.0",
# ]
# ///
"""
Image generator for Vibe Coding presentation.

This script parses the markdown file, finds image placeholders with IMG_GEN tags,
and generates images using OpenAI's DALL-E API.

Usage: 
  uv run generate_images.py                    # Generate all images with IMG_GEN tags
  uv run generate_images.py --target=PATH      # Generate only the specified image
"""

import re
import json
import os
import sys
from pathlib import Path
from typing import Dict, List
import requests
from openai import OpenAI

# Configuration
MARKDOWN_FILE = "vibecoding.md"

def extract_images_with_prompts(markdown_content: str) -> List[Dict]:
    """
    Extract image placeholders with IMG_GEN tags from markdown.
    
    Looks for patterns like:
    <!-- IMG_GEN: {"prompt": "description", "size": "1024x1024"} -->
    ![bg right:40% 80%](images/placeholder-image-name.png)
    
    Returns list of dicts with full path, prompt, and dimensions.
    """
    images = []
    lines = markdown_content.split('\n')
    
    for i, line in enumerate(lines):
        # Look for image placeholders
        img_match = re.search(r'!\[.*?\]\((.*?placeholder-.*?\.png)\)', line)
        if img_match:
            full_path = img_match.group(1)
            
            # Look backwards for IMG_GEN comment (up to 5 lines back)
            prompt = None
            size = "1024x1024"
            
            for j in range(max(0, i-5), i):
                comment_line = lines[j].strip()
                
                # Look for IMG_GEN comment with JSON
                gen_match = re.search(r'<!--\s*IMG_GEN:\s*({.*?})\s*-->', comment_line)
                if gen_match:
                    try:
                        config = json.loads(gen_match.group(1))
                        prompt = config.get('prompt')
                        size = config.get('size', '1024x1024')
                        break
                    except json.JSONDecodeError as e:
                        print(f"⚠️  Warning: Invalid JSON in IMG_GEN on line {j+1}: {e}")
                        continue
            
            # Only include images that have IMG_GEN tags
            if prompt:
                images.append({
                    'path': full_path,
                    'prompt': prompt,
                    'size': size,
                    'line_number': i + 1
                })
    
    return images

def generate_image(client: OpenAI, prompt: str, output_path: str, size: str = "1024x1024") -> bool:
    """Generate an image using OpenAI DALL-E and save it."""
    try:
        print(f"🎨 Generating {output_path}...")
        print(f"📝 Prompt: {prompt}")
        print(f"📐 Size: {size}")
        
        # Enhance prompt for presentation context
        enhanced_prompt = f"{prompt}, professional presentation style, clean background, high quality, suitable for slides"
        
        response = client.images.generate(
            model="dall-e-3",
            prompt=enhanced_prompt,
            size=size,
            quality="standard",
            n=1,
        )
        
        # Download the image
        image_url = response.data[0].url
        img_response = requests.get(image_url)
        img_response.raise_for_status()
        
        # Save the image at the exact path specified
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'wb') as f:
            f.write(img_response.content)
        
        print(f"  ✅ Saved to {output_file}")
        return True
        
    except Exception as e:
        print(f"  ❌ Error generating {output_path}: {e}")
        return False

def main():
    """Main function to generate images for presentation."""
    # Parse command line arguments
    target_path = None
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            if arg.startswith('--target='):
                target_path = arg.split('=', 1)[1]
            elif arg in ['--help', '-h']:
                print(__doc__)
                return
    
    # Check for OpenAI API key
    if not os.getenv('OPENAI_API_KEY'):
        print("❌ Error: OPENAI_API_KEY environment variable not set")
        print("Please set your OpenAI API key:")
        print("export OPENAI_API_KEY='your-api-key-here'")
        return
    
    # Initialize OpenAI client
    client = OpenAI()
    
    # Read markdown file
    markdown_path = Path(MARKDOWN_FILE)
    if not markdown_path.exists():
        print(f"❌ Error: {MARKDOWN_FILE} not found")
        return
    
    with open(markdown_path, 'r', encoding='utf-8') as f:
        markdown_content = f.read()
    
    # Extract images with IMG_GEN tags
    all_images = extract_images_with_prompts(markdown_content)
    
    if not all_images:
        print("No images with IMG_GEN tags found in markdown file")
        print("Add IMG_GEN tags like: <!-- IMG_GEN: {\"prompt\": \"your prompt here\"} -->")
        return
    
    # Filter by target if specified
    if target_path:
        images = [img for img in all_images if img['path'] == target_path]
        if not images:
            print(f"❌ Error: Target path '{target_path}' not found.")
            print(f"Available paths:")
            for img in all_images:
                print(f"  - {img['path']} (line {img['line_number']})")
            return
        print(f"🎯 Targeting specific image: {target_path}")
    else:
        images = all_images
        print(f"Found {len(images)} images with IMG_GEN tags:")
        for img in images:
            print(f"  - {img['path']} (line {img['line_number']})")
    
    print()
    
    # Generate images
    success_count = 0
    for img in images:
        success = generate_image(
            client, 
            img['prompt'], 
            img['path'], 
            img['size']
        )
        if success:
            success_count += 1
        print()
    
    if target_path:
        if success_count > 0:
            print(f"✅ Successfully regenerated {target_path}")
        else:
            print(f"❌ Failed to regenerate {target_path}")
    else:
        print(f"✅ Successfully generated {success_count}/{len(images)} images")

if __name__ == "__main__":
    main() 