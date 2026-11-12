"""
Derive a workspace member's production dependency closure from a lockfile, with no npm subprocess.

Replaces `npm ls --all --parseable --omit=dev` for the #933 artifact-narrowing step, and answers the
same shape: absolute real paths, one per resolved package. None means the caller should ask npm.

Reads npm's HIDDEN lockfile, `node_modules/.package-lock.json`, not the project's own: only the hidden
one records the tree npm reified. See aws/aws-lambda-builders#938.
"""

import json
import logging
import os
from typing import Dict, List, Optional, Set, Tuple

LOG = logging.getLogger(__name__)

# lockfileVersion 1 predates the per-path `packages` map this resolver reads
MINIMUM_LOCKFILE_VERSION = 2

# npm's record of the tree it reified, written on every install from npm 7 on
HIDDEN_LOCKFILE = os.path.join("node_modules", ".package-lock.json")


def hidden_lockfile_path(project_root: str) -> str:
    """Where npm records the tree it installed under `project_root`."""
    return os.path.join(project_root, HIDDEN_LOCKFILE)


def _describes_the_installed_tree(project_root: str) -> bool:
    """
    Is npm's hidden lockfile still a true record of `node_modules`?

    npm's own staleness test, which it applies before trusting the file itself. `>=`, not `>`: a fresh
    install writes both in one clock tick. See aws/aws-lambda-builders#938.
    """
    try:
        hidden = os.path.getmtime(hidden_lockfile_path(project_root))
        tree = os.path.getmtime(os.path.join(project_root, "node_modules"))
    except OSError:
        return False
    return hidden >= tree


def _resolve_key(packages: Dict, from_key: str, name: str) -> Optional[str]:
    """
    Find the packages-map key that `name` resolves to when required from `from_key`.

    Walks up looking for `node_modules/<name>` the way node does. `from_key` is "" at the root,
    else a member path like "endpoints/orders" or "node_modules/express".
    """
    prefix = from_key
    while True:
        candidate = f"{prefix}/node_modules/{name}" if prefix else f"node_modules/{name}"
        if candidate in packages:
            return candidate
        if not prefix:
            return None
        # strip one path segment and try again, which is what walking up node_modules means
        prefix = prefix.rsplit("/", 1)[0] if "/" in prefix else ""
        if prefix.endswith("/node_modules"):
            prefix = prefix[: -len("/node_modules")]


def _entry_dir(project_root: str, key: str, entry: Dict) -> str:
    """The directory a packages-map entry lives in."""
    # a workspace link points at the real source directory rather than the link's own path
    if entry.get("link") and entry.get("resolved"):
        return os.path.join(project_root, *entry["resolved"].split("/"))
    return os.path.join(project_root, *key.split("/")) if key else project_root


def _lockfile_packages(project_root: str) -> Optional[Dict]:
    """
    The packages map of whichever lockfile under `project_root` parses, hidden one first.

    No staleness gate, unlike `production_closure`: this is read for `dev` markers only, and which
    packages a project declares as dev survives a tree the hidden lockfile no longer describes.
    """
    candidates = [hidden_lockfile_path(project_root)] + [
        os.path.join(project_root, name) for name in ("npm-shrinkwrap.json", "package-lock.json")
    ]
    for path in candidates:
        try:
            with open(path) as handle:
                lock = json.load(handle)
        except (OSError, ValueError):
            continue
        if lock.get("lockfileVersion", 1) >= MINIMUM_LOCKFILE_VERSION and "packages" in lock:
            return lock["packages"]
    return None


def _declared_dev_dependencies(directory: str) -> Set[str]:
    """The names in one manifest's `devDependencies`, empty when it cannot be read."""
    try:
        with open(os.path.join(directory, "package.json")) as handle:
            return set(json.load(handle).get("devDependencies") or {})
    except (OSError, ValueError, AttributeError):
        return set()


def dev_packages(project_root: str, install_dir: str) -> Tuple[Set[str], Set[str]]:
    """
    What is installed only for development, as `(real directories, package names)`.

    For the shared install at a workspace root, which keeps dev dependencies on purpose - the root's
    own build tools have to survive it - so that the artifacts can still leave them out.

    A lockfile answers by directory, and answers properly: it marks an entry `dev` when every path to
    it runs through a devDependency, so transitive ones are covered too. Without a usable lockfile
    only the manifests' own declarations are known, and those answer by NAME: npm hoists a workspace
    member's dev dependency to the root, so the directory it ends up in is not one this can predict.
    """
    packages = _lockfile_packages(project_root)
    if packages is not None:
        dev_dirs = {
            os.path.realpath(_entry_dir(project_root, key, entry))
            for key, entry in packages.items()
            if key and entry.get("dev")
        }
        return dev_dirs, set()

    LOG.debug("NODEJS no usable lockfile under %s; excluding only the manifests' own dev dependencies", project_root)
    dev_names = _declared_dev_dependencies(project_root) | _declared_dev_dependencies(install_dir)
    return set(), dev_names


def production_closure(project_root: str, install_dir: str) -> Optional[List[str]]:
    """
    The production dependency closure of `install_dir`, as absolute directories.

    None when the hidden lockfile cannot answer: absent, stale, too old a version, unreadable, or
    silent about this install directory.
    """
    if not _describes_the_installed_tree(project_root):
        LOG.debug("NODEJS no current hidden lockfile under %s; asking npm instead", project_root)
        return None

    try:
        with open(hidden_lockfile_path(project_root)) as handle:
            lock = json.load(handle)
    except (OSError, ValueError):
        return None

    if lock.get("lockfileVersion", 1) < MINIMUM_LOCKFILE_VERSION or "packages" not in lock:
        return None

    packages = lock["packages"]
    project_root = os.path.realpath(project_root)
    rel = os.path.relpath(os.path.realpath(install_dir), project_root).replace(os.sep, "/")
    start = "" if rel == "." else rel
    if start not in packages:
        return None

    # a link entry for a workspace member carries no dependencies; its source entry does
    def deps_of(key: str) -> Dict[str, str]:
        entry = packages.get(key) or {}
        if entry.get("link") and entry.get("resolved"):
            entry = packages.get(entry["resolved"], entry)
        # Production only. Peers included because npm 7+ installs them and `npm ls --all` walks them;
        # a declined optional peer is dropped by the on-disk check below.
        out = dict(entry.get("dependencies") or {})
        out.update(entry.get("optionalDependencies") or {})
        out.update(entry.get("peerDependencies") or {})
        return out

    found: Set[str] = set()
    stack = [start]
    while stack:
        key = stack.pop()
        for name in deps_of(key):
            resolved = _resolve_key(packages, key, name)
            if resolved is None or resolved in found:
                continue
            entry = packages[resolved]
            if entry.get("dev"):
                continue
            found.add(resolved)
            # resolve a link's dependencies from its source directory, as node does through the real
            # path: walking up from the link would find a hoisted copy the source nests
            if entry.get("link") and entry.get("resolved"):
                stack.append(entry["resolved"])
            else:
                stack.append(resolved)

    # Keep only what is on disk, as npm ls does: an optional dependency excluded by os/cpu/libc is
    # listed but not installed.
    dirs = set()
    for key in found:
        directory = _entry_dir(project_root, key, packages[key])
        if os.path.isdir(directory):
            dirs.add(directory)
        else:
            LOG.debug("NODEJS lockfile lists %s but it is not installed; leaving it out", key)
    # npm --parseable prints these too and the caller filters them, so emit them for parity
    dirs.add(project_root)
    dirs.add(os.path.realpath(install_dir))
    return sorted(dirs)
