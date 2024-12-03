import sys
import os
from openai import OpenAI
import weave

def read_file(file_path):
    """Reads the content of a file."""
    try:
        with open(file_path, 'r') as file:
            content = file.read()
        return content
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
        sys.exit(1)

def split_content(content):
    """Splits the file content into frontmatter and markdown content."""
    parts = content.split('---')
    '''
    if len(parts) < 3:
        print("Error: File does not have the expected frontmatter and content structure.")
        sys.exit(1)
    '''
    return parts

def create_openai_client():
    """Creates and returns an OpenAI client."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable is not set.")
        sys.exit(1)
    return OpenAI(api_key=api_key)

def generate_prompt():
    """Returns the prompt for GPT editing."""
    return """Given a page comprised of the following markdown, rewrite the text for clarity, brevity, and adherence to the Google Technical Documentation style guide. Do not remove things like the import statements at the top of the markdown file as that is used to tell our markdown processor that it needs to import certain libraries to render the content correctly. Be sure to leave markup intact, as well, such as <TabItem> and <Tab> tags. Avoid the use of future tense and the word "will," for example do not say "W&B will do x, y, or z." Avoid the use of Latin abbreviations such as "i.e." and "e.g." Do not wrap the output in triple tics or label it as markdown, it will be parsed as markdown already. Avoid any use of passive voice, such as the phrases "be added" or "are stored." Do not use soft language like "may," "should," "might," and "maybe." Avoid use of problematic or non-inclusive language, for example do not describe things as "disabled" or "enabled" but rather "turned off" or "turned on," and don't say things are "blacklisted" or "whitelisted," but rather "allowed" or "not allowed." Avoid the use of first-person pronouns such as "I," "my," and "we." Use the Oxford comma when appropriate. Commas and periods must go inside quotation marks. Headings must use sentence-style capitalization.
"""

@weave.op()
def edit_content(client, prompt, content):
    """Uses OpenAI GPT to rewrite the markdown content."""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": content},
        ]
    )
    return response.choices[0].message.content

def write_file(file_path, content):
    """Writes content back to a file."""
    with open(file_path, 'w') as file:
        file.write(content)

def main():
    
    weave.init('gpt-editor')

    if len(sys.argv) < 2:
        print("Usage: python gpt-editor.py <path/to/markdown-file.md>")
        sys.exit(1)

    file_path = sys.argv[1]
    original_content = read_file(file_path)

    client = create_openai_client()
    prompt = generate_prompt()
    new_content = edit_content(client, prompt, original_content)

    print("OLD CONTENT:")
    print(markdown_content)
    print("NEW CONTENT:")
    print(new_content)

    output_content = f"---{frontmatter}---\n{new_content}"
    write_file(file_path, output_content)

if __name__ == "__main__":
    main()
