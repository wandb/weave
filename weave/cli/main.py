"""Main Weave CLI entry point."""

import click


@click.group()
@click.version_option()
def cli():
    """Weave CLI - Tools for working with Weave tracing and evaluation."""
    pass


@cli.command()
@click.option('--name', default='World', help='Name to greet')
@click.option('--count', default=1, help='Number of times to greet')
def hello(name, count):
    """Print a friendly hello message.

    Example:
        weave hello
        weave hello --name Alice
        weave hello --name Bob --count 3
    """
    for _ in range(count):
        click.echo(f'Hello, {name}!')


if __name__ == '__main__':
    cli()
