# Ruby - Lambda Builder

## Scope

For the basic case, building the dependencies for a Ruby Lambda project is very easy:

```shell
# ensure you are using Ruby 2.5, for example with rbenv or rvm
bundle install # if no Gemfile.lock is present
bundle install --deployment
zip -r source.zip * # technically handled by `sam package`
```

The basic scope of a `sam build` script for Ruby would be as a shortcut for this, while performing some housekeeping steps:

- Skipping the initial `bundle install` if a Gemfile.lock file is present.
- Ensuring that `ruby --version` matches `/^ ruby 2\.5\./`
- Raising a soft error if there is already a `.bundle` and `vendor/bundle` folder structure, and giving an option to clobber this if desired.
  - I don't want this to be a default behavior, in case users are using the `vendor` or `.bundle` folder structures for other things and clobbering it could have destructive and unintended side effects.

Having a unified command also gives us the ability to solve once the most common issues and alternative use cases in a way that follows best practices:

1. Including dependencies that have native extensions, and building them in the proper environment.
   - An open question is how to help users represent binary dependencies, but that's not a Ruby concern per se so it should be solved the same way across all builds.
2. Building and deploying the user dependencies as a layer rather than as part of the code package.
   - These also have slightly different folder pathing:
     - Bundled dependencies are looked for in `/var/task/vendor/bundle/ruby/2.5.0` which is the default result of a `bundle install --deployment` followed by an upload.
     - Layer dependencies are looked for in `/opt/ruby/gems/2.5.0`, so for a layer option would have to use a `--path` build or transform the folder structure slightly.
3. Down the road, perhaps providing a way to bundle code as a layer, such as for shared libraries that are not gems. These need to go in the `/opt/ruby/lib` folder structure.

## Challenges

- Ensuring that builds happen in Ruby 2.5.x only.
- Ensuring that builds that include native extensions happen in the proper build environment.

## Interface/Implementation

Off hand, I envision the following commands as a starting point:
- `sam build`: Shorthand for the 2-liner build at the top of the document.
- `sam build --use-container`: Provides a build container for native extensions.

I also envision Ruby tie-ins for layer commands following the same pattern. I don't yet have a mental model for how we should do shared library code as a layer, that may be an option that goes into `sam init` perhaps? Like `sam init --library-layer`? Layer implementations will be solved at a later date.

Some other open issues include more complex Gemfiles, where a user might want to specify certain bundle groups to explicitly include or exclude. We could also build out ways to switch back and forth between deployment and no-deployment modes.

### sam build

First, validates that `ruby --version` matches a `ruby 2.5.x` pattern, and exits if not. When in doubt, container builds will not have this issue.

```shell
# exit with error if vendor/bundle and/or .bundle directory exists and is non-empty
bundle install # if no Gemfile.lock is present
bundle install --deployment
```

This build could also include an optional cleanout of existing `vendor/bundle` and `.bundle` directories, via the `--clobber-bundle` command or similar. That would behave as follows:

```shell
rm -rf vendor/bundle*
rm -rf .bundle*
bundle install # if no Gemfile.lock is present
bundle install --deployment
```

### sam build --use-container

This command would use some sort of container, such as `public.ecr.aws/sam/build-ruby2.7`.

```shell
# exit with error if vendor/bundle and/or .bundle directory exists and is non-empty
bundle install # if no Gemfile.lock is present
docker run -v `pwd`:`pwd` -w `pwd` -i -t $CONTAINER_ID bundle install --deployment
```

This approach does not need to validate the version of Ruby being used, as the container would use Ruby 2.5.

This build could also include an optional cleanout of existing `vendor/bundle` and `.bundle` directories, via the `--clobber-bundle` command or similar. That would behave as follows:

```shell
rm -rf vendor/bundle*
rm -rf .bundle*
bundle install # if no Gemfile.lock is present
docker run -v `pwd`:`pwd` -w `pwd` -i -t $CONTAINER_ID bundle install --deployment
```
