import os
from weave.content_types.mime_types import _current_mime_detector 
from weave.content_types.mime_types import *
from weave.content_types.content import *
# --- Example Usage (Illustrative) ---
def main_content_test():
    try:
        # This import is for the test to know which detector is active.
        # It assumes a certain package structure.
        from weave.content_types.mime_types import _current_mime_detector
        print(f"--- Testing with MIME Detector: {type(_current_mime_detector).__name__} ---")
    except ImportError:
        print("--- Testing (MIME detector type not printed due to potential import context issues when run standalone) ---")


    temp_dir = "./temp_content_files_normalized" 
    os.makedirs(temp_dir, exist_ok=True)

    # Create a file with non-UTF-8 encoding (Latin-1 with special chars)
    latin1_filename = "latin1_doc.txt"
    latin1_content_str = "Hällö Wörld with Latin-1 chars: åäöü"
    latin1_bytes = latin1_content_str.encode('latin-1')
    with open(os.path.join(temp_dir, latin1_filename), "wb") as f:
        f.write(latin1_bytes)

    # Create a UTF-8 file with BOM
    utf8_bom_filename = "utf8_bom_doc.txt"
    utf8_bom_content_str = "Hello with BOM"
    # Prepend BOM: \xef\xbb\xbf
    utf8_bom_bytes = b'\xef\xbb\xbf' + utf8_bom_content_str.encode('utf-8')
    with open(os.path.join(temp_dir, utf8_bom_filename), "wb") as f:
        f.write(utf8_bom_bytes)

    # Create a plain UTF-8 file
    utf8_filename = "utf8_doc.txt"
    utf8_content_str = "Hello UTF-8 World"
    with open(os.path.join(temp_dir, utf8_filename), "w", encoding="utf-8") as f:
        f.write(utf8_content_str)


    print(f"\n--- Testing PlainText with Latin-1 file ({latin1_filename}) ---")
    latin1_path = os.path.join(temp_dir, latin1_filename)
    try:
        pt_latin1_obj = PlainText.from_path(latin1_path)
        print(f"Loaded: {pt_latin1_obj}")
        # Verify data is now UTF-8
        redecoded_content = pt_latin1_obj.data.decode('utf-8')
        assert redecoded_content == latin1_content_str 
        print(f"Original Latin-1 string: '{latin1_content_str}'")
        print(f"Stored as UTF-8, re-decoded: '{redecoded_content}' - Content MATCHES.")
        assert pt_latin1_obj.metadata['size'] == len(latin1_content_str.encode('utf-8'))
        pt_latin1_obj.export_metadata(os.path.join(temp_dir, "latin1_doc_meta.json"))
    except Exception as e: 
        print(f"PlainText (Latin-1) Error: {e}")
        import traceback
        traceback.print_exc()

    print(f"\n--- Testing PlainText with UTF-8 BOM file ({utf8_bom_filename}) ---")
    utf8_bom_path = os.path.join(temp_dir, utf8_bom_filename)
    try:
        pt_utf8_bom_obj = PlainText.from_path(utf8_bom_path)
        print(f"Loaded: {pt_utf8_bom_obj}")
        # Verify data is now UTF-8 and BOM is stripped
        redecoded_content_bom = pt_utf8_bom_obj.data.decode('utf-8')
        assert redecoded_content_bom == utf8_bom_content_str
        print(f"Original string (post-BOM): '{utf8_bom_content_str}'")
        print(f"Stored as UTF-8 (BOM stripped), re-decoded: '{redecoded_content_bom}' - Content MATCHES.")
        # Size should be of the string without BOM, encoded in UTF-8
        assert len(pt_utf8_bom_obj.data) == len(utf8_bom_content_str.encode('utf-8'))
        pt_utf8_bom_obj.export_metadata(os.path.join(temp_dir, "utf8_bom_doc_meta.json"))

    except Exception as e: print(f"PlainText (UTF-8 BOM) Error: {e}")

    print(f"\n--- Testing PlainText with regular UTF-8 file ({utf8_filename}) ---")
    utf8_path = os.path.join(temp_dir, utf8_filename)
    try:
        pt_utf8_obj = PlainText.from_path(utf8_path)
        print(f"Loaded: {pt_utf8_obj}")
        redecoded_content_utf8 = pt_utf8_obj.data.decode('utf-8')
        assert redecoded_content_utf8 == utf8_content_str
        print(f"Original UTF-8 string: '{utf8_content_str}'")
        print(f"Stored and re-decoded: '{redecoded_content_utf8}' - Content MATCHES.")
        pt_utf8_obj.export_metadata(os.path.join(temp_dir, "utf8_doc_meta.json"))
    except Exception as e: print(f"PlainText (UTF-8) Error: {e}")

    print("\n--- Testing Json from_data (string input) ---")
    json_string_data = '{"status": "ok", "message": "你好世界"}' # Contains non-ASCII
    try:
        json_from_str_obj = Json.from_data(json_string_data, mime_type="application/json")
        print(f"Loaded: {json_from_str_obj}")
        # from_data (via __init__ -> try_decode) encodes string to UTF-8 bytes
        expected_bytes = json_string_data.encode('utf-8')
        assert json_from_str_obj.data == expected_bytes
        print(f"String input content matches stored UTF-8 bytes.")
        assert json_from_str_obj.get_content_as_string() == json_string_data
        json_from_str_obj.export_metadata(os.path.join(temp_dir, "json_from_string_meta.json"))
    except Exception as e: print(f"Json (from_data string) Error: {e}")


# --- Example Usage (Illustrative) ---
def main_media_test():
    temp_dir = "./temp_media_files"
    os.makedirs(temp_dir, exist_ok=True)

    # Create dummy files with various extensions
    files_to_create = {
        "document.pdf": b"%PDF-1.4 dummy content",
        "data.json": b'{"key": "value", "numbers": [1, 2, 3]}',
        "config.yaml": b"setting: true\nvalues:\n  - item1\n  - item2",
        "report.csv": b"id,name,value\n1,test,100\n2,another,200",
        "notes.md": b"# My Markdown\n\nThis is a test.\n\n* item 1\n* item 2",
        "script.py": b"#!/usr/bin/env python\nprint('Hello Python!')\n# Some comments",
        "app.js": b"// JavaScript example\nconsole.log('Hello JavaScript!');\nconst x = 10;",
        "module.ts": b"// TypeScript example\ninterface User { name: string; id: number; }\nconst user: User = { name: 'TS', id: 1 };",
        "archive.tar.gz": b"dummy tarball data", # A type not explicitly handled by a class
        "audio_test.mp3": b"MP3 audio data placeholder",
        "plain.txt": b"Simple text file."
    }
    for filename, content in files_to_create.items():
        with open(os.path.join(temp_dir, filename), "wb") as f:
            f.write(content)

    print(f"--- Testing with MIME Detector: {type(_current_mime_detector).__name__} ---")

    test_cases = [
        (Pdf, "document.pdf", "application/pdf"),
        (Json, "data.json", "application/json"),
        (Yaml, "config.yaml", ["application/yaml", "text/yaml"]), # mimetypes can vary
        (Csv, "report.csv", "text/csv"),
        (Markdown, "notes.md", ["text/markdown", "text/x-markdown"]),
        (Python, "script.py", ["text/x-python", "application/x-python-code", "text/python"]),
        (JavaScript, "app.js", ["application/javascript", "text/javascript"]),
        (TypeScript, "module.ts", ["text/x-typescript", "application/typescript", "text/typescript"]), # Our added types should take precedence
        (Audio, "audio_test.mp3", "audio/mpeg"),
        (PlainText, "plain.txt", "text/plain")
    ]

    for media_cls, filename, expected_mime in test_cases:
        print(f"\n--- Testing {media_cls.__name__} with {filename} ---")
        file_path = os.path.join(temp_dir, filename)
        try:
            media_obj = media_cls.from_path(file_path)
            print(f"Loaded: {media_obj}")
            print(f"Guessed MIME: {media_obj.mime_type}")

            if isinstance(expected_mime, list):
                assert media_obj.mime_type in expected_mime, f"Expected MIME in {expected_mime}, got {media_obj.mime_type}"
            else:
                assert media_obj.mime_type == expected_mime, f"Expected MIME {expected_mime}, got {media_obj.mime_type}"

            if hasattr(media_obj, "get_content_as_string") and media_cls not in [Audio, Video, Image, Pdf]:
                 print(f"Content Preview: {media_obj.get_content_as_string()[:100]}...")

            exported_path = media_obj.export(os.path.join(temp_dir, f"exported_{filename.split('.')[0]}"))
            print(f"Exported to: {exported_path}")
            assert os.path.exists(exported_path)

        except Exception as e:
            print(f"Error for {filename}: {e}")
            # import traceback
            # traceback.print_exc() # For more detailed debugging if needed

    print("\n--- Testing Unhandled Type (expect ValueError on class instantiation if strict) ---")
    unhandled_path = os.path.join(temp_dir, "archive.tar.gz")
    guessed_unhandled_mime = guess_mime_type_from_path(unhandled_path)
    print(f"Guessed MIME for '{unhandled_path}': {guessed_unhandled_mime}")
    # No class directly handles .tar.gz, so trying to load with a specific class would fail
    # unless its MIME type was added to that class's supported list.
    try:
        # Example: Trying to load a tar.gz as PlainText (will fail due to MIME mismatch)
        txt_obj = PlainText.from_path(unhandled_path)
        print(f"Incorrectly loaded unhandled type as PlainText: {txt_obj}") # Should not reach here
    except ValueError as e:
        print(f"Correctly caught ValueError for unhandled type: {e}")

    print("\n--- Testing from_data ---")
    try:
        json_data_str = '{"message": "hello from data"}'
        # For from_data, we must provide the mime_type
        json_obj_data = Json.from_data(json_data_str, mime_type="application/json")
        print(f"Loaded from data: {json_obj_data}")
        print(f"Content: {json_obj_data.get_content_as_string()}")
        assert json_obj_data.mime_type == "application/json"
    except Exception as e:
        print(f"Error in from_data test: {e}")


if __name__ == "__main__":
    # Need to import _current_mime_detector for the test to show which detector is active
    from weave.content_types.mime_types import _current_mime_detector # Relative import for when running as a module
    main_media_test()
    main_content_test()
