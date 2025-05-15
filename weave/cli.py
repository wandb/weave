"""Command line interface for Weave."""

import click

@click.group()
def cli():
    """Weave - A toolkit for building composable interactive data driven applications."""
    pass

@cli.command()
@click.option('--name', default='World', help='Who to greet')
def hello(name):
    """Say hello to someone."""
    click.echo(f'Hello {name}! Welcome to Weave!')

if __name__ == '__main__':
    cli() 