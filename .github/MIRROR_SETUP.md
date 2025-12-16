# Setting Up GitLab Mirror

This repository is primarily hosted on GitHub with an automatic mirror to GitLab.

## GitHub → GitLab Mirror Setup

### Prerequisites

1. GitHub repository (primary)
2. GitLab account with repository created
3. GitHub Personal Access Token with `repo` scope

### Setup Steps

#### 1. Create GitLab Repository

1. Go to GitLab and create a new project
2. Choose "Create blank project"
3. Name it the same as your GitHub repository
4. Set visibility level (public/private)
5. **Do NOT initialize with README** (will be overwritten by mirror)

#### 2. Generate GitHub Personal Access Token

1. Go to GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Click "Generate new token (classic)"
3. Name: "GitLab Mirror Access"
4. Scopes: Select `repo` (Full control of private repositories)
5. Generate token and **save it securely**

#### 3. Configure GitLab Pull Mirror

1. In GitLab, go to: Settings → Repository → Mirroring repositories
2. Enter GitHub repository URL:
   ```
   https://github.com/OWNER_USERNAME/domain-mcp-template.git
   ```
3. **Mirror direction:** Pull
4. **Authentication method:** Password
5. **Password:** Paste your GitHub Personal Access Token
6. **Mirror branches:** All branches (or select specific branches)
7. **Optional settings:**
   - Enable "Overwrite diverged branches" (recommended)
   - Set update interval (default: every hour)
8. Click "Mirror repository"

### Verification

After setup:

1. Check GitLab repository should show "Mirroring from..." badge
2. Wait for first sync (may take a few minutes)
3. Verify branches and commits match GitHub

### Updating the Mirror

The mirror updates automatically based on your configured interval. To force an update:

1. Go to Settings → Repository → Mirroring repositories
2. Click the refresh icon next to your mirror

## Alternative: GitHub Actions Mirror (Manual)

If you prefer GitHub Actions to push to GitLab:

### 1. Generate SSH Key Pair

```bash
ssh-keygen -t ed25519 -C "github-to-gitlab-mirror" -f gitlab_mirror_key
# Creates: gitlab_mirror_key (private) and gitlab_mirror_key.pub (public)
```

### 2. Add Public Key to GitLab

1. Go to GitLab → Settings → SSH Keys
2. Paste contents of `gitlab_mirror_key.pub`
3. Title: "GitHub Mirror Key"
4. Click "Add key"

### 3. Add Private Key to GitHub Secrets

1. Go to GitHub repo → Settings → Secrets and variables → Actions
2. Click "New repository secret"
3. Name: `GITLAB_SSH_PRIVATE_KEY`
4. Value: Paste contents of `gitlab_mirror_key` (the private key)
5. Click "Add secret"

### 4. Create GitHub Actions Workflow

The workflow is already included in `.github/workflows/mirror-to-gitlab.yml` (if you created it).

If not, create it:

```yaml
name: Mirror to GitLab

on:
  push:
    branches:
      - main
      - develop
  workflow_dispatch:

jobs:
  mirror:
    runs-on: ubuntu-latest
    steps:
      - name: Mirror to GitLab
        uses: wearerequired/git-mirror-action@v1
        env:
          SSH_PRIVATE_KEY: ${{ secrets.GITLAB_SSH_PRIVATE_KEY }}
        with:
          source-repo: https://github.com/${{ github.repository }}.git
          destination-repo: git@gitlab.com:OWNER_USERNAME/domain-mcp-template.git
```

### 5. Enable Workflow

1. Push the workflow file to GitHub
2. Go to Actions tab to verify it runs

## Troubleshooting

### Mirror shows "Failed"

**Check:**
- GitHub token is still valid (they expire)
- GitHub token has correct permissions (`repo` scope)
- GitLab repository exists and is accessible
- No branch protection conflicts

**Fix:**
1. Generate new GitHub token
2. Update in GitLab: Settings → Repository → Mirroring repositories
3. Click edit (pencil icon) → Update password → Save

### Mirror is out of sync

**Manual sync:**
1. Go to Settings → Repository → Mirroring repositories
2. Click refresh icon (⟳)

**Check update interval:**
- Default is 1 hour
- Can be increased/decreased in mirror settings

### SSH key issues (GitHub Actions method)

**Check:**
- Private key added to GitHub Secrets correctly
- Public key added to GitLab
- SSH key has no passphrase
- Key type is supported (ed25519 or RSA)

## Maintenance

### Rotating Tokens

Recommended every 90 days:

1. Generate new GitHub Personal Access Token
2. Update in GitLab mirror settings
3. Delete old token from GitHub

### Monitoring

Check mirror status regularly:
- GitLab: Settings → Repository → Mirroring repositories
- Look for "Successfully updated" timestamp
- Check for any error messages

## Documentation for Users

Add this to your repository README:

```markdown
## 🔄 Repository Mirrors

This repository is available on multiple platforms:

- **GitHub (Primary):** https://github.com/OWNER_USERNAME/domain-mcp-template
- **GitLab (Mirror):** https://gitlab.com/OWNER_USERNAME/domain-mcp-template

Both repositories are synchronized automatically. Choose the platform you prefer!
```

## Support

If you encounter issues:
- Check GitLab's mirroring documentation
- Verify token permissions
- Check repository visibility settings
- Review GitLab's mirror logs for specific errors

