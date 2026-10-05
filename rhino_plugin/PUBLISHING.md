# Publishing rhino-mcp

The current source version is **0.20.0**. Local builds and public releases are separate steps; see the [upgrade guide](../docs/upgrade-0.20.0.md) for the prepared artifacts and validation limits.

## Per-release preparation

1. Synchronize versions using the [AGENTS.md checklist](../AGENTS.md#version-bumping-checklist): Python metadata and lockfile, C# project and informational version, Yak manifest, Docker label, and documentation.
2. Run the full non-integration test suite and lint commands in [AGENTS.md](../AGENTS.md#running-tests). Run live Rhino integration separately on a scratch document.
3. From the repository root, build matching artifacts:

   ```bash
   bash scripts/package-plugin.sh
   uv build
   docker build -t rhino-mcp:0.20.0 -t rhino-mcp:latest .
   ```

4. Inspect the generated Yak manifest and Python package metadata. Confirm that `rhino_plugin/release/manifest.yml` matches the source version. The package script stages only the current version's Yak package; older files may remain in the output directory, so select exact filenames when publishing.
5. Test the installed plugin and configured container. Building the plugin does not install it; rebuilding an image does not recreate an existing container. Document any unverified integration behavior.

## One-time setup for McNeel Package Server

The Yak CLI ships with Rhino 8 at `/Applications/Rhino 8.app/Contents/Resources/bin/yak` on macOS and `C:\Program Files\Rhino 8\System\yak.exe` on Windows. Create a McNeel account and run `yak login` once. With Yak available on your command path:

```bash
yak inspect rhino_plugin/release/rhino-mcp-0.20.0-rh8_17-any.yak
# Publishing step: uploads the package to the public package server
yak push rhino_plugin/release/rhino-mcp-0.20.0-rh8_17-any.yak
```

After publication, verify the available version in Rhino's `_PackageManager` and install it on a test workstation.

## GitHub and Python distribution

Create the intended version tag and GitHub release explicitly, then attach the matching `.rhp`, `.yak`, and release checksums. The optional [plugin release workflow](../.github/workflows/release-plugin.yml) is manually dispatched and requires a self-hosted macOS runner with Rhino. Verify its tag/ref and release configuration before use; building alone does not create a tag or publish a release.

Python wheel and sdist are generated in `dist/`. Their creation does not upload them to PyPI. Publish through the project's chosen distribution process only after verifying matching versions and release contents.

## Versioning policy

Keep `rhino_plugin/package/manifest.yml` synchronized with Python package metadata, the lockfile, C# assembly/project versions, and Docker labels as detailed above.

## Verification

Inspect the exact packaged version before publication, then verify MCP initialization and the installed plugin report that same version after installation.

## macOS installer

Build the matching Python wheel first, then run `bash scripts/build-installer.sh` on macOS with Rhino 8, .NET 8, uv-managed Python 3.13 runtimes, and Developer ID signing certificates. Set `NOTARY_PROFILE` to the existing notarytool Keychain profile to submit and staple both packages.

The builder stages runtimes and virtual environments in a temporary directory, rewrites their paths for `/Users/Shared/rhino_mcp`, and includes the Rhino plugin dependencies. Building does not overwrite the live shared installation. It outputs `release/rhino-mcp-0.20.0-universal-signed.pkg` and `release/rhino-mcp-0.20.0-universal-uninstaller-signed.pkg`. Verify signatures, stapled tickets, and both bundled Python versions before distribution.

## Published 0.17.1 and documentation updates

The [v0.17.1 GitHub release](https://github.com/hov172/rhino_mcp/releases/tag/v0.17.1) contains nine assets. Both macOS packages are signed, notarized, and stapled. The installed plugin/server passed a local read-only end-to-end check; see the [validation record](../release/validation-0.17.1.md).

Keep published binary tags fixed at their build commit. Documentation-only follow-ups go to `main`; update the release’s validation attachment and notes when verification evidence changes. Do not rebuild or relabel unchanged binaries. `release/SHA256SUMS-0.17.1` covers seven binary assets; when changing a documentation attachment, verify its uploaded digest separately.
