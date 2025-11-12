# Build Scripts

## build-and-push.sh

Automated script to build and push Docker images with version bumping.

### Features

- ✅ Automatically increments patch version (e.g., 0.0.1 → 0.0.2)
- ✅ Updates VERSION file
- ✅ Builds Docker image with both version and latest tags
- ✅ Pushes to GitHub Container Registry (ghcr.io)
- ✅ Interactive prompts for confirmation and login
- ✅ Colorized output for better readability

### Usage

#### Option 1: Using Make (Recommended)
```bash
make build-push
```

#### Option 2: Direct Script Execution
```bash
bash scripts/build-and-push.sh
```

#### Option 3: Using Cursor IDE Command
1. Open Command Palette (Cmd/Ctrl + Shift + P)
2. Type "Build and Push Docker Image"
3. Select the command

### Prerequisites

1. **Docker** must be installed and running
2. **GitHub Personal Access Token** with `write:packages` permission
3. **Git repository** configured (for auto-detecting repository name)

### GitHub Container Registry Login

If not already logged in, the script will prompt you. You can also login manually:

```bash
echo $GITHUB_TOKEN | docker login ghcr.io -u YOUR_USERNAME --password-stdin
```

### What It Does

1. Reads current version from `VERSION` file
2. Increments patch version (0.0.1 → 0.0.2)
3. Updates `VERSION` file with new version
4. Builds Docker image with tags:
   - `ghcr.io/{owner}/{repo}:{version}` (e.g., `ghcr.io/kono/flowdash-backend:0.0.2`)
   - `ghcr.io/{owner}/{repo}:latest`
5. Prompts for confirmation before pushing
6. Pushes both tags to GitHub Container Registry

### Environment Variables

The script will try to auto-detect the GitHub repository from:
1. Git remote URL
2. `GITHUB_REPOSITORY` environment variable
3. Prompt if neither is available

### Example Output

```
🚀 FlowDash Backend - Build and Push Docker Image

📦 Current version: 0.0.1
✨ New version: 0.0.2

✅ Updated VERSION file

🐳 Building Docker image...
   Image: ghcr.io/kono/flowdash-backend
   Tags: ghcr.io/kono/flowdash-backend:0.0.2, ghcr.io/kono/flowdash-backend:latest

✅ Docker image built successfully

Push image to GitHub Container Registry? (y/N): y

📤 Pushing Docker image...
   Pushing ghcr.io/kono/flowdash-backend:0.0.2...
   Pushing ghcr.io/kono/flowdash-backend:latest...

✅ Successfully pushed Docker image!

📋 Summary:
   Version bumped: 0.0.1 → 0.0.2
   Image: ghcr.io/kono/flowdash-backend
   Tags pushed:
     - ghcr.io/kono/flowdash-backend:0.0.2
     - ghcr.io/kono/flowdash-backend:latest
```

