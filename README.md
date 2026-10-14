# btc-core-aux-mat
utility scripts i use to speed up work on Bitcoin Core.

now, this tool is _heavily_ opinionated because it is optimised for the areas i work on in bitcoin core. but... as time progresses, i will be venturing into various new (from my POV) areas of the project, thus adding more code and files to this repo.

i respect the time it takes to gain experience in sth. i could use LLMs to expand into new areas every day, but "_what's the point?_" _you cannot cheat experience_ (sth a close friend of mine always reminds me of whenever he sees people cheating their way to the top with sth as questionable as an LLM). by that reasoning, you should take the stairs when learning anything new, so that the brain has time to build the neural pathways it can always invoke when similar situations that require them engulf you. so, that is why you find that i am too slow to add features here.

## usage

just run (there's _one_ tool right now):
```sh
./build-and-test-pr.py -h
```

you will see what you need. here's an example output:
```text
$ ./build-and-test-pr.py -h
usage: build-and-test-pr.py [-h] [-n] [-u] [pr_number] {http,tor,psbt}

Fetch, checkout, build and test a Bitcoin Core PR for a given subsystem {http,tor,psbt}.

positional arguments:
  [pr_number] {http,tor,psbt}
                        Pull request number (e.g. 12345) followed by the subsystem to test, one of: http, tor, psbt.
                        With -n/--no-git only the subsystem is given.

options:
  -h, --help            show this help message and exit
  -n, --no-git          Skip all git operations (fetch/checkout) and just configure, build and test whatever is
                        currently checked out. The PR number is not needed in this mode.
  -u, --update          PR branch already exists locally; force-fetch the latest commits from the author and reset
                        pr-<pr_number> to them instead of creating it fresh.
```
