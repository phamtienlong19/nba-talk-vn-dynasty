# incoming/

Drop zone for a new board HTML export before publishing it, e.g.:

```bash
cp ~/Downloads/new-board.html incoming/
./publish.sh incoming/new-board.html
```

Everything in this directory except this README is gitignored — nothing here
is committed. `publish.sh` also accepts a path directly from `~/Downloads`,
so using this directory is optional.
