# Duplicate and noise review (for an independent subagent)

You are reviewing a functional spec written by another agent. You did not
write it, and that is the point: read it as its readers will. The readers are
listed in its Readers section.

You are given the spec directory, and a list of sentence pairs the check
script flagged as possible duplicates. Optionally, a list of sections to
limit the review to.

## What to do

Edit `spec.md` in place. Make three kinds of cut:

1. **Repeated facts.** The same fact said in two places. Keep it in the
   section that owns it, replace the other occurrence with a link to it, or
   delete it if the sentence around it still reads without it. Owners:

   | Fact | Owner |
   |---|---|
   | field, type, constraint, default | Entities |
   | cardinality, ownership, delete behaviour | Relations |
   | state, transition, trigger, guard, side effect | Lifecycles |
   | rule, limit, permission, calculation, flag | Decisions |
   | order of calls across modules | Flows |
   | what a page shows and lets the user do | Pages |

   Diagrams and the prose beside them: the table or list keeps the details
   the diagram cannot show (guards, side effects, links); delete prose that
   only narrates the diagram.

2. **Sentences that change nothing for the reader.** Restated headings,
   introductions ("本节介绍…"), summaries of what was just said, transitions,
   explanations of self-explanatory field names, hedges that add no
   information, descriptions of code structure the reader does not need.

3. **Over-long phrasing.** Shorten a sentence when a shorter one says the
   same. Do not rewrite for style.

## What not to do

- Do not delete a fact that appears nowhere else.
- Do not remove or change evidence links, quotes, 〔推断〕/〔未知〕 markers,
  section markers or prototype markers. When you merge two occurrences, keep
  every link the surviving sentence needs.
- Do not move content between As-is and Proposals.
- Do not add content, opinions or new facts.
- Do not touch `changes.md`.

## Return

A list, one line per cut: location (`spec.md:<line>` before your edit), kind
(repeat / noise / shorten), and what was removed or where it now links. End
with the number of lines before and after.
