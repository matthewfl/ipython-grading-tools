# this file is suppose to be included into the notebook to control various aspects of the auto grader

import sys
import os
import atexit
from collections import defaultdict
import time
import threading
import json
import traceback

import resource

# TODO: add in checking for the amount of memory that is being used
# then if it is climbing above whatever limit is set, then it could just send
# a keyboard interrupt instead of letting the whole process die I suppose?
# that should

# if the student's cell should be evaluated
eval_cell = True

_current_section = None
_grades = defaultdict(list)
_grades[None] = []

# the main pid of the processes, for tracking timeout events when running the notebook
_main_pid = os.getpid()
_send_timeout = None
_timeout_lock = threading.Lock()
timeout_enabled = True

# memory limit of the progarm in MB
# otherwise a keyboard interrupt will be sent
# default to 2 GB
memory_limit = 1024 * 2

# if this is actually grading vs just running the development of some file
is_grading = 'AUTOGRADER_SAVE_FILE' in os.environ


def track_exception(track_timeouts=True):
    """
    Called when there is an exception inside of the student's code while running
    """
    global _grades, _current_section
    e, exception, trace = sys.exc_info()
    if not track_timeouts and e is KeyboardInterrupt:
        # the interrupt is just a timeout exception, so
        # will just let these slide as they should not represent anything
        print('Captured timeout exception')
        return
    s = '* (-1) Exception while executing code\n'
    tr = traceback.format_exc()
    s += '\n'.join(['    '+x for x in tr.splitlines()])
    _grades[_current_section].append(s)
    print('-'*50)
    print(f'Section: {_current_section}\nMark:\n{s}')
    print('-'*50)


def section(name=None):
    """
    Track which section/problem we are in
    """
    global _current_section
    assert name is None or ' ' not in name
    _current_section = name


def mark(s, tt=None):
    global _grades, _current_section
    if tt is not None:
        s += '\n'+'\n'.join(['    '+x for x in tt.splitlines()])
    _grades[_current_section].append(s)
    print('-'*50)
    print(f'Section: {_current_section}\nMark:\n{s}')
    print('-'*50)
    #import pdb; pdb.set_trace()


def set_timeout(seconds=None):
    global _send_timeout, _timeout_lock, timeout_enabled
    if timeout_enabled:
        _timeout_lock.acquire()
        try:
            if seconds is None or seconds == 0:
                # then clear the timeout
                _send_timeout = None
            else:
                _send_timeout = time.time() + seconds
        finally:
            _timeout_lock.release()

def _exit_writer():
    """
    When we are done with the notebook
    """
    sf = os.environ.get('AUTOGRADER_SAVE_FILE')
    print(json.dumps(_grades, indent=2))
    if sf:
        # then we want to generate some output file that represents which sections have been graded
        with open(sf, 'w+') as f:
            del _grades[None]
            json.dump(_grades, f, indent=1)


atexit.register(_exit_writer)


def _timeout_watcher():
    global _send_timeout, _timeout_lock, is_grading
    while True:
        time.sleep(2)  # sleep 2 seconds
        _timeout_lock.acquire()
        try:
            # size in KB
            ram_usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            if ram_usage > memory_limit * 1024:
                print('ABOVE MEMORY LIMIT, SENDING KEYBOARDINTERRUPT')
                os.kill(_main_pid, 2)

            s = _send_timeout
            if s is not None:
                now = time.time()
                if now > s + 30:
                    # then this is just running and not terminating within the timebounds
                    # this should terminate the processes
                    # this is the raw syscall so this will not clean up the python handles or run the exit handler?
                    # so maybe want to do that ourselves?
                    if is_grading:
                        os._exit(55)
                elif now > s:
                    print('SENDING KEYBOARDINTERRUPT')
                    # then just send a sigint to be a keyboard interupt and hopefully stop the cell
                    os.kill(_main_pid, 2)
        finally:
            _timeout_lock.release()

_timeout_watcher_thread = threading.Thread(target=_timeout_watcher)
_timeout_watcher_thread.start()
