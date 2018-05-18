#!/bin/bash

# this file wraps the autograder.  There should be a timeout statement to ensure that the student's code doesn't run for tooo long
# use: sudo -u limited-user to change the user to another account on the system which can't modify files

# requires that the anaconda env can be access by this user

# set to track issues while running
set -xe


DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"


# arguments to the autograder
answers=$DIR/example-answers.ipynb
code_dir=$1
feedback_dir=$2
student=$3

# set this to an accessible location of the anaconda environment
# the student's code MUST run using ipython
PY=/home/seq2class/anaconda3/bin/ipython

WDIR=`mktemp -d /tmp/autograder.XXXXXXXX`

# copy over the files that this should use
cp -r $code_dir/$student/* $WDIR
# copy over the autograder implementation
cp $DIR/../autograder.py $WDIR

# generate the converted autograder code
python $DIR/../nb_autograder.py --answer $answers --student $code_dir/$student/homework_3.ipynb --output $WDIR/ag_code.py

chmod -R 777 $WDIR

# TODO: also use ulimit to limit the amount of memory and

# run in 15 minutes or less, and 3 gb or less
# also with 15 minutes of cpu time, so if it tries to use more than one thread it is going to end up getting stopped

pushd $WDIR
timeout -s KILL 15m sudo -u limited-user -i <<EOF
export AUTOGRADER_SAVE_FILE=$WDIR/autograder.json
export OMP_NUM_THREADS=1
cd $WDIR/
ulimit -v 3000000 -u 50 -t 1000
timeout -s KILL 14m nice $PY $WDIR/ag_code.py > $WDIR/stdout 2> $WDIR/stderr
EOF
exit=$?
popd

# export OMP_NUM_THREADS=1
# # run the code to generate the autograder output
# pushd $WDIR
# timeout -s KILL 14m sudo -u limited-user AUTOGRADER_SAVE_FILE=$WDIR/autograder.json timeout -s KILL 13m nice $PY $WDIR/ag_code.py > $WDIR/stdout 2> $WDIR/stderr
# exit=$?
# popd

# move the results of autograding back to where the feedback is being collected
cp $WDIR/autograder.json $feedback_dir/$student/autograder.json
