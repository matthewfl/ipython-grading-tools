# Github classroom helper

This directory contains the helper script that I developed to manage github
classroom for [seq2class](https://seq2class.github.io/).

## Review of features provided by github classroom
We tried github classroom for seq2class as it looks like an interesting platform
as it allows for using git repositories as a tool to collect student repos.
Github classroom only really provides **one** feature, and that is the
automatic creation of private repos for every student and importing the base
code into each repository.  Outside of that one feature, everything else seems
overly simplistic for even the *common* use case.  For example, management of
student names is upload a single text field in a CSV format.  Then students can
select themselves out of a drop down menu from the names of the entire class.
If you are trying to respect even the most basic student privacy rules, then
this solution is not workable.  To collect the assignments, github classroom has
support for logging which commit was in a repo at the time of a deadline.  (This
is sufficient to ensure that something was submitted in time) However, github
classroom only allows for a single deadline (no late day management).  Also the
what revision was present in the repo is only accessible through the web
interface of the classroom tool instead of any API afaik.

When it comes to grading, there is no support for bulk grading or tracking
scores along the way.  Their suggested method (at least on their help
documentation) is to just create a file in each repository using the web
interface and then write comments in that (aka, hard to scale and manage).
There is also no builtin support for autograding, so you also have to handroll
that.

TL;DR: github classrooms provides **one** feature: creating private repos.
Everything else you will have to hand roll.  In general, I don't think I would
suggest using it again without integration it with another platform (maybe
gradescope integration might work, idk) as there are just too many missing
features and it does not seem like there is much effort going towards increasing
the set of features vs minor bug fixes, however it
is [open source](https://github.com/education/classroom) so you can always add
features *yourself*.


## What is this script:

This script it trying to fill the gaps between what github classroom's offered
and what is required to manage a classroom at a *basic* level.  This script
contains actions to 1) clone all the student's repos, 2) create basic feedback
files for grading and incorporate the output from the autograder (also contained
in this repo), 3) run a grading loop by opening files in emacs in a random order
to implement "blind" grading 4) tally the scores and return the scores back to
the students by pushing into their private github repos.

(Again, I don't suggest using this script as a stopgap that evolved naturally to
fill the holes in github classroom.)
