import pytest

from weave.legacy.weave.util import relpath_no_syscalls


@pytest.mark.parametrize(
    "target_path, start_path, current_working_directory, expected",
    [
        # First batch
        (
            "/home/user/documents/report.txt",
            "/home/user/projects",
            "/home/user",
            "../documents/report.txt",
        ),
        ("reports/summary.pdf", "downloads", "/home/user", "../reports/summary.pdf"),
        ("/home/user/documents", "/home/user/documents", "/home/user", "."),
        # Second batch (mixed cases)
        (
            "/home/user/documents/report.txt",
            "projects",
            "/home/user",
            "../documents/report.txt",
        ),
        ("/var/log", "downloads", "/home/user", "../../../var/log"),
        (
            "projects/subproject/code.py",
            "/usr/local",
            "/home/user",
            "../../home/user/projects/subproject/code.py",
        ),
        # Edge cases
        ("/", "/", "/", "."),
        ("/", "subfolder", "/home/user", "../../.."),
        ("/home/user/subfolder", ".", "/home/user", "subfolder"),
        ("/home/user/subfolder", "..", "/home/user/subfolder", "subfolder"),
        (
            "/home/user/documents/file.txt",
            "../../../documents",
            "/home/user/projects/subproject",
            "../user/documents/file.txt",
        ),
        (
            "/home/user/documents/file.txt",
            "../../documents",
            "/home/user/projects/subproject",
            "file.txt",
        ),
        ("./file.txt", ".", "/home/user", "file.txt"),
        ("./file.txt", "./", "/home/user", "file.txt"),
        ("././file.txt", "./", "/home/user", "file.txt"),
    ],
)
def test_relpath_no_syscalls(
    target_path, start_path, current_working_directory, expected
):
    assert (
        relpath_no_syscalls(target_path, start_path, current_working_directory)
        == expected
    )
