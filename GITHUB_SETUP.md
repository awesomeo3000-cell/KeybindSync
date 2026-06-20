# GitHub Setup

This local repo is ready at:

```text
E:\WoWKeyBindSync\Repo
```

## Option A: GitHub Desktop

1. Open GitHub Desktop.
2. Choose `File -> Add local repository`.
3. Select `E:\WoWKeyBindSync\Repo`.
4. Click `Publish repository`.
5. Recommended first publish setting: private.
6. Make it public when ready for the public source release.

## Option B: GitHub CLI

Install GitHub CLI, then:

```powershell
gh auth login
cd E:\WoWKeyBindSync\Repo
gh repo create WoWKeyBindSync --private --source . --remote origin --push
```

To make it public later:

```powershell
gh repo edit --visibility public
```

## Version Tags

For a public release:

```powershell
git tag v1.3.0
git push origin v1.3.0
```

The GitHub Actions workflow will build and attach the Windows exe to the tagged release.
