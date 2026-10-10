#!/usr/bin/env python3

"""
pr_review.py - Fast local review helper for Bitcoin Core PRs.

Fetches a PR from upstream, checks it out into a dedicated branch, then
configures/builds with CMake and runs the unit + functional tests relevant
to the chosen subsystem (http, tor, psbt).

Works on Linux, FreeBSD and NetBSD (assumes `git`, `cmake`, `clang`/`clang++`
and a Python 3 interpreter for the functional test runner are on PATH).
"""

import argparse
import shlex
import subprocess
import sys
from enum import Enum

CMAKE_BASE = [
    "cmake",
    "-B",
    "build",
    "-DCMAKE_C_COMPILER=clang",
    "-DCMAKE_CXX_COMPILER=clang++",
    "-DCMAKE_BUILD_TYPE=Debug",
    "-DENABLE_IPC=OFF",
    "-DCMAKE_CXX_FLAGS_DEBUG=-O0 -ggdb3",
    "-DBUILD_GUI=OFF",
    "-DBUILD_BENCH=OFF",
    "-DBUILD_FOR_FUZZING=OFF",
    "-DBUILD_KERNEL_LIB=OFF",
    "-DBUILD_SHARED_LIBS=OFF",
    "-DBUILD_TESTS=ON",
    "-DBUILD_TX=OFF",
    "-DBUILD_UTIL=OFF",
    "-DBUILD_WALLET_TOOL=OFF",
]

BUILD_CMD = [
    "cmake",
    "--build",
    "build",
    "-j",
    "10",
    "--target",
    "test_bitcoin",
    "bitcoind",
    "bitcoin-cli",
]


class Subsystem(Enum):
    HTTP = "http"
    TOR = "tor"
    PSBT = "psbt"

    @property
    def boost_test(self) -> str:
        return {
            Subsystem.HTTP: "httpserver_tests,netbase_tests",
            Subsystem.TOR: "torcontrol_tests",
            Subsystem.PSBT: "psbt_tests",
        }[self]

    @property
    def functional_test(self) -> str:
        return {
            Subsystem.HTTP: "interface_http interface_bitcoin_cli rpc_bind",
            Subsystem.TOR: "feature_torcontrol",
            Subsystem.PSBT: "rpc_psbt",
        }[self]


def run(cmd, **kwargs) -> None:
    """Run a command, streaming output live, and abort on failure."""

    print(f"\n$ {' '.join(shlex.quote(c) for c in cmd)}\n", flush=True)
    result = subprocess.run(cmd, **kwargs)
    if result.returncode != 0:
        print(
            f"\n[FAILED] Command exited with code {result.returncode}: "
            f"{' '.join(cmd)}",
            file=sys.stderr)
        sys.exit(result.returncode)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch, checkout, build and test a Bitcoin Core PR "
        "for a given subsystem (http, tor, psbt).")

    parser.add_argument(
        "pr_number",
        type=int,
        help="Pull request number, e.g. 12345",
    )

    parser.add_argument(
        "subsystem",
        type=str,
        choices=[s.value for s in Subsystem],
        help="Subsystem to test",
    )

    parser.add_argument(
        "-u",
        "--update",
        action="store_true",
        help="PR branch already exists locally; force-fetch the latest "
        "commits from the author and reset pr-<pr_number> to them "
        "instead of creating it fresh.",
    )

    args = parser.parse_args()
    if args.pr_number <= 0:
        parser.error("pr_number must be a positive integer")
    return args


def fetch_and_checkout(pr_number: int) -> None:
    branch = f"pr-{pr_number}"
    run(["git", "fetch", "upstream", f"pull/{pr_number}/head:{branch}"])
    run(["git", "checkout", branch])


def update_checkout(pr_number: int) -> None:
    """Pull in new commits the PR author has pushed since the initial fetch.

    Mirrors: git checkout master && git fetch upstream +pull/<n>/head:pr-<n>
    && git checkout pr-<n>
    The leading '+' forces the local pr-<n> branch to be reset to whatever
    upstream currently has, even if history was rewritten (force-push).
    """

    branch = f"pr-{pr_number}"
    run(["git", "checkout", "master"])
    run(["git", "fetch", "upstream", f"+pull/{pr_number}/head:{branch}"])
    run(["git", "checkout", branch])


def configure_build_and_test(subsystem: Subsystem) -> None:
    run(CMAKE_BASE)
    run(BUILD_CMD)
    run(["./build/bin/test_bitcoin", f"--run_test={subsystem.boost_test}"])
    run(["./build/test/functional/test_runner.py", subsystem.functional_test])


def main() -> None:
    args = parse_args()
    pr_number = args.pr_number
    subsystem = Subsystem(args.subsystem)
    if args.update:
        update_checkout(pr_number)
    else:
        fetch_and_checkout(pr_number)

    configure_build_and_test(subsystem)
    print(f"\n✅ PR #{pr_number} ({subsystem.value}) built and tests passed.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(130)
    except Exception as e:
        print("\nUnexpected error: ", e, file=sys.stderr)
        sys.exit(1)
