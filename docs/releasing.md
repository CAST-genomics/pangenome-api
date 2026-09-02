# Releasing: `release` is the branch that's live

> ## ⚠️ Not what the server is doing, as of 2026-09-02
>
> **The live server runs `main`.** `release` is 71 commits behind and is no longer a claim
> about anything.
>
> **Why, and it is not drift.** There is one server and one port. The hosting facility does
> not offer a second port, so there is no way to stand up an in-development instance beside
> the live one — the only way to exercise a change against real graph data is to point the
> live server at `main` for a window. That is what happened on 2026-08-31 for increment B and
> again on 2026-09-02 so that `pgb` could read the band format. The second window did not
> end, partly because confidence in `main` kept growing and partly because nothing forced it
> to.
>
> **That constraint is an argument for this document, not against it.** A testing window
> needs a way home, and `release` is the way home. What has gone wrong is not the discipline
> but the gap: `release` points at a commit nobody has run since August, so the rollback in
> *Rolling back* would replace working code with the 120-second version. **Fix that first,
> whatever else is decided** — promote `release` to `main`'s tip, which changes nothing about
> what is running and costs one fast-forward.
>
> **Then the standing decision**, which is a human one: switch the server back to tracking
> `release` (this document applies unchanged, and the banner comes out), or accept that
> `main` is what deploys and rewrite this around tags — see *What this deliberately isn't,
> yet*, whose reason for ruling tags out is weaker now that milestone tags exist anyway
> (`increment-b`, `increment-c`).
>
> **Worth one question before accepting the constraint:** if anything fronts the API — nginx,
> Apache, a campus proxy — a path prefix or a second hostname on the existing `:8000` gives
> the same isolation without a new port. Facilities usually restrict inbound ports rather
> than processes.
>
> Meanwhile **rule 2 below still binds**: nobody commits on the server. A server checkout of
> `main` that has drifted is worse than one of `release` that has, because there is no second
> branch to diff it against.

A small change to how the API gets deployed, and the first step toward doing releases
properly. Doug and Cici both work off this document.

**The change in one sentence:** the server stops following `main` and starts following a
branch called `release`, so that merging something is no longer the same act as shipping
it.

---

## Why

Right now the deploy is:

```sh
git checkout main
git pull
# restart the API
```

Which means **production isn't a branch, it's a moment.** What's running on the server is
whatever `main` happened to be the last time somebody pulled — and afterwards there's no
way to reconstruct which commit that was. Two consequences, both of which have teeth:

- Anything merged to `main` ships on the next pull, even a pull done for an unrelated
  reason. Merging is deploying, whether or not anybody meant it that way.
- There's nothing to roll back *to*. "Put back what was working this morning" has no
  answer, because nothing recorded what was working this morning.

With a `release` branch, `main` becomes "merged and tested" and `release` becomes "this is
what's live". Promotion between the two is a thing somebody does on purpose.

---

## One-time setup

### Doug — create the branch

Point `release` at whatever is deployed today. If the server is up to date with `main`,
that's just:

```sh
git checkout main
git pull
git branch release
git push -u origin release
```

If the server is *behind* `main` — likely, if anything has been merged since the last
deploy — then create `release` at the commit that's actually running instead. Ask Cici for
it:

```sh
# on the server, in the repo directory
git rev-parse HEAD
```

and then, locally:

```sh
git branch release <that-commit>
git push -u origin release
```

Getting this right matters more than getting it done fast: `release` is a claim about
what's live, and it should be true from its first commit.

### Cici — point the server at it

Once, on the server, in the repo directory:

```sh
git fetch origin
git checkout release
```

That's the whole change on your end. Check it took:

```sh
git branch --show-current   # should print: release
```

---

## Deploying, from then on

**Cici — this is unchanged from what you do today**, except that the branch is `release`
instead of `main`:

```sh
git pull
# restart the API the way you normally do
```

The restart still matters — until the process restarts, it's running the old code.

If `git pull` ever says something other than "Fast-forward" or "Already up to date" —
anything mentioning a merge, a conflict, or diverged branches — **stop and ping Doug.** It
means the server has picked up a change of its own somehow, and pulling on top of it will
make a mess that's easier to prevent than to unpick.

## Promoting, from then on

**Doug — this is the new step**, and it's the point of the whole exercise. When something
on `main` is ready to be live:

```sh
git checkout main
git pull
git checkout release
git merge --ff-only main
git push
```

Then tell Cici there's something to pull.

`--ff-only` is deliberate. It fails rather than creating a merge commit, and if it fails
that's real information: `release` has something on it that `main` doesn't, which should
never happen and wants investigating rather than merging past.

### What's waiting to ship

```sh
git log release..main --oneline
```

Everything merged but not yet live. This is also the list to paste into a message to Cici
when you ask her to deploy.

### Rolling back

Because `release` has a history, the previous known-good commit now has a name:

```sh
git log release --oneline     # find the commit from before the bad deploy
git checkout release
git reset --hard <that-commit>
git push --force-with-lease
```

Then Cici re-deploys. On her side a rollback isn't a `git pull` — it needs:

```sh
git fetch origin
git reset --hard origin/release
# restart the API
```

`--force-with-lease` on a shared branch is a sharp tool, and rollback is the one situation
that justifies it. Tell Cici before you do it, not after.

---

## The rules that keep this honest

Three, and they're the difference between a release branch and a second name for `main`:

1. **`release` only ever fast-forwards from `main`.** Never commit to it directly, never
   cherry-pick onto it. If a fix needs to be live, it goes to `main` first and gets
   promoted — even the one-line ones, especially the one-line ones.
2. **Nobody commits on the server.** The server's checkout is a read-only mirror of
   `release` that happens to be writable. If something needs editing to make the server
   work, that's a change to the repo.
3. **`main` stays deployable.** Nothing goes onto `main` that we wouldn't be willing to
   promote. Work that isn't ready lives on its own branch until it is.

## What this deliberately isn't, yet

- **No tags.** Immutable, named deploy artifacts are the better end state, but they'd
  change the deploy procedure every single time instead of once. Worth revisiting when
  there's more than one place to deploy to.
- **No automation.** Nothing pushes to the server; deploying stays a thing a human does.
  This step is about making *what's live* legible, not about making it automatic.
- **No third branch.** No `development` tier. Once the server stops following `main`,
  `main` is the integration branch, and adding another one would just create a second
  place for changes to sit and drift.

The repo now runs its tests in CI on every pull request
([`.github/workflows/ci.yml`](../.github/workflows/ci.yml)). Requiring those checks before
a merge into `main` is the natural companion to this change: it's what makes "merged to
`main`" mean "tested", which is what makes promoting to `release` a boring, safe act.
