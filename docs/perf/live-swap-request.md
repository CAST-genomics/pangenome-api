# Running `main` on the live server for a short while

Hi Cici — this replaces what I sent you before. Please don't do the earlier one.

- Rendered version, which is the one to read: *(link to follow)*
- Source of the rendered version: [`live-swap-request.html`](./live-swap-request.html)

**What changed and why.** I'd asked for a second copy of the API on its own port, running
alongside the live one. That was written on the assumption we could open a second port, and
we can't. So I'm asking for something smaller in steps but more honest about what it touches:
**point the live server at `main` for a short while, look at it together, then put it back.**

I want to be straight about that up front. The earlier request promised it wouldn't touch the
live server. This one does — that's the whole of it. Everything below is about making it a
change you can undo in about thirty seconds, on your own, without me.

Anywhere below that says `<something>`, that's a placeholder for a real value on your end.
If a step doesn't work, stop and ping me rather than digging.

---

## What I'm asking for

Two commands on the server, a restart, and the same two commands in reverse when we're done.

```sh
git checkout main      # then restart
# ... we look at it ...
git checkout release   # then restart
```

That's genuinely it. No install step, no configuration, no new folder.

## Why there's no install step

This is the part that makes the whole thing safe, so it's worth a sentence.

Normally switching branches means reinstalling packages, and that's where a swap like this
would get risky — one of the packages the current code uses has to be compiled on the machine,
and if that compile ever failed we'd be stuck. **It doesn't apply here.** The new code uses
*fewer* packages than the current one, and every package it needs is already installed at the
same version. Nothing to install, nothing to compile, nothing to undo.

The Python side doesn't change at all.

So `node_modules` never gets touched, which means going back is only ever a checkout and a
restart.

## Why I'm asking

We've been rebuilding how the sequence tube map gets drawn, in deliberate increments, and the
big one just landed. It's tagged `increment-b` if you ever want the exact commit.

All of it is tested — there's an automated suite, and it checks the output byte for byte
against known-good copies. But every one of those tests runs on my laptop, where I don't have
the real graph files and don't have `vg`. There are parts of the real pipeline I simply cannot
run here, and no amount of local testing tells me about them.

What I want is to open the browser app against the real server and click on real regions,
especially the big ones that currently fail — roughly 4 in 10 give up before they finish today,
and this work is meant to fix exactly that. I want to find that out with you watching, on
purpose, for a bounded window, rather than discover it after we've made it live.

**This is a confidence-building step, not the release.** If it goes well, making it live is a
separate conversation and follows [`releasing.md`](../releasing.md) properly.

---

## The steps

### 1. Note where we are now, so we can prove we got back

```sh
git branch --show-current   # expect: release
git rev-parse --short HEAD
```

Send me those two lines, or just keep them somewhere. It's the "what was working this
morning" answer, and it takes five seconds.

### 2. Switch to `main`

```sh
git fetch origin
git checkout main
git pull
```

Then **restart the API** the way you normally do. The restart matters — until the process
restarts, it's still running the old code.

If `git checkout` or `git pull` says anything other than the usual — anything about a merge, a
conflict, uncommitted changes, or diverged branches — **stop and ping me.** Don't force it.
That would mean the server has a change of its own that I don't know about, and I'd want to
see it before we go any further.

### 3. Tell me it's up

That's all I need. I'll do the clicking from here.

---

## What "working" looks like

If you want to confirm it yourself before handing it over, this should print `200`:

```sh
curl -s -o /dev/null -w "%{http_code}\n" \
  "https://pangenome-api.ucsd.edu:8000/seqtubemap?chrom=chr8&start=78771162&end=78771252&version=v2"
```

It may take a minute or two the first time. Anything other than `200`, send me what you got
and put it back — step 4 below, don't wait for me.

---

## Putting it back

**You don't need my permission or my presence to do this.** If anything looks wrong, if
someone complains, or if you just want the server back on known ground — do it, then tell me.
I would much rather be interrupted than have you wait.

```sh
git checkout release
```

Then restart. Confirm it took:

```sh
git branch --show-current   # expect: release
git rev-parse --short HEAD  # expect: what you noted in step 1
```

That's the entire rollback. Because nothing was installed, removed, or configured, there's no
other state to unwind — the running code goes back to being exactly what it was.

---

## Two things you should hear from me first

**The logs will get noisy.** `main` still has debugging output in it that I haven't stripped
yet — it writes a memory reading every half second while a picture is being drawn, plus a
timing line at about twenty points through each one. It's harmless and it only goes to the
log, but if you look at the log during the trial you'll see a lot more than usual, and I don't
want you thinking something's wrong. It comes out before anything goes live
([issue #45](https://github.com/CAST-genomics/PangenomeAPI/issues/45)).

**A pre-existing rough edge this work makes easier to hit.** When two requests for the *same*
region arrive at once and that region hasn't been fetched before, both start fetching it and
both write to the same file. That's true today; `main` handles requests at the same time rather
than one after another, which makes it more likely. It needs two people asking for the same new
region within seconds of each other, so I don't think it's a reason to hold this up — but you
should hear it from me rather than meet it later.
[Issue #54](https://github.com/CAST-genomics/PangenomeAPI/issues/54) has the detail; there's
nothing for you to do about it.

---

## When we're done

I'll tell you once I've clicked through enough to be confident, and then you put it back with
step 4 — or you can put it back at any point before that for any reason at all.

If it goes as I expect, the next conversation is about promoting `main` to `release` properly,
which is the procedure in [`releasing.md`](../releasing.md) and is a different thing from this.
