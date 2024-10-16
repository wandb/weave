import os

import git


def get_git_root(path: str) -> str:
    git_repo = git.Repo(path, search_parent_directories=True)
    git_root = git_repo.git.rev_parse("--show-toplevel")
    return os.path.relpath(git_root, path)


NOTEBOOK_TEST_TEMPLATE = """
import {checkWeaveNotebookOutputs} from '%s/notebooks';

describe('%s notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('%s')
    );
});
""".strip()


def makedir(path):
    path = os.path.dirname(path)
    if not os.path.exists(path):
        os.makedirs(path)


def main():
    # For any notebook found within the examples directory, generate a
    # test file in integration_test/cypress/e2e/notebooks.
    git_root = get_git_root(os.curdir)
    examples_dir = os.path.join(git_root, "examples")
    integration_dir = os.path.join(git_root, "integration_test")
    test_dir = os.path.join(integration_dir, "cypress", "e2e", "notebooks")
    for root, dirs, files in os.walk(examples_dir):
        subdir = root.split("/")[-1]
        if subdir == "skip_test" or subdir == "ProductionMonitoring":
            continue
        for file in files:
            if "ipynb_checkpoints" in root:
                continue
            if file.endswith(".ipynb"):
                # keep location of Embeddings.ipynb for ProdMon demos and explore_embeddings for getting started
                # TODO: replace with tested demo notebook
                if "mbedding" in file:
                    continue
                notebook_path = os.path.join(root, file)
                test_path = os.path.join(
                    test_dir,
                    os.path.relpath(root, "examples"),
                    file.replace(".ipynb", ".cy.ts"),
                )
                makedir(test_path)
                cypress_notebook_path = os.path.relpath(notebook_path, integration_dir)
                relative_notebook_path = os.path.relpath(
                    test_dir, os.path.dirname(test_path)
                )
                test_code = NOTEBOOK_TEST_TEMPLATE % (
                    relative_notebook_path,
                    cypress_notebook_path,
                    cypress_notebook_path,
                )
                print("PATHS %s %s\n%s" % (notebook_path, test_path, test_code))
                with open(test_path, "w") as f:
                    f.write(test_code)


if __name__ == "__main__":
    main()
