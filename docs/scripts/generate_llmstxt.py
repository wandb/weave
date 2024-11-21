from pathlib import Path
import yaml
import re
from collections import defaultdict
from typing import Callable, Dict, List, Tuple
import json

# Type for a rule that determines if a file belongs in a section
SectionRule = Callable[[Path], bool]

def is_optional_from_frontmatter(file_path: Path) -> bool:
    """Check if a file is marked as optional in its frontmatter."""
    try:
        text = file_path.read_text()
        if not text.startswith('---\n'):
            return False
            
        parts = re.split(r"---\n", text, maxsplit=2)
        if len(parts) >= 3:
            try:
                frontmatter = yaml.safe_load(parts[1])
                return frontmatter and frontmatter.get("optional", False)
            except yaml.YAMLError:
                print(f"Warning: Invalid YAML frontmatter in {file_path}")
                return False
    except Exception as e:
        print(f"Warning: Error reading frontmatter from {file_path}: {str(e)}")
    return False

def is_optional_from_category(file_path: Path) -> bool:
    """Check if any parent directory is marked as optional in _category_ files."""
    current_dir = file_path.parent
    
    # Keep checking parent directories until we reach the root
    while current_dir.name:  # Stop when we reach the root (empty name)
        # Check for both .yml and .json category files
        yml_category = current_dir / '_category_.yml'
        json_category = current_dir / '_category_.json'
        
        try:
            if yml_category.exists():
                with yml_category.open() as f:
                    category_data = yaml.safe_load(f)
                    if category_data.get("optional", False):
                        return True
            elif json_category.exists():
                with json_category.open() as f:
                    category_data = json.loads(f.read())
                    is_optional = category_data.get("customProps", {}).get("optional", False)
                    if is_optional:
                        return True
        except Exception as e:
            print(f"Error reading category file for {current_dir}: {str(e)}")
        
        # Move up to parent directory
        current_dir = current_dir.parent
    
    return False

def create_section_rules() -> Dict[str, List[SectionRule]]:
    """Create the rules for each section. Earlier rules take precedence."""
    rules = {
        "Optional": [
            lambda p: ('integrations' in str(p) or 
                      'integration' in p.stem.lower()),
            lambda p: 'gen_notebooks' in str(p),
            lambda p: 'examples' in str(p),
            lambda p: p.name.startswith('example-'),
            lambda p: p.name.startswith('api-'),
            lambda p: 'reference' in str(p), 
            lambda p: '/api/' in str(p),
            lambda p: is_optional_from_category(p) or is_optional_from_frontmatter(p)
        ],
        "Docs": [
            lambda p: p.name in ['introduction.md', 'quickstart.md'],
            lambda p: '/guides/' in str(p),
            lambda p: p.parent == Path('.') 
        ]
    }
    return rules

def get_section(file_path: Path, section_rules: Dict[str, List[SectionRule]]) -> str:
    """Determine which section a file belongs to based on the rules."""
    # Check all rules in order of precedence
    for section, rules in section_rules.items():
        if any(rule(file_path) for rule in rules):
            return section
    return "Docs"  
def get_display_title(file_path: Path, frontmatter_title: str | None = None) -> str:
    """Get the display title for a file, handling index files specially."""
    if file_path.stem == 'index':
        if is_optional_from_category(file_path):
            return None 
        return file_path.parent.name
    return frontmatter_title or file_path.stem

def generate_llms_txt(
    directory: Path,
    output_file: Path,
    title: str,
    description: str,
    github_base_url: str,
    section_rules: Dict[str, List[SectionRule]],
    section_order: List[str]
):
    # Start with title, description, and an empty info section
    content = [
        f"# {title}",
        f"> {description}",
        "",
        "This file contains documentation links for Weave.",  
        ""
    ]

    sections = {section: [] for section in section_rules.keys()}
    def should_skip(path: Path) -> bool:
        """Check if a file should be skipped based on its path."""
        if any(part.startswith('.') for part in path.parts):
            return True
        
        skip_dirs = {
            'ipynb_checkpoints',
            'node_modules',
            '__pycache__',
        }
        
        return any(part in skip_dirs for part in path.parts)
    
    for md_file in directory.rglob('*.[mM][dD]*'):
        if should_skip(md_file.relative_to(directory)) or md_file.suffix == '.ipynb':
            continue
            
        try:
            text = md_file.read_text()
            frontmatter_title = None
            description = ''
            if text.startswith('---\n'):
                parts = re.split(r"---\n", text, maxsplit=2)
                if len(parts) >= 3:
                    try:
                        frontmatter = yaml.safe_load(parts[1])
                        if frontmatter:
                            frontmatter_title = frontmatter.get('title')
                            description = frontmatter.get('description', '')
                    except yaml.YAMLError:
                            print(f"Warning: Invalid YAML frontmatter in {md_file}")
            
            relative_path = md_file.relative_to(directory)
            
            display_title = get_display_title(relative_path, frontmatter_title)
            if display_title is None: 
                continue
                
            url_path = str(relative_path).replace('\\', '/')
            
            entry = f"- [{display_title}]({github_base_url}/{url_path}): {description}"
            
            section = get_section(md_file, section_rules)
            if section == "Optional":
                if relative_path.stem == 'index':
                    continue
            sections[section].append((relative_path.parent == Path('.'), entry))
            
        except Exception as e:
            print(f"Warning: Error processing {md_file}: {str(e)}")
            continue
    
    for section_name in section_order:
        if sections[section_name]:
            content.append(f"## {section_name}")
            content.append("")  # Single blank line after section header
            sorted_entries = sorted(sections[section_name], key=lambda x: (not x[0], x[1]))
            content.extend(entry[1] for entry in sorted_entries)
            content.append("")  # Single blank line after section entries
    
    # Remove any trailing blank lines
    while content and not content[-1]:
        content.pop()
        
    output_file.write_text('\n'.join(content))

# Usage example
if __name__ == "__main__":
    docs_dir = Path("./docs")
    output_file = Path("./static/llms.txt")
    title = "Weave"
    description = "Weave is a lightweight toolkit for tracking and evaluating LLM applications, built by Weights & Biases."
    github_base_url = "https://raw.githubusercontent.com/wandb/weave/master/docs/docs"
    section_rules = create_section_rules()
    section_order = ["Docs",  "Optional"]
    
    generate_llms_txt(
        directory=docs_dir,
        output_file=output_file,
        title=title,
        description=description,
        github_base_url=github_base_url,
        section_rules=section_rules,
        section_order=section_order
    )