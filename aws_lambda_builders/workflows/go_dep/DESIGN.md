# Go Dep - Lambda Builder

## Scope
Building Go projects using the dep tool (https://github.com/golang/dep) is rather simple, if you was to do
this by hand, you would perform these commands:

For x86 architecture

    - `dep ensure`
    - `GOOS=linux GOARCH=amd64 go build -o handler main.go`
    - `zip -r source.zip`

Or for ARM architecture

    - `dep ensure`
    - `GOOS=linux GOARCH=arm64 go build -o handler main.go`
    - `zip -r source.zip`

The scope of the Go dep builder is to create a macro for these commands to ensure that spelling and paths are correct.
We don't have to care about versioning of the tooling of either Go or dep since Lambda doesn't have to care, and so it becomes
user preference.

## Implementation
The go-dep builder runs the above commands with some minor tweaks, the commands ran on behalf of the user are:

For x86 architecture:

    1. dep ensure
    2. GOOS=linux GOARCH=amd64 go build -o $ARTIFACT_DIR/$HANDLER_NAME $SOURCE_DIR

For ARM architecture:

    1. dep ensure
    2. GOOS=linux GOARCH=arm64 go build -o $ARTIFACT_DIR/$HANDLER_NAME $SOURCE_DIR

The main difference being we want to capture the compiled binary to package later, so the binary has the
output path as the artifact dir set by the caller.

## Challenges
There are no challenges for go building, most problems have been abstracted away by the Go tooling

## Notes
Go does native cross-compilation regardless of what's compiling it. Regardless of how the user builds their code it would run on
AWS Lambda.

### Layers
This pattern might not work for Layers, plugins for go require an extra compilation flag (`-buildmode=plugin`), this would be something
to add later on, should SAM CLI support building layers