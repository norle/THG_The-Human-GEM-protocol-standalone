# Publish the Git LFS migration in a standalone repository

This runbook describes how to publish the rewritten `refactoring-cleanup`
branch in a new GitHub repository that is not part of the existing public fork
network.

GitHub rejected new LFS objects in the existing public fork. Creating a
repository with `gh repo create` uses the normal repository-creation API rather
than the fork API, allowing the new repository to own its LFS objects.

The procedure deliberately leaves the existing `origin` and `fork` remotes
unchanged until the new repository and its LFS objects have been validated.

## 1. Choose the repository name and visibility

The examples use:

```text
norle/THG_The-Human-GEM-protocol-standalone
```

Choose whether the repository should be public or private. GitHub LFS storage
and bandwidth limits may apply in either case.

## 2. Verify the local branch

Run these checks from the existing checkout:

```bash
gh auth status
git lfs version
git status --short
git branch --show-current
git lfs fsck refactoring-cleanup
git lfs ls-files
```

The active branch should be `refactoring-cleanup`. The LFS listing should
contain the seven paths recorded in
[`artifact-inventory.md`](artifact-inventory.md).

Review and commit any intended working-tree changes before publishing.
Uncommitted and untracked files are not included in the new repository.

## 3. Create an independent GitHub repository

For a public repository:

```bash
gh repo create norle/THG_The-Human-GEM-protocol-standalone \
  --public \
  --source=. \
  --remote=standalone
```

Use `--private` instead of `--public` if required.

This creates the repository and adds a local remote named `standalone`. It does
not modify the existing `origin` or `fork` remotes.

## 4. Confirm that the repository is not a fork

```bash
gh repo view norle/THG_The-Human-GEM-protocol-standalone \
  --json nameWithOwner,isFork,parent,url
```

Confirm that `isFork` is `false` and `parent` is `null`. Stop if GitHub reports
that the new repository belongs to a fork network.

## 5. Upload LFS objects

Upload the objects before publishing commits that refer to them:

```bash
git lfs push standalone refs/heads/refactoring-cleanup
```

Do not continue until this command succeeds. In particular, do not publish
only the Git pointer files.

## 6. Publish the rewritten branch

The new repository is empty, so a force push should not be necessary:

```bash
git push -u standalone \
  refs/heads/refactoring-cleanup:refs/heads/refactoring-cleanup
```

Do not use `git push --all`, a mirror push, or `git lfs push --all` at this
stage. The other local branches have different histories and have not undergone
the same LFS review.

## 7. Validate from a genuinely fresh clone

Use a temporary directory and clone directly from GitHub. Do not populate the
clone with the original checkout's local LFS cache:

```bash
THG_VALIDATION_DIR="$(mktemp -d)"

git clone \
  --branch refactoring-cleanup \
  https://github.com/norle/THG_The-Human-GEM-protocol-standalone.git \
  "$THG_VALIDATION_DIR/repository"

git -C "$THG_VALIDATION_DIR/repository" lfs fsck
git -C "$THG_VALIDATION_DIR/repository" lfs ls-files
```

Verify that all seven LFS files contain their full contents and match the
SHA-256 checksums in
[`artifact-inventory.md`](artifact-inventory.md). This confirms that GitHub can
serve the uploaded objects, rather than only proving that they exist in the
original checkout's local cache.

## 8. Choose the default branch

To keep `refactoring-cleanup` as the default branch:

```bash
gh repo edit norle/THG_The-Human-GEM-protocol-standalone \
  --default-branch refactoring-cleanup
```

If the rewritten branch has been approved as the new project baseline, publish
the same commit as `main`:

```bash
git push standalone \
  refs/heads/refactoring-cleanup:refs/heads/main

gh repo edit norle/THG_The-Human-GEM-protocol-standalone \
  --default-branch main
```

Do not create `main` this way until the rewritten branch is accepted as the new
baseline.

## 9. Keep the existing remotes during validation

Initially, the checkout should retain all three remotes:

```text
origin      MarindeMasLab repository
fork        existing norle public fork
standalone  new independent repository
```

Do not delete the existing fork or rename the remotes as part of this
procedure. After the standalone repository has passed fresh-clone validation,
decide separately whether it should become the checkout's primary `origin`.
