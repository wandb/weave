#!/bin/bash

# Apply the patch
git apply my_patch.patch
PATCH_APPLIED=$?

# Run your tests here
# Replace `your_test_command` with the actual command to run your tests
cd weave 
pytest "tests/test_hypothesis.py::test_join2"
TEST_RESULT=$?
cd ..

if [ $PATCH_APPLIED -eq 0 ]; then
  # If the patch was applied successfully, revert it
  git apply -R my_patch.patch
fi

# Return the test result
exit $TEST_RESULT
