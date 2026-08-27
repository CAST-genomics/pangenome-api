# What I need from the server

Hi Cici — two things, and they both come off the same deploy. Probably 15 minutes.

Anywhere below that says `<something>`, that's a placeholder for a real value on your end.
If a step doesn't work, stop and ping me rather than digging — none of this is worth your
afternoon.

---

## Task 1 — deploy a logging patch, then send me the log file

PR [#12](https://github.com/CAST-genomics/PangenomeAPI/pull/12) added timing printouts to
`/seqtubemap`. It's already merged into `main`, so there's no branch to switch to — the
server just needs to pull and restart. It only prints things; it doesn't change what the
endpoint returns.

### Step 1 — deploy it

On the server, from the repo directory:

```sh
git checkout main
git pull
```

Then **restart the API** the way you normally do. The restart matters — until the process
restarts, it's still running the old code and won't print anything.

### Step 2 — run three requests

Paste this whole block into a terminal (it can be your laptop or the server, either is
fine). It makes three requests, one after another, and prints a line for each.

```sh
BASE='https://pangenome-api.ucsd.edu:8000/seqtubemap'
OPTS='version=v2&pathnumoption=normal&nodewidthoption=compressed'

for R in 'chrom=chr8&start=78900000&end=78900090' \
         'chrom=chr8&start=78910000&end=78913000' \
         'chrom=chr8&start=78920000&end=78930000'; do
  curl -s -o /dev/null -w "%{http_code}  %{size_download} bytes  %{time_total}s\n" \
    "$BASE?$R&$OPTS"
done
```

Two things to expect:

- **It will look frozen.** The third request holds the whole API for about two minutes.
  That's a known bug I'm fixing separately, not something you did. Let it finish.
- **Three lines print out**, each starting with `200`. If you get a `500` or a `000`, send
  me what you got and stop there.

Because the API stalls while this runs, pick a moment when nobody else is using it.

### Step 3 — save the log and send it to me

Don't read it or filter it — I just want the raw file. Run these **in order** and stop at
the first one that produces a file with something in it:

```sh
# If the API runs under Docker:
docker compose logs api > ~/seqtubemap-log.txt

# If it runs under systemd:
journalctl -u <service-name> --since '2 hours ago' > ~/seqtubemap-log.txt

# If it writes to a log file somewhere, just copy that file:
cp <path-to-the-logfile> ~/seqtubemap-log.txt
```

Check it isn't empty:

```sh
wc -l ~/seqtubemap-log.txt
```

If that's `0`, try the next command in the list. If none of them work, tell me how the API
gets started on that machine and I'll figure out where the log goes.

Then send me `~/seqtubemap-log.txt` however is easiest — Slack, email, attached to the PR.
It's fine if it's big or full of unrelated stuff; I'll pull out what I need.

---

## Task 2 — five subgraph files

Same server, same idea: five requests, then copy five files. Do this *after* Task 1 so the
two don't overlap.

### Step 1 — request the five regions

Paste this block into a terminal. Same as before: one request at a time, `-o /dev/null`
throws away the picture, and a status line prints for each.

```sh
BASE='https://pangenome-api.ucsd.edu:8000/seqtubemap'
OPTS='version=v2&pathnumoption=normal&nodewidthoption=compressed'

for R in 'chrom=chr8&start=78771162&end=78771252' \
         'chrom=chr1&start=25331046&end=25331646' \
         'chrom=chr8&start=10079054&end=10080461' \
         'chrom=chr1&start=25301271&end=25309238' \
         'chrom=chr1&start=25331646&end=25335796'; do
  curl -s -o /dev/null -w "%{http_code}  %{size_download} bytes  %{time_total}s\n" \
    "$BASE?$R&$OPTS"
done
```

The last two are large regions and will each take a few minutes. Same as Task 1: the API is
unresponsive while they run, so pick a quiet moment. If a region has been requested before
it'll come back almost instantly — that's fine and actually saves time.

### Step 2 — copy the five files out

Each request leaves a `.gfa` file behind on the server, in the API's cache directory:

```sh
cd <the-repo-directory-on-the-server>/cache/seqtubemap/mc
ls -la subgraph_chr8_78771162_78771252_v2.gfa \
       subgraph_chr1_25331046_25331646_v2.gfa \
       subgraph_chr8_10079054_10080461_v2.gfa \
       subgraph_chr1_25301271_25309238_v2.gfa \
       subgraph_chr1_25331646_25335796_v2.gfa
```

All five should be listed, and none should be 0 bytes. If one is missing, its request in
Step 1 probably failed — re-run just that one and check again.

Then bundle them up:

```sh
tar czf ~/seqtubemap-subgraphs.tar.gz subgraph_chr8_78771162_78771252_v2.gfa \
                                      subgraph_chr1_25331046_25331646_v2.gfa \
                                      subgraph_chr8_10079054_10080461_v2.gfa \
                                      subgraph_chr1_25301271_25309238_v2.gfa \
                                      subgraph_chr1_25331646_25335796_v2.gfa
```

Send me `~/seqtubemap-subgraphs.tar.gz` — email, Drive, or just tell me it's on the server
and where, if it's too big to attach. I can take it from that file onward; everything else
in the pipeline I can regenerate myself.

---

Happy to jump on a call and do any of this together if that's easier than going back and
forth.

Thanks —
Doug
