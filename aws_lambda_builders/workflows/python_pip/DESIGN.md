## Python - PIP Lambda Builder

### Scope

This package is an effort to port the Chalice packager to a library that can
be used to handle the dependency resilution portion of packaging Python code
for use in AWS Lambda. The scope for this builder is to take an existing
directory containing customer code, and a top-level `requirements.txt` file
specifying third party depedencies. The builder will examine the dependencies
and use pip to build and include the dependencies in the customer code bundle
in a way that makes them importable.

### Challenges

Python is particularly difficult to package for other platforms because it is
heavily coupled to your local environment. This is because `setup.py` the
"config" to describe an install is just a python file, which means authors can
run code to check things about your current system, and then use that to make
decisions about how to install the package. These decisions are obviously not
valid once we move the built package to a different platform.

Python packaging also has the concept of a wheel, which is more of a self
contained package that can be trivially installed into a python environment
and does not execute any code. Our goal is to build up a set of these that
are known to be compatible with AWS Lambda.

### Interface

The top level interface is presented by the `PythonPipDependencyBuilder`
class. There will be one public method `build_dependencies`, which takes
the provided arguments and builds python dependencies using pip under
the hood.

```python
def build_dependencies(artifacts_dir_path,
                       requirements_path,
                       runtime,
                       ui=None,
                       config=None,
                      ):
    """Builds a python project's dependencies into an artifact directory.

	:type artifacts_dir_path: str
	:param artifacts_dir_path: Directory to write dependencies into.

	:type requirements_path: str
	:param requirements_path: Path to a requirements.txt file to inspect
	    for a list of dependencies.

    :type runtime: str
    :param runtime: Python version to build dependencies for. This can
        either be python3.6, python3.7, python3.8 or python3.9. These are 
        currently the only supported values.

    :type ui: :class:`lambda_builders.actions.python_pip.utils.UI`
    :param ui: A class that traps all progress information such as status
        and errors. If injected by the caller, it can be used to monitor
        the status of the build process or forward this information
        elsewhere.

    :type config: :class:`lambda_builders.actions.python_pip.utils.Config`
    :param config: To be determined. This is an optional config object
        we can extend at a later date to add more options to how pip is
        called.
    """
```

### Implementation

The general algorithm for preparing a python package for use on AWS Lambda
is as follows.

#### Step 1: Install all dependencies with no restrictive settings

Let pip choose what to install, this gives us the best chance of getting
a complete closure over all the requirements from our `requirements.txt` file.
We will have a mixture of sdists and wheel files after this step. Pip prefers
wheels so the sdists will be present when we couldn't find a wheel. We now use
this directory full of sdists and wheels as our source of truth for a complete
list of all dependencies we need.

#### Step 2: Sort our dependencies by compatibility with AWS Lambda

Sort the downloaded packages into three categories:
* sdists (Pip could not get a wheel so it gave us an sdist)
* lambda compatible wheel files
* lambda incompatible wheel files

Pip will give us a wheel when it can, but some distributions do not ship with
wheels at all in which case we will have an sdist for it. In some cases a
platform specific wheel file may be availble so pip will have downloaded that,
if our platform does not match the platform defined for the lambda function
(linux/manylinux x86_64 or aarch64) then the downloaded wheel file may not be
compatible with lambda. Pure python wheels still will be compatible because
they have no platform specific dependencies.

#### Step 3: Try to download a compatible wheel for each incompatible package

Next we need to go through the downloaded packages and pick out any
dependencies that do not have a compatible wheel file downloaded. For these
packages we need to explicitly try to download a compatible wheel file. A
compatible wheel file means one that is explicitly for marked as supporting the
corresponding architecture for the function.

#### Step 4: Try to compile wheel files ourselves

Re-count the wheel files after the second download pass. Anything that has an
sdist but not a valid wheel file is still not going to work on AWS Lambda and
we must now try and build the sdist into a wheel file ourselves as none was
available on PyPi in a compatible format.

#### Step 5: Try to compile wheel files without a C compiler

Re-count the wheel files after the custom compile pass. If there are still
dependencies that only have incompatible wheels or sdists all hope is not lost.

There is still the case where the package had optional C dependencies for
speedups. In this case the wheel file will have built above with the C
dependencies if it managed to find a C compiler. If we are on an incompatible
architecture this means the wheel file generated will not be compatible. Our
last ditch effort to build the package will be to try building it again while
severing its ability to find the C compiler. If the dependencies were optional
it will fall back to pure python and build a valid pure python wheel.

#### Step 6: Ignore packages that lie about their compatibility

Now there is still the case left over where the setup.py has been made in such
a way to be incompatible with python's setup tools, causing it to lie about its
compatibility. To fix this we have a hand-curated list of packages that will
work, despite claiming otherwise.

#### Step 7: Find any leftover unmet dependencies

At this point there is nothing we can do about any missing wheel files. We
tried downloading a compatible version directly and building from source. All
we can do here is report that we could not build this dependency and the bundle
is missing some dependencies.

#### Step 8: Unpack all valid wheel files into the target bundle

For each wheel file that has been built we install it into the target bundle
directory at the top level. This will make it importable assuming the top level
bundle has an `__init__.py` and is on the `PYTHONPATH`.

#### Step 9: Clean up temp directories

The dependencies should now be succesfully installed in the target directory.
All the temporary/intermediate files can now be deleting including all the
wheel files and sdists.
