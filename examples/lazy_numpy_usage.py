"""Example demonstrating how to use lazy NumPy import with type checking support."""

from typing import TYPE_CHECKING, List

# Import pattern for lazy NumPy loading with type checking support
if TYPE_CHECKING:
    # During type checking, import the actual module for proper type hints
    import numpy as np
else:
    # At runtime, use lazy import to defer loading
    from weave.utils.lazy_import import lazy_import_numpy
    np = lazy_import_numpy()


def process_data(values: List[float]) -> 'np.ndarray':
    """Process a list of values into a NumPy array.
    
    This function demonstrates that type checkers understand 'np.ndarray'
    even though NumPy is lazily loaded at runtime.
    
    Args:
        values: List of float values to process
        
    Returns:
        A NumPy array containing the processed values
    """
    # NumPy will only be imported when this line is executed
    array = np.array(values)
    
    # Apply some NumPy operations
    normalized = (array - np.mean(array)) / np.std(array)
    
    return normalized


def calculate_statistics(data: 'np.ndarray') -> dict:
    """Calculate statistics for a NumPy array.
    
    Args:
        data: Input NumPy array
        
    Returns:
        Dictionary containing statistics
    """
    return {
        'mean': float(np.mean(data)),
        'std': float(np.std(data)),
        'min': float(np.min(data)),
        'max': float(np.max(data)),
        'median': float(np.median(data))
    }


# Alternative pattern using the get_numpy function
from weave.utils.lazy_import import get_numpy

def alternative_process_data(values: List[float]):
    """Alternative approach using get_numpy for inline lazy loading."""
    # Import NumPy only when needed
    np = get_numpy()
    
    array = np.array(values)
    return np.sqrt(np.abs(array))


if __name__ == "__main__":
    # Demonstrate that NumPy is not imported until needed
    import sys
    
    print("Before using NumPy functions:")
    print(f"NumPy imported: {'numpy' in sys.modules}")
    
    # This will trigger the NumPy import
    result = process_data([1.0, 2.0, 3.0, 4.0, 5.0])
    
    print("\nAfter using NumPy functions:")
    print(f"NumPy imported: {'numpy' in sys.modules}")
    print(f"Result: {result}")
    
    # Calculate statistics
    stats = calculate_statistics(result)
    print(f"Statistics: {stats}")
    
    # Test alternative approach
    alt_result = alternative_process_data([1.0, 4.0, 9.0, 16.0])
    print(f"Alternative result: {alt_result}")