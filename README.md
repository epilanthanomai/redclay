# redclay, a Georgia MUD

because the world desperately needs another mud engine

## useful dev commands

```console
# install local dev environment and start a subshell
$ pipenv install --dev
$ pipenv shell
# set up git hooks
$ pre-commit install
# run the tests
$ tox
# run the game
$ python -m redclay
# connect to the game (from another terminal)
$ telnet localhost 6666
```

## probably handy in your (local) .vimrc
```vim
augroup localblack
  autocmd BufWritePre *.py execute ':Black'
augroup END
```
