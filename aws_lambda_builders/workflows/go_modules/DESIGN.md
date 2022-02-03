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
def build(self, source_dir_path, artifacts_dir_path, executable_name):
    """Builds a go project onto an output path.

    :type source_dir_path: str
    :param source_dir_path: Directory with the source files.

    :type output_path: str
    :param output_path: Filename to write the executable output to.
```

### Implementation

The general algorithm for preparing a Go package for use on AWS Lambda
is very simple. It's as follows:

Depending on the architecture pass in either:
 
 - `GOOS=linux and GOARCH=arm64` for ARM architecture or

 - `GOOS=linux and GOARCH=amd64` for an X86 architecture

to the `go build` command to target the
OS and architecture used on AWS Lambda. Let go tooling handle the
cross-compilation, regardless of the build environment. Move the resulting
static binary to the artifacts folder to be shipped as a single-file zip
archive.
