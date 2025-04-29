# Video Type Handler Tests

These tests verify the functionality of the Video type handler defined in `weave/type_handlers/Video/video.py`.

## Test Files

- **video_test.py**: Core tests for Video type handler, covering publishing, serialization/deserialization, and using videos in various contexts (properties, tables, operation inputs/outputs).
- **video_edge_cases_test.py**: Tests for edge cases and additional functionality.
- **video_saving_script.py**: Script to test saving multiple videos in succession.
- **registration_test.py**: Tests to ensure proper registration of the type handler.

## Test Coverage

The tests cover:

1. **Object Publishing**
   - Direct publishing of VideoClip objects
   - Publishing as a property of a Weave Object
   - Using as a cell in a table/dataset

2. **Call Input/Output**
   - Using as input parameters
   - Using as function return values
   - Using as part of composite return values

3. **Format Support**
   - Testing all supported formats (gif, mp4, webm)
   - Testing unsupported formats (error handling)

4. **Edge Cases**
   - No format attribute
   - Video files without extensions
   - Multiple video formats in the same session

## Test Data

The tests generate their own test data using ColorClip from moviepy. For file-based tests, the tests also use `test_video.mp4` if available in the test directory.