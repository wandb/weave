"""Tests to verify scorer documentation and examples."""
import pytest
import inspect
import doctest
from typing import get_type_hints
import weave
from weave.scorers import (
    BLEUScorer,
    RougeScorer,
    CoherenceScorer,
    ContextRelevanceScorer,
    RobustnessScorer,
    ToxicScorer,
    GenderRaceBiasScorer,
)


def get_all_scorers():
    """Get all scorer classes from the weave.scorers module."""
    return [
        BLEUScorer,
        RougeScorer,
        CoherenceScorer,
        ContextRelevanceScorer,
        RobustnessScorer,
        ToxicScorer,
        GenderRaceBiasScorer,
    ]


@pytest.mark.parametrize("scorer_class", get_all_scorers())
def test_docstring_exists(scorer_class):
    """Test that all scorer classes have proper docstrings."""
    assert scorer_class.__doc__ is not None, f"{scorer_class.__name__} missing docstring"
    
    # Check docstring content
    doc = scorer_class.__doc__
    assert len(doc.strip()) > 0, f"{scorer_class.__name__} has empty docstring"
    
    # Check for key documentation sections
    required_sections = ["Parameters", "Returns", "Examples"]
    doc_lower = doc.lower()
    for section in required_sections:
        assert section.lower() in doc_lower, (
            f"{scorer_class.__name__} docstring missing '{section}' section"
        )


@pytest.mark.parametrize("scorer_class", get_all_scorers())
def test_doctest_examples(scorer_class):
    """Test that docstring examples are valid and run successfully."""
    try:
        # Run doctests
        doctest.run_docstring_examples(
            scorer_class.__doc__,
            {"scorer_class": scorer_class},
            name=scorer_class.__name__,
            verbose=True
        )
    except Exception as e:
        pytest.fail(
            f"Doctests failed for {scorer_class.__name__}: {str(e)}"
        )


@pytest.mark.parametrize("scorer_class", get_all_scorers())
def test_method_documentation(scorer_class):
    """Test that all public methods have proper documentation."""
    for name, method in inspect.getmembers(scorer_class, inspect.isfunction):
        if not name.startswith('_'):  # Public methods only
            assert method.__doc__ is not None, (
                f"{scorer_class.__name__}.{name} missing docstring"
            )
            
            # Check docstring content
            doc = method.__doc__
            assert len(doc.strip()) > 0, (
                f"{scorer_class.__name__}.{name} has empty docstring"
            )


@pytest.mark.parametrize("scorer_class", get_all_scorers())
def test_type_hints(scorer_class):
    """Test that all methods have proper type hints."""
    for name, method in inspect.getmembers(scorer_class, inspect.isfunction):
        if not name.startswith('_'):  # Public methods only
            hints = get_type_hints(method)
            assert len(hints) > 0, (
                f"{scorer_class.__name__}.{name} missing type hints"
            )
            
            # Check return type hint
            assert 'return' in hints, (
                f"{scorer_class.__name__}.{name} missing return type hint"
            )


@pytest.mark.parametrize("scorer_class", get_all_scorers())
def test_error_messages(scorer_class):
    """Test that error messages are helpful and well-documented."""
    scorer = scorer_class()
    
    # Test with invalid inputs
    invalid_inputs = [
        None,
        "",
        123,
        ["not", "a", "string"],
        {"not": "valid"},
    ]
    
    for invalid_input in invalid_inputs:
        try:
            if hasattr(scorer, 'score'):
                scorer.score(invalid_input, invalid_input)
            pytest.fail(
                f"{scorer_class.__name__} didn't raise error for invalid input: {invalid_input}"
            )
        except Exception as e:
            # Verify error message is helpful
            assert str(e), "Empty error message"
            assert len(str(e)) > 10, "Error message too short"
            assert str(e) != str(type(e)), "Generic error message"


@pytest.mark.parametrize("scorer_class", get_all_scorers())
def test_output_format(scorer_class):
    """Test that scorer outputs match their documented format."""
    scorer = scorer_class()
    
    # Get documented output format from docstring
    doc = scorer.__doc__
    assert "Returns:" in doc, f"{scorer_class.__name__} missing Returns section in docstring"
    
    # Test with valid input
    valid_input = "This is a test input."
    valid_output = "This is a test output."
    
    try:
        if hasattr(scorer, 'score'):
            result = scorer.score(valid_input, valid_output)
            
            # Verify result matches documented format
            assert isinstance(result, dict), "Result should be a dictionary"
            
            # Check for required fields based on docstring
            returns_section = doc.split("Returns:")[1].split("\n")[1:]
            for line in returns_section:
                if ":" in line:
                    field = line.split(":")[0].strip()
                    if field:
                        assert field in result, (
                            f"Missing documented field '{field}' in result"
                        )
    except Exception as e:
        if "not implemented" not in str(e).lower():
            pytest.fail(f"Error testing output format: {str(e)}")


def test_readme_examples():
    """Test that examples in the README.md file work correctly."""
    import os
    
    readme_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "README.md"
    )
    
    if os.path.exists(readme_path):
        with open(readme_path, 'r') as f:
            content = f.read()
            
        # Extract Python code blocks
        code_blocks = []
        in_block = False
        current_block = []
        
        for line in content.split('\n'):
            if line.startswith('```python'):
                in_block = True
            elif line.startswith('```') and in_block:
                in_block = False
                if current_block:
                    code_blocks.append('\n'.join(current_block))
                    current_block = []
            elif in_block:
                current_block.append(line)
        
        # Test each code block
        for i, code in enumerate(code_blocks):
            try:
                # Add necessary imports
                setup_code = """
                import weave
                from weave.scorers import *
                """
                
                # Execute the code
                exec(setup_code + code)
            except Exception as e:
                pytest.fail(
                    f"README example #{i+1} failed: {str(e)}\nCode:\n{code}"
                )