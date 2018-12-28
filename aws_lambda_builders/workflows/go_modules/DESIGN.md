## Go - Go Modules Lambda Builder

### Scope

This package leverages standard Go tooling available as of Go1.11 to build Go
applications to be deployed in an AWS Lambda environment. The scope of this
builder is to take an existing directory containing customer code, and a
top-level `go.mod` file specifying third party dependencies. The builder will
run `go build` on the project and put the resulting binary in the given
artifacts folder.

### Interface

The top level interface is presented by the `GoModulesBuilder` class. There
will be one public method `build`, which takes the provided arguments and
builds a static binary using standard go tools.

```python
def build(self, source_dir_path, artifacts_dir_path, ui=None, config=None):
    """Builds a go project into an artifact directory.

    :type source_dir_path: str
    :param source_dir_path: Directory with the source files.

    :type artifacts_dir_path: str
    :param artifacts_dir_path: Directory to write dependencies into.

    :type executable_name: str
    :param executable_name: Name of the executable to create from the build.

    :type ui: :class:`lambda_builders.utils.UI` or None
    :param ui: A class that traps all progress information such as status
        and errors. If injected by the caller, it can be used to monitor
        the status of the build process or forward this information
        elsewhere.

    :type config: :class:`lambda_builders.utils.Config` or None
    :param config: To be determined. This is an optional config object
        we can extend at a later date to add more options to how modules is
        called.
    """
```

### Implementation

The general algorithm for preparing a Go package for use on AWS Lambda
is very simple. It's as follows:

Pass in GOOS=linux and GOARCH=amd64 to the `go build` command to target the
OS and architecture used on AWS Lambda. Let go tooling handle the
cross-compilation, regardless of the build environment. Move the resulting
static binary to the artifacts folder to be shipped as a single-file zip
archive.
