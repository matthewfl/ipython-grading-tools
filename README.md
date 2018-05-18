# IPython notebook grading tools

This repository contains tools developed
for [seq2class](https://seq2class.github.io/) for dealing with IPython
notebooks.  This includes stripping answers from an IPython notebook to generate
student versions of the code as well as autograding.  These scripts are loosely
based off the ideas presented
in [nbgrader](https://github.com/jupyter/nbgrader), however that is more of a
"full fledged" classroom management system and requires that students also
install custom plugins.  These scripts on the other hand are "loosely coupled"
and do not require that students install any additional software outside of the
typical ipython notebook.  This means that these scripts are potentially good
for adapting into an autograder for a platform like gradscope.

Each script is fairly small (~100 LOC) and thus should be easily modifiable to
suite the needs of any class.

Additionally, there is a set of utilities for with github (classroom) with
support for bulk pulling repos and returning the grades in the form of markdown
files.  That script was specialized for seq2class, however it should be easy to
modify.

## Features
1. Prepossessing ipython notebooks to remove answers in code
2. Autograder written into same answer key to make a single document to manage / maintain
3. Allow for changing the definition of the autograder after an assignment has been released
3. Autograder support specialized for machine learning models
   1. timeouts that only interrupt the current cell, allows for limiting the amount of training on the autograding server while still checking that the training routines are coded correctly
   2. memory limits via interrupting a cell.  (prevents killing the entire process bur rather just the single part that was consuming too much memory)
   3. disable execution of some cells while performing autograding
4. Slice the Ipython notebooks to select out written prompts inside of the notebook.  Makes for faster grading of written questions


## Example
See the example folder for an example of how to structure an answer key as well
as what the resulting output will look like.  There is also an example
`Makefile` that can serve as a good base for managing ipython notebook tasks.

## Files
1. `add_cell_tracking.py` -- This modifies the passed notebook to add a UUID to
   every cell in the notebook.  You must apply this operation before releasing
   an Ipython notebook if you want to use the autograder.  The UUIDs are used to
   locate cells in the Ipython notebook during autograding and determine where
   autograding commands should be inserted into the resulting file.
2. `preprocesser.py` -- This creates a student version of the notebook, it
   removes all of the code between `### STUDENTS START` and `### STUDENTS END`
   and replaces it with a `NotImplemented() # REPLACE ME` exception and a
   comment to replace it.  It additionally removes any cell that contains `###
   AUTOGRADER` at the top.  If you are using the autograder, make sure that you
   apply `add_cell_tracking.py` to the answer-key file **before** applying the
   processor.
3. `nb_autograder.py` -- This file takes the student's answer and the answer key
   (with the autograding directives) and generates a new file to execute which
   represents the autograder.  The generated output **must** be executed using
   `ipython` instead of `python` as the conversion script will use various
   ipython magic when converting from the notebook format.
4. `nb_written.py` -- This will select out the written prompts inside of the
   student's notebook.  This is useful in the case that you release a *long*
   ipython notebook for the assignment and there are a few written prompts
   throughout the notebook.  This way you don't have to scroll through any of
   the instructions when grading the ipython notebook and only have to focus on
   the student's code.  The selected cells are surrounded with a cell
   containing: `### AUTOGRADER ### ANSWERS START` and `### AUTOGRADER ### ANSWERS END`.
5. `autograder.py` -- This file contains runtime code to in used while
   autograding.  When developing the autograder or writing the answer key, I
   suggest creating a symbolic link to this file from your working directory.
   At the top of your autograder script that you are writing, you should write
   `import autograder`.  If you are trying to integrate these scripts into your
   own autograding platform, presumably this is the script that you will want to
   modify to add your own functionality.
6. `Makefile` -- An example make file that automates the operations for
   distributing an assignment, can be used as a base for a Makefile for a class


## Common Commands
### Generating the student's version of the notebook
```bash
    python add_cell_tracking.py --notebook ../homework_1-answer.ipynb
    python preprocessor.py --input ../homework_1-answer.ipynb --output ../homework_1-student.ipynb
```

### Running the autograder
```bash
    # do this first to the answer key if you added any additional cells after releasing the notebook
    # do **not** do this again to the student's code
    python add_cell_tracking.py --notebook ../homework_1-answer.ipynb

    # generate code to execute as the autograder
    python nb_autograder.py --answer ../homework_1-answer.ipynb --student ../../student-submmited-code/homework_1-student.ipynb --output /tmp/running-directory/generated_autograder_code.py

    # copy any files that are required by the students code & autograder.py
    cp autograder.py /tmp/running-directory/

    # I perfer to use a different user account when running the student's code as this prevents them messing up the computer that
    # I am running the code on.  Additionally, setting ulimits and timeouts on the script itself is a good idea

    sudo -u limited-user -I <<EOF
    # this environment variable controls where the autograder.py script saves its output
    export AUTOGRADER_SAVE_FILE=/tmp/running-directory/autograder.json
    # don't want student's using threads in their code, so we set it here and in a few other places
    export OMP_NUM_THREADS=1
    # change to the directory where we copied the files so if there is code that does `open('foo')` it will have the right path
    cd /tmp/running-directory/
    # set ulimits to 3GB and limit the amount of cpu time to 15 minutes.
    # If the program hits this limit it will get killed and produce no output
    ulimit -v 3000000 -u 50 -t 900
    # use timeout to again limit the runtime of the program to <15 minutes
    timeout -s KILL 14m nice /path/to/ipython ag_code.py > /tmp/running-directory/stdout 2> /tmp/running-directory/stderr
    EOF

    # there should be a file /tmp/running-directory/autograder.json that contains the output from the autograder
    # or the above command must have failed.
```
