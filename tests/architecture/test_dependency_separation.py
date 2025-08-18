"""Test architectural improvements for dependency separation between client and server.

This test ensures that client-side code (weave/trace/) can be imported without
requiring server-side dependencies like clickhouse_connect. This is achieved by
moving shared exceptions to a common module.
"""

import unittest
import os
import sys


class TestExceptionRefactor(unittest.TestCase):
    """Test that the exception refactoring allows imports without heavy dependencies."""

    def test_exception_module_exists(self):
        """Test that the new exceptions module was created."""
        exceptions_path = os.path.join(
            os.path.dirname(__file__), '..', '..', 'weave', 'trace', 'exceptions.py'
        )
        self.assertTrue(os.path.exists(exceptions_path), 
                       "weave/trace/exceptions.py should exist")
        
        # Check the content
        with open(exceptions_path, 'r') as f:
            content = f.read()
        
        self.assertIn('class ObjectDeletedError', content,
                     "ObjectDeletedError should be defined in exceptions.py")
        self.assertIn('deleted_at', content,
                     "ObjectDeletedError should have deleted_at attribute")

    def test_client_imports_dont_require_clickhouse(self):
        """Test that client code can be imported without clickhouse_connect."""
        # This test will pass because we moved ObjectDeletedError
        # If it was still in trace_server/errors.py, this would fail without clickhouse
        try:
            from weave.trace.exceptions import ObjectDeletedError
            from weave.trace import refs
            from weave.trace import vals
            success = True
        except ImportError as e:
            if 'clickhouse' in str(e):
                success = False
                error_msg = str(e)
            else:
                raise
        
        self.assertTrue(success, 
                       "Client imports should not require clickhouse_connect")

    def test_exception_is_properly_imported(self):
        """Test that both client and server can use the exception."""
        # Import from the new location
        from weave.trace.exceptions import ObjectDeletedError
        
        # Create an instance to verify it works
        import datetime
        exc = ObjectDeletedError("Test object deleted", datetime.datetime.now())
        
        self.assertIsInstance(exc, Exception)
        self.assertTrue(hasattr(exc, 'deleted_at'))
        self.assertIn("Test object deleted", str(exc))

    def test_refs_uses_new_import(self):
        """Test that refs.py imports from the new location."""
        refs_path = os.path.join(
            os.path.dirname(__file__), '..', '..', 'weave', 'trace', 'refs.py'
        )
        
        with open(refs_path, 'r') as f:
            content = f.read()
        
        # Should import from trace.exceptions, not trace_server.errors
        self.assertIn('from weave.trace.exceptions import ObjectDeletedError', content,
                     "refs.py should import ObjectDeletedError from trace.exceptions")
        self.assertNotIn('from weave.trace_server.errors import ObjectDeletedError', content,
                        "refs.py should NOT import ObjectDeletedError from trace_server.errors")

    def test_vals_uses_new_import(self):
        """Test that vals.py imports from the new location."""
        vals_path = os.path.join(
            os.path.dirname(__file__), '..', '..', 'weave', 'trace', 'vals.py'
        )
        
        with open(vals_path, 'r') as f:
            content = f.read()
        
        # Should import from trace.exceptions, not trace_server.errors
        self.assertIn('from weave.trace.exceptions import ObjectDeletedError', content,
                     "vals.py should import ObjectDeletedError from trace.exceptions")
        self.assertNotIn('from weave.trace_server.errors import ObjectDeletedError', content,
                        "vals.py should NOT import ObjectDeletedError from trace_server.errors")

    def test_server_errors_imports_from_common(self):
        """Test that server errors.py imports from the common location."""
        errors_path = os.path.join(
            os.path.dirname(__file__), '..', '..', 'weave', 'trace_server', 'errors.py'
        )
        
        with open(errors_path, 'r') as f:
            content = f.read()
        
        # Should import from trace.exceptions
        self.assertIn('from weave.trace.exceptions import ObjectDeletedError', content,
                     "errors.py should import ObjectDeletedError from trace.exceptions")
        
        # Should not define it locally anymore
        self.assertNotIn('class ObjectDeletedError(Error):', content,
                        "errors.py should NOT define ObjectDeletedError locally")


if __name__ == '__main__':
    unittest.main()
