// A strand's identity, as CONTEXT.md defines it.
//
// The triple `sample#haplotype#contig` is the whole of it. `vg` appends its own
// phase block and subrange — `sample#haplotype#contig#0[9659985-9661740]` — and
// that string travels the wire verbatim, because rewriting it would make this
// codebase's documents disagree with the tool that produced them. The tail is
// metadata riding on the identity; the codebase truncates back to the triple
// only where it looks something up, such as a PCLAI colour.
//
// This is the same rule as `truncateTrackName` in tubemap.js, which is where the
// layout applies it (`getPclaiEntry`, tubemap.js:2563). It lives here as well
// because tubemap.js cannot be imported without first standing up its config —
// it used to cost a jsdom window too — and a name is not a thing that should
// cost a layout engine.

/**
 * The `sample#haplotype#contig` triple a strand is identified by.
 *
 * A name with three components or fewer is already the identity and is returned
 * untouched — including its subrange, if it carries one. That is deliberate, and
 * it is what makes this agree with the layout: a PCLAI scheme is keyed by
 * whatever `truncateTrackName` produces, so a stricter rule here would look up
 * keys the layout never uses.
 */
export function strandIdentity(name) {
  if (!name) return name;
  const parts = name.split("#");
  return parts.length <= 3 ? name : parts.slice(0, 3).join("#");
}
