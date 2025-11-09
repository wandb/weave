# Repo Cleanup

This document is a guide on cleaning old blobs from the repo if it get's too big.

## Steps

You can see how big the repo is by running the following command:

```bash
git count-objects -vH
```

If we start getting north of 200MB, we should likely clean the repo.

### Install BFG Repo-Cleaner

[Download BFG Repo-Cleaner](https://rtyley.github.io/bfg-repo-cleaner/) and install java if you don't have it.

```bash
brew install java
```

### Clone the repo

Checkout a bare version of the repo with the following command:

```bash
git clone --mirror https://github.com/wandb/weave.git weave-cleanup.git
```

### Backup the repo

```bash
git bundle create weave-$(date +%Y-%m-%d).bundle --all
```

### Clean the repo

The below command will remove all files larger than 500K and delete the files with the following extensions:

```bash
java -jar bfg.jar --strip-blobs-bigger-than 500K --delete-files "*.{so,pdb,pyx,whl,dat,dylib}" weave-cleanup.git
```

Then gc the repo and see how much space it saved:

```bash
git reflog expire --expire=now --all && git gc --prune=now --aggressive
git count-objects -vH
```

### YOLO

```bash
git push --force --all
```
