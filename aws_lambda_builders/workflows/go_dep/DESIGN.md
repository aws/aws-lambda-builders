### Go-Dep Lambda function builder
Building Lambda functions written in Golang is very straightforward. We use the `dep` dependency manager and 
`go` tool to install dependencies and cross-compile the function for architecture that Lambda supports.


The workflow does the following:
1. Check for manifest **Gopkg.toml**
2. Install dependencies using `dep ensure -v`
3. Compile using `GOOS=linux GOARCH=amd64 go build -ldflags="-s -w" -o $ARTIFACT_DIR/$HANDLER $SOURCE_DIR`
4. `chmod a+x $ARTIFACT_DIR/$HANDLER`

#### Challenges
1. **Handler name**: Since the binary must be named after the handler, we have modify the base workflow to pass 
handler name to the workflow
2. **Artifact File**: Unlike other workflows, the built artifact is the entire directory. But it is a specific file
within the directory. We need to modify the base workflow to let specific workflows provide the path to artifact file
that will be sent through output.


