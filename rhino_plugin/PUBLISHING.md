# Publishing to McNeel Package Server

## One-time setup
1. Create a McNeel account at https://accounts.mcneel.com
2. Install the Yak CLI (ships with Rhino 8):
   - macOS: `/Applications/Rhino 8.app/Contents/Resources/bin/yak`
   - Windows: `C:\Program Files\Rhino 8\System\yak.exe`
3. Authenticate: `yak login`

## Per-release
1. Build plugin: `./scripts/build-plugin.sh`
2. Package: `./scripts/package-plugin.sh`
3. Verify: `yak inspect rhino_plugin/package/rhino-mcp-<version>-rh8_17-any.yak`
4. Push: `yak push rhino_plugin/package/rhino-mcp-<version>-rh8_17-any.yak`

## Versioning policy
- Yak version must match `manifest.yml` → must match `AssemblyInformationalVersion` → must match `pyproject.toml`
- All four locations updated by `scripts/bump-version.sh <new-version>`

## Verification
After pushing, wait ~5 min then search in Rhino: `_PackageManager` → search "rhino-mcp"
