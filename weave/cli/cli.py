"""Command line interface for Weave."""

import weave
import click
import litellm

@click.group()
def cli():
    """Weave - A toolkit for building composable interactive data driven applications."""
    weave.init("cli", settings={"print_call_link": False})
    pass

@cli.command()
@click.option('--prompt', required=True, help='The prompt to send to the model')
@click.option('--model', default='gpt-3.5-turbo', help='The model to use for completion')
@click.option('--temperature', default=0.7, help='Temperature for completion')
@click.option('--max-tokens', default=1000, help='Maximum number of tokens to generate')
def llm(prompt, model, temperature, max_tokens):
    """Generate text completions using various LLM models via litellm."""
    try:
        response = litellm.completion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens
        )
        click.echo(response.choices[0].message.content)
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)

@cli.command()
def complete():
    """Complete a command."""
    click.echo('Completing...')

if __name__ == '__main__':
    cli() 