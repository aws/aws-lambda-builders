## Python - UV Lambda Builder

### Scope

This package provides a Python dependency builder that uses UV (An extremely fast Python package installer and resolver, written in Rust) as an alternative to the traditional pip-based workflow. The scope for this builder is to take an existing directory containing customer code, and dependency specification files (such as `pyproject.toml` or `requirements.txt`) and use UV to build and include the dependencies in the customer code bundle in a way that makes them importable in AWS Lambda.

UV offers several advantages over pip:
- **Performance**: UV is significantly faster than pip for dependency resolution and installation
- **Better dependency resolution**: More reliable and consistent dependency resolution
- **Lock file support**: Native support for lock files for reproducible builds
- **Modern Python packaging**: Built-in support for modern Python packaging standards (PEP 517/518)
- **Virtual environment management**: Integrated virtual environment handling

### Challenges

Similar to the Python PIP workflow, Python packaging for AWS Lambda presents unique challenges:

1. **Platform compatibility**: Python packages often contain platform-specific code or compiled extensions that must be compatible with the AWS Lambda runtime environment (Amazon Linux 2 for Python 3.8-3.11, Amazon Linux 2023 for Python 3.12+)

2. **Architecture compatibility**: Packages must be compatible with the target Lambda architecture (x86_64 or arm64)

3. **Dependency resolution complexity**: Complex dependency trees with potential conflicts need to be resolved consistently

4. **Binary dependencies**: Some packages require compilation of C extensions or have binary dependencies that must be built for the target platform

5. **Package size optimization**: Lambda has deployment package size limits, requiring efficient dependency packaging

UV addresses many of these challenges through:
- Better dependency resolution algorithms
- Improved handling of platform-specific wheels
- More efficient caching mechanisms
- Better support for lock files ensuring reproducible builds

### Interface

The top level interface is presented by the `PythonUvDependencyBuilder` class. There will be one public method `build_dependencies`, which takes the provided arguments and builds python dependencies using UV under the hood.

```python
def build_dependencies(artifacts_dir_path,
                       scratch_dir_path,
                       manifest_path,
                       architecture=None,
                       config=None,
                      ):
    """Builds a python project's dependencies into an artifact directory using UV.

    Note: The runtime parameter is passed to the PythonUvDependencyBuilder constructor,
    not to this method.

    :type artifacts_dir_path: str
    :param artifacts_dir_path: Directory to write dependencies into.

    :type scratch_dir_path: str
    :param scratch_dir_path: Temporary directory for build operations and intermediate files.

    :type manifest_path: str
    :param manifest_path: Path to a dependency manifest file. Supported manifests:
        - pyproject.toml (preferred for modern Python projects)
        - requirements.txt (traditional pip format)  
        - requirements-*.txt (environment-specific: dev, test, prod, etc.)
        
        Note: uv.lock is NOT a valid manifest - it's a lock file that automatically
        enhances pyproject.toml builds when present in the same directory.

    :type runtime: str
    :param runtime: Python version to build dependencies for. This can
        be python3.8, python3.9, python3.10, python3.11, python3.12, python3.13,
        python3.14, or python3.15.
        These are currently the only supported values.
        Note: This parameter is passed to the PythonUvDependencyBuilder constructor.

    :type config: :class:`lambda_builders.actions.python_uv.utils.UvConfig`
    :param config: Optional config object for customizing UV behavior,
        including cache settings, index URLs, and build options.

    :type architecture: str
    :param architecture: Target architecture for Lambda compatibility (x86_64 or arm64).
        Defaults to x86_64 if not specified.
    """
```

### Usage Pattern

The `PythonUvDependencyBuilder` follows a constructor + method call pattern:

```python
# 1. Create builder with runtime
builder = PythonUvDependencyBuilder(
    osutils=osutils,
    runtime="python3.9",  # Runtime specified here
    uv_runner=uv_runner
)

# 2. Call build_dependencies method
builder.build_dependencies(
    artifacts_dir_path="/path/to/artifacts",
    scratch_dir_path="/path/to/scratch",
    manifest_path="/path/to/pyproject.toml",
    architecture="x86_64",
    config=uv_config
)
```

### Implementation

The general algorithm for preparing a python package using UV for use on AWS Lambda follows a streamlined approach that leverages UV's advanced capabilities:

#### Step 1: Pick the manifest

An explicit manifest path is used as given. Without one, the workflow picks a manifest in the
order listed under [Smart Manifest Detection and Dispatch](#smart-manifest-detection-and-dispatch).

When the manifest is `pyproject.toml`, the workflow resolves the workspace root (the project
directory for a standalone project; see
[Workspace Resolution Failure Policy](#workspace-resolution-failure-policy)) and uses a
`uv.lock` found there. `uv.lock` is never a manifest on its own.

#### Step 2: Build dependencies based on manifest type

**For pyproject.toml with uv.lock present:**
- Use `uv export` to convert lock file to requirements.txt format
- Export with `--locked`, reusing the lock's resolution mode, prerelease mode, fork strategy, and `exclude-newer`
  cutoff so export validates rather than rewrites the existing lock. Stale locks fail the build;
  run `uv lock` explicitly after dependency changes.
- For relative cutoffs, replay `exclude-newer-span` instead of the lock's placeholder `exclude-newer` date.
  Python 3.10 uses the runtime dependency `tomli` to read lock options; Python 3.11+ uses `tomllib`.
- Replay each `options.exclude-newer-package` entry with `--exclude-newer-package`, preferring its `span`
  over the placeholder `timestamp` for relative per-package cutoffs.
- Install using `uv pip install` with platform targeting (--python-platform)
- Provides reproducible builds with locked dependency versions AND cross-platform support

**For pyproject.toml without uv.lock:**
- Run `uv lock` from the project directory. uv writes `uv.lock` there, or at the workspace root
  for a workspace member, and the file stays in the source tree after the build
- Use `uv export` to convert lock file to requirements.txt format
- Install dependencies using `uv pip install` with platform targeting

**Stale locks:** both pyproject.toml paths run `uv export --locked`, so a `uv.lock` that no longer
matches `pyproject.toml` fails the build instead of being rewritten. A project without
`requires-python` that was locked on one Python version can be stale on another runtime; set
`requires-python` or run `uv lock` again.

**Hashes:** the export keeps the lock's hashes, so a project that sets `require-hashes` in
`[tool.uv.pip]` builds.

**For requirements.txt files:**
- Use `uv pip install` directly with Lambda-compatible settings
- uv runs from the manifest's directory, so local paths in the file (such as `./libs/foo` or
  `-e ../shared`) resolve from there

**Local paths in lock builds:** exported local paths are relative to the workspace root, so
`uv pip install` runs from the workspace root (the project directory for a standalone project).

**Why export + pip install instead of uv sync?**
`uv sync` doesn't support cross-platform builds (no --python-platform flag). Since Lambda
requires building for Linux (x86_64 or ARM64) regardless of the build machine's OS, we use
`uv export` to convert lock files to requirements.txt, then `uv pip install` which supports
the `--python-platform` flag for cross-platform wheel selection.

#### Step 3: Configure Lambda-compatible installation

UV is configured with Lambda-specific settings:
- Target platform: explicit manylinux targets, independent of the build host's glibc.
  Python 3.8-3.11 use `manylinux_2_17` (the AL2-compatible download target used by the pip workflow);
  Python 3.12+ use `manylinux_2_34` for Amazon Linux 2023.
- Target architecture: `x86_64` or `aarch64` 
- Python version matching Lambda runtime
- Prefer wheels over source distributions for faster builds

#### Step 4: Install to target directory

Install resolved dependencies to the Lambda deployment package:
- Extract packages to artifacts directory
- Maintain proper Python package structure
- Ensure all packages are importable from Lambda function

This streamlined approach leverages UV's built-in capabilities rather than manually implementing dependency resolution, compilation handling, and optimization steps that UV already performs efficiently.

### UV-Specific Features

This workflow leverages several UV-specific features that provide advantages over the traditional pip workflow:

#### Lock File Support
- **Reproducible builds**: `uv.lock` files ensure identical dependency versions across builds
- **Faster subsequent builds**: Lock files eliminate dependency resolution time
- **Conflict detection**: Early detection of dependency conflicts during resolution

#### Advanced Dependency Resolution
- **Better conflict resolution**: UV's resolver handles complex dependency graphs more reliably
- **Version range optimization**: More intelligent selection of compatible versions
- **Platform-aware resolution**: Better handling of platform-specific dependencies

#### Performance Optimizations
- **Parallel downloads**: Multiple packages downloaded simultaneously
- **Efficient caching**: Smart caching reduces redundant downloads and builds
- **Fast installs**: Rust-based implementation provides significant speed improvements

#### Modern Python Standards
- **PEP 517/518 support**: Native support for modern Python packaging standards
- **pyproject.toml first**: Preferred support for modern project configuration
- **Build isolation**: Proper build environment isolation for reliable builds

### Error Handling and Diagnostics

The UV workflow provides enhanced error handling:

1. **Dependency resolution errors**: Clear reporting of version conflicts and resolution failures
2. **Platform compatibility warnings**: Explicit warnings about potential platform issues
3. **Build failures**: Detailed error messages for compilation and build failures
4. **Lock file conflicts**: Detection and reporting of lock file inconsistencies
5. **Performance metrics**: Optional reporting of build times and cache efficiency

### Configuration Options

The workflow supports various configuration options through the config parameter:

```python
config = {
    "index_url": "https://pypi.org/simple/",  # Custom package index
    "extra_index_urls": [],                   # Additional package indexes
    "cache_dir": None,                       # Custom cache directory; UV's own default when unset
    "no_cache": False,                       # Disable caching
    "prerelease": "disallow",                # Handle pre-release versions
    "resolution": "highest",                 # Resolution strategy
    "compile_bytecode": True,                # Compile .pyc files
    "exclude_newer": None,                   # Exclude packages newer than date
    "generate_hashes": False,                # Generate package hashes
}
```

### Build options

`PythonUvWorkflow` reads these keys from the workflow `options` and passes them to `uv export`.
SAM CLI maps them from `Metadata.BuildProperties`.

| Option | SAM CLI property | Type | `uv export` effect |
|---|---|---|---|
| `uv_groups` | `UvGroups` | list of str | `--group <name>` per entry |
| `uv_extras` | `UvExtras` | list of str | `--extra <name>` per entry |
| `uv_all_extras` | `UvAllExtras` | bool | `--all-extras` |
| `uv_prune` | `UvPrune` | list of str | `--prune <name>` per entry: drops the package and any dependency only it needs |

Default groups stay excluded (`--no-default-groups`); `uv_groups` adds groups on top of that.
`uv_prune` is meant for packages the Lambda runtime already ships, such as `boto3`. The function then
uses the runtime's version, which AWS picks, not the version in `uv.lock`.
The build fails with a clear message, instead of ignoring the option, when:
- a value has the wrong type, or an unknown `uv_*` key is given;
- `uv_extras` and `uv_all_extras` are combined;
- an option is set on a `requirements.txt` build (they apply only to pyproject.toml / uv.lock projects);
- a `uv_prune` name is not a package in `uv.lock`, which `uv export --prune` would otherwise ignore.

### Settings from pyproject.toml

The workflow runs `uv export` and `uv pip install` from the project, so uv reads its own settings there.
Build-control settings in `[tool.uv]` (`no-build`, `no-build-package`, `no-binary`, `no-binary-package`) apply
to both steps; `[tool.uv.pip]` settings (`no-build`, `no-binary`, `only-binary`) apply to the install. `UV_*`
environment variables apply to every uv call. The workflow's own flags always win: the target platform and
Python version come from the function's architecture and runtime, default groups are excluded, and nothing
is installed editable. In a uv workspace only the workspace root's `pyproject.toml` settings are used; a
member's `[tool.uv]` and `[tool.uv.pip]` tables are ignored. An unknown key in either table makes uv ignore
every setting in that file. The build log shows uv's warning about it (the workflow logs every `warning:`
that uv prints, once per build), so check the key names against uv's settings reference.

### uv warnings

Every `warning:` block uv prints is logged at WARNING, once per build. Some are harmless, such as
"Failed to hardlink files; falling back to full copy" when the cache and the target are on
different file systems. The one to act on is an unknown key in `[tool.uv]` (or `[tool.uv.pip]`):
uv then ignores every setting in that file.

### Caching

The workflow does not pass `--cache-dir` unless a caller supplies one, so UV uses its own
default cache location (`~/.cache/uv` on Linux, overridable with `UV_CACHE_DIR`). This mirrors
the `python_pip` workflow, which likewise leaves `PIP_CACHE_DIR` alone and inherits pip's
user-level cache.

Keeping the cache outside the build directory is what makes it useful: it survives a single
build, so UV reuses previously downloaded dependencies across functions within one `sam build`
and across successive builds. Pointing UV at the build's scratch directory instead would
discard the cache every time, because that directory is deleted when the build finishes — every
function would then re-download its entire dependency set on every build.

The one exception is a default cache location that can't be created, such as `/.cache/uv` for a
container build run as a host uid with no home directory (`sam build --use-container
--mount-with WRITE`). Then the build uses `uv-cache` under the scratch directory and logs a
warning. Nothing is lost there, because such a container starts with an empty cache anyway.

### Compatibility with Existing Workflows

The UV workflow is designed to be a drop-in replacement for the pip workflow:
- Supports the same manifest formats (requirements.txt, pyproject.toml)
- Uses native UV commands for pyproject.toml (lock/export workflow)
- Maintains the same output structure and package layout
- Compatible with existing Lambda deployment processes
- Provides migration path from pip-based builds
- Follows established requirements file naming conventions

### Architecture Components

The UV workflow consists of several key components that mirror the PIP workflow structure:

#### Core Classes

1. **PythonUvWorkflow**: Main workflow class that orchestrates the build process
2. **PythonUvBuildAction**: Action class that handles dependency resolution
3. **UvRunner**: Wrapper around UV command execution
4. **SubprocessUv**: Low-level UV subprocess interface
5. **PythonUvDependencyBuilder**: High-level dependency builder orchestrator

#### File Structure
```
python_uv/
├── __init__.py
├── DESIGN.md
├── workflow.py          # Main workflow implementation
├── actions.py           # Build actions
├── packager.py          # Core packaging logic
├── utils.py             # Utility functions
└── exceptions.py        # UV-specific exceptions
```

#### Capability Definition
```python
CAPABILITY = Capability(
    language="python", 
    dependency_manager="uv", 
    application_framework=None
)
```

#### Smart Manifest Detection and Dispatch

The workflow uses intelligent manifest detection:

**Auto-detection (when no manifest path is given), in order of preference:**
1. `pyproject.toml`, when it is the uv project: a `uv.lock` sits beside it, or its `[project]` table declares a non-empty `dependencies` list
2. `requirements.txt`, then `requirements-prod.txt`
3. `pyproject.toml` otherwise (metadata or tool settings only, empty `dependencies`, or `dynamic` dependencies)

`requirements-dev.txt` and `requirements-test.txt` are never auto-detected: development and test dependencies do not belong in a Lambda package. They can still be passed as an explicit manifest path.

On Python 3.10 without `tomli`, declared dependencies cannot be read, so only a `uv.lock` makes `pyproject.toml` win over a requirements file.

**Smart Lock File Enhancement:**
- When `pyproject.toml` is used, automatically detects `uv.lock` at the resolved workspace or project root
- If `uv.lock` exists, uses lock-based build for reproducible dependencies
- If no `uv.lock`, uses standard pyproject.toml workflow with UV's lock and export

**Important:** `uv.lock` is NOT a standalone manifest - attempting to use it as one will result in an "Unsupported manifest file" error.

#### Requirements File Naming Conventions
The workflow follows Python ecosystem standards for requirements files:
- `requirements.txt` - Standard format (primary)
- `requirements-dev.txt` - Development dependencies
- `requirements-test.txt` - Test dependencies  
- `requirements-prod.txt` - Production dependencies
- `requirements-staging.txt` - Staging dependencies

Only `requirements.txt` and `requirements-prod.txt` are auto-detected. The others are used only
when passed as the manifest path.

Note: `requirements.in` (pip-tools format) is not supported to keep the implementation simple and focused.

#### UV Binary Requirements
- UV must be available on the system PATH
- Minimum UV version: 0.1.0 (to be determined based on feature requirements)
- Workspace discovery needs UV 0.9.9 or newer; older versions build from the project directory
- A missing UV raises `MissingUvError`; the workflow does not install UV

#### Error Handling Strategy
- **MissingUvError**: UV binary not found on PATH (includes path information)
- **UvInstallationError**: UV installation/setup failures
- **UvBuildError**: Package build failures
- **LockFileError**: Lock file parsing or validation errors

#### Workspace Resolution Failure Policy

Workspace discovery runs before the lock-file lookup for every `pyproject.toml` build.
The compatibility fallback to the project directory is deliberately limited to two cases:

- A plain `X.Y.Z` UV version is numerically below `0.9.9`; the workspace command is not invoked.
- The workspace command exits unsuccessfully and stderr contains `unrecognized subcommand 'workspace'`.

Both cases log at DEBUG. They additionally emit a WARNING only if a `pyproject.toml`
in the project directory or an ancestor contains a `tool.uv.workspace` table. This is
only a diagnostic hint: `members` and `exclude` are not evaluated, so the warning does
not assert membership or change the chosen root or build path. Unreadable or invalid
TOML is logged at DEBUG and skipped. The helper lazily imports `tomllib`, or optional
`tomli` on Python 3.10. If neither is available, it logs at DEBUG and skips configuration
inspection; no TOML parser is required to build dependencies.
This preserves the previous behavior for standalone projects
using unsupported UV versions; it does not provide workspace support for those versions.
Unknown or prerelease version strings are tested by invoking the workspace command rather
than assuming support or lack of support.

All other command failures raise `UvBuildError` with the diagnostic, and a successful exit
with empty or whitespace-only output also raises because it supplies no root directory.
These outcomes do not establish that the project is outside a workspace. Falling back could
miss an existing workspace-root lock, trigger lock generation, or resolve local dependencies
from the wrong directory.

This intentionally favors stopping on uncertain workspace discovery over continuing a
potentially incorrect build. Consequently, a standalone project that previously built may
now stop if workspace discovery fails for an unknown reason. That compatibility limitation
is accepted rather than treating permission, configuration, or process-start failures as
evidence that the workspace command is unsupported. The original diagnostic is surfaced
instead of recommending an upgrade for an unknown cause.

#### Platform Compatibility Matrix
| Python Version | x86_64 | arm64 | Status |
|---------------|--------|-------|---------|
| python3.8     | ✓      | ✓     | Supported |
| python3.9     | ✓      | ✓     | Supported |
| python3.10    | ✓      | ✓     | Supported |
| python3.11    | ✓      | ✓     | Supported |
| python3.12    | ✓      | ✓     | Supported |
| python3.13    | ✓      | ✓     | Supported |
| python3.14    | ✓      | ✓     | Supported |
| python3.15    | ✓      | ✓     | Supported |

#### Integration with Lambda Builders
- Registers with the workflow registry automatically
- Follows the same build lifecycle as other workflows
- Compatible with existing SAM CLI integration
- Supports all standard build options (scratch_dir, dependencies_dir, etc.)

### Implementation Phases

#### Phase 1: Core Infrastructure
1. Basic workflow and action classes
2. UV binary detection and validation
3. Simple requirements.txt support
4. Basic error handling

#### Phase 2: Advanced Features
1. pyproject.toml support
2. Lock file handling
3. Advanced configuration options
4. Performance optimizations

#### Phase 3: Production Readiness
1. Comprehensive testing
2. Error message improvements
3. Documentation and examples
4. Performance benchmarking

### Testing Strategy

#### Unit Tests
- UV binary detection and validation
- Manifest file parsing and detection
- Dependency resolution logic
- Error handling scenarios
- Platform compatibility checks

#### Integration Tests
- End-to-end build scenarios
- Different manifest file formats
- Lock file generation and usage
- Multi-architecture builds
- Performance comparisons with pip

#### Compatibility Tests
- Migration from pip to UV workflows
- Existing SAM CLI integration
- Various Python project structures
- Different dependency complexity levels

### Future Enhancements

Potential future improvements to the UV workflow:
- **Dependency vulnerability scanning**: Integration with security scanning tools
- **Package size optimization**: Advanced techniques for reducing package size
- **Multi-platform builds**: Support for building packages for multiple architectures simultaneously
- **Custom build hooks**: Support for custom build steps and transformations
- **Integration with other tools**: Better integration with other Python development tools
- **UV auto-installation**: Automatic UV installation if not present on system
- **Build caching**: Advanced caching strategies for faster subsequent builds
- **Dependency analysis**: Detailed dependency tree analysis and reporting
