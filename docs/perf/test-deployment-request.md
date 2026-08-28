# A second copy of the API, for testing before we go live

Hi Cici — one thing to set up, and I think it's about 20 minutes. Nothing here touches the
live server.

- Rendered version, which is the one to send her: <https://claude.ai/code/artifact/ccfbbb63-c362-4cab-977d-78664278a6df>
- Source of the rendered version: [`test-deployment-request.html`](./test-deployment-request.html)

Anywhere below that says `<something>`, that's a placeholder for a real value on your end.
If a step doesn't work, stop and ping me rather than digging.

---

## What I'm asking for

A **second copy of the API running alongside the live one**, on a different port, using the
code from `main` instead of `release`.

That's the whole thing. It's the same deploy you already do, with two differences: it lives
in its own folder, and it answers on a different port number.

## Why

There's a batch of work waiting to go live — 33 commits, the biggest being a rewrite of how
the sequence tube map gets built. It's tested heavily, but all of that testing has been on
my laptop, where I don't have the real graph files or the `vg` program. There are parts of
the real pipeline I simply cannot run here.

Before we make it live, I want to open the browser app, click on actual nodes, and see real
pictures come back. Especially the big nodes that currently fail — right now roughly 4 in 10
give up before they finish, and this work is supposed to fix that. I'd like to find out
whether it did *before* it's in front of anyone else.

Once it's up I'll do that clicking myself. I just can't create the second copy.

## What it does and doesn't touch

- **It does not change the live server.** Different folder, different port, separate process.
- **It only reads the graph files.** Same ones the live server reads; it never writes to them.
- **It uses less memory than the live one**, not more — that's most of what this work did. The
  measurement is about 470 MB where the current code peaks around 2.4 GB on the same request.
- **It can be killed at any time** with no effect on the live server, and I'll tell you when
  we're done with it.

---

## The steps

### 1. Make a second folder with the code in it

Somewhere alongside the existing one — whatever you'd normally call it:

```sh
git clone https://github.com/CAST-genomics/PangenomeAPI.git <new-folder>
cd <new-folder>
git checkout main
```

It needs to be a **separate folder from the live server's**, not the same one switched over.
Two reasons: the live folder has to stay on `release` so nothing accidentally goes live, and
both copies write temporary files to the same place *relative to their own folder* and delete
them after each request — if they shared a folder they'd delete each other's files partway
through.

You shouldn't need to configure anything in the new folder. The settings that point at the
graph files are set once for your whole account, so a fresh copy picks them up on its own.

### 2. Install what it needs

Same as the live one:

```sh
npm ci
```

(If you install the Python packages per-folder rather than once for the machine, that too.)

### 3. Start it, the way you normally start the API — but on a different port

This is the step I can't write for you, because I don't know how you run it. However you
normally do it, the only change is the port number: **8100** instead of 8000, or any free port
you prefer.

- If you start it with a command that names the port, change the number.
- If it's a service definition or a compose file, copy it, change the port and the name.

It also needs HTTPS, the same way the live one gets it — the browser app won't talk to a copy
without it. The certificate you already have covers any port on the same address, so there's
nothing new to obtain; it just needs the same certificate settings the live one uses.

### 4. Tell me two things

- The port number you used.
- That it's running.

I'll check it myself from there and won't need anything else.

---

## What "working" looks like

If you want to confirm it before handing it over, this should print `200`:

```sh
curl -s -o /dev/null -w "%{http_code}\n" \
  "https://pangenome-api.ucsd.edu:<port>/seqtubemap?chrom=chr8&start=78771162&end=78771252&version=v2"
```

It may take a minute or two the first time — it has to pull that region out of the graph,
same as the live server does the first time anyone asks for it. Anything other than `200`,
send me what you got.

---

## One thing worth knowing, unrelated to this request

While going through the code I noticed something that isn't caused by this work but that this
work makes easier to hit. When two requests for the *same* region arrive at once and that
region hasn't been fetched before, both of them start fetching it and both write to the same
file. One of the changes waiting to go live makes the server handle requests at the same time
rather than one after another, so this becomes more likely than it is today.

I don't think it's a reason to hold anything up — it needs two people asking for the same new
region within seconds of each other. But you should hear it from me rather than meet it later.
It's written up as
[issue #54](https://github.com/CAST-genomics/PangenomeAPI/issues/54) if you ever want the
detail; there's nothing for you to do about it.

---

## When we're done

I'll tell you once I've clicked through enough to be confident. Then the second copy can be
shut down and its folder deleted, and we can talk about making the changes live properly —
which is the `release` branch procedure in [`releasing.md`](../releasing.md), not this.
