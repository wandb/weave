{
    "targets": [
        {
            "target_name": "tree_sitter_weave_binding",
            "include_dirs": ["src"],
            "sources": ["src/parser.c", "src/scanner.c"],
            "cflags_c": [
                "-std=c99",
            ],
        }
    ]
}
