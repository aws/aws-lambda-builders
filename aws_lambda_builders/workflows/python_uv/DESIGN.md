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

1. **Platform compatibility**: Python packages often contain platform-specific code or compiled extensions that must be compatible with the AWS Lambda runtime environment (Amazon Linux 2)

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
        be python3.8, python3.9, python3.10, python3.11, python3.12, or python3.13.
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

#### Step 1: Smart manifest detection and dispatch

The workflow uses a smart dispatch system that recognizes actual manifest files:

**Supported Manifests:**
- `pyproject.toml` - Modern Python project manifest (preferred)
- `requirements.txt` - Traditional pip requirements file
- `requirements-*.txt` - Environment-specific variants (dev, prod, test, etc.)

**Smart Lock File Detection:**
- When `pyproject.toml` is the manifest, automatically checks for `uv.lock` in the same directory
- If `uv.lock` exists alongside `pyproject.toml`, uses lock-based build for precise dependencies
- If no `uv.lock`, uses standard pyproject.toml build with UV's lock and export workflow

**Important:** `uv.lock` is NOT a standalone manifest - it's a lock file that enhances `pyproject.toml` builds when present.

#### Step 2: Build dependencies based on manifest type

**For pyproject.toml with uv.lock present:**
- Use `uv sync` to install exact dependencies from lock file
- Provides reproducible builds with locked dependency versions

**For pyproject.toml without uv.lock:**
- Use `uv lock` to create temporary lock file with resolved dependencies  
- Use `uv export` to convert lock file to requirements.txt format
- Install dependencies using the exported requirements

**For requirements.txt files:**
- Use `uv pip install` directly with Lambda-compatible settings

#### Step 3: Configure Lambda-compatible installation

UV is configured with Lambda-specific settings:
- Target platform: `linux` (Amazon Linux 2)
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
    "cache_dir": "/tmp/uv-cache",            # Custom cache directory
    "no_cache": False,                       # Disable caching
    "prerelease": "disallow",                # Handle pre-release versions
    "resolution": "highest",                 # Resolution strategy
    "compile_bytecode": True,                # Compile .pyc files
    "exclude_newer": None,                   # Exclude packages newer than date
    "generate_hashes": False,                # Generate package hashes
}
```

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
6. **PythonUvDependencyBuilder**: High-level dependency builder orchestrator

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

**Supported Manifests (in order of preference):**
1. `pyproject.toml` - Modern Python project manifest (preferred)
2. `requirements.txt` - Standard pip format  
3. `requirements-*.txt` - Environment-specific variants (dev, test, prod, etc.)

**Smart Lock File Enhancement:**
- When `pyproject.toml` is used, automatically detects `uv.lock` in the same directory
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

Note: `requirements.in` (pip-tools format) is not supported to keep the implementation simple and focused.

#### UV Binary Requirements
- UV must be available on the system PATH
- Minimum UV version: 0.1.0 (to be determined based on feature requirements)
- Fallback: Attempt to install UV using pip if not found (optional behavior)

#### Error Handling Strategy
- **MissingUvError**: UV binary not found on PATH (includes path information)
- **UvInstallationError**: UV installation/setup failures
- **UvBuildError**: Package build failures
- **LockFileError**: Lock file parsing or validation errors

#### Platform Compatibility Matrix
| Python Version | x86_64 | arm64 | Status |
|---------------|--------|-------|---------|
| python3.8     | ✓      | ✓     | Supported |
| python3.9     | ✓      | ✓     | Supported |
| python3.10    | ✓      | ✓     | Supported |
| python3.11    | ✓      | ✓     | Supported |
| python3.12    | ✓      | ✓     | Supported |
| python3.13    | ✓      | ✓     | Supported |

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
