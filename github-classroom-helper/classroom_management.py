# Tools to help with the grading of assignments when using github classroom


import os
import sys
import json
import subprocess
import argparse
import glob
import shutil
import csv
import ast
import time
import random
import re

import numpy as np
import requests

if 'GH_ACCESS' not in os.environ:
    print(
        """
        Set `export GH_ACCESS=your_access_token`
        You can get an access token at https://github.com/settings/tokens (give it the permission to list repos)
        Also have your ssh key configured such that you can clone repos
        """)
    sys.exit(1)


access_token = os.environ['GH_ACCESS']

argsp = argparse.ArgumentParser()
argsp.add_argument('--assignment_prefix', type=str, help='the prefix that that was used when creating the assignment with github classroom, ex: \'sp18-assignment1-\'', required=True)
argsp.add_argument('--local_directory', type=str, help='local directory where operations should be performed', required=True)
argsp.add_argument('--feedback_directory', type=str, default=None, help='location where the feedback files should be stored')
argsp.add_argument('-op', '--operation', choices=('clone', 'create_feedback', 'grade', 'process_feedback', 'release_feedback', 'autograder'), required=True)
argsp.add_argument('--feedback_file', type=str, help='A file to insert into all of the repos where comments and grades can be collected')
argsp.add_argument('--collected_feedback', type=str, help='A csv file which will contain all of the written feedback')
argsp.add_argument('--notebook_name', type=str, help='The name of what the students notebook file should be that they are turning in')
argsp.add_argument('--feedback_compute_out_of', action='store_true', help='If the system should automattically compute what a problem is out of based on what scores were assigned')
#argsp.add_argument('--students_list', type=str, help='A csv of the students in the class and if they are enrolled for a grade or audit, thus direct grading efforts')
argsp.add_argument('--autograder-script', type=str, help='The main script that wraps running the rest of the autograder')
argsp.add_argument('--force_make_feedback', nargs='*', help='Force creating the feedback file for these students regardless of it they created the done message in the commit', default=[])
argsp.add_argument('--answer_key', type=str, help='The notebook that contains the answer key (and autograder commands)')
args = argsp.parse_args()


if args.feedback_directory is None:
    args.feedback_directory = os.path.dirname(args.local_directory + '/') + '-feedback'


# helper functions that are useful
def system(cmd):
    print('+{}'.format(cmd))
    return os.system(cmd)


def system_output(cmd):
    print('+{}'.format(cmd))
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    try:
        out, _ = p.communicate()
        assert p.returncode == 0
        return out.decode('utf-8')
    finally:
        p.kill()


def get_open_emacs_files():
    # grab the list of open files
    # emacsclient -e "(mapcar 'buffer-file-name (buffer-list))"
    # emacsclient -e "(mapcar 'buffer-file-name (mapcar 'window-buffer (window-list)))"
    # TODO: have to parse a lisp expression
    el = subprocess.Popen(['emacsclient', '-e', "(mapcar 'buffer-file-name (mapcar 'window-buffer (window-list)))"],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = el.communicate()
    # out should be like: '(nil "/tmp/test.txt" nil nil nil nil nil nil nil nil nil)
    # HACK: just assume that we can split the above string by spaces and that there are no spaces in the filename....sigh
    ret = []
    out = out.decode('utf-8').strip()[1:-1]
    print(out)
    for name in out.split():
        if name == 'nil':
            # this isn't a file that is open
            continue
        ret.append(name[1:-1])  # remove the "" from the string
    return ret


def get_repo_list():
    rr = []
    i = 0
    while True:
        r = requests.get('https://api.github.com/orgs/seq2class/repos', params={'page': i}, auth=(access_token, '')).json()
        i += 1
        rr += r
        if not r: break
    return [r for r in rr if r['name'].startswith(args.assignment_prefix)]


def clone_operation():
    repos = get_repo_list()

    for repo in repos:
        uname = repo['name'][len(args.assignment_prefix):]
        dest = os.path.join(args.local_directory, uname)
        if os.path.exists(dest):
            # then we already cloned this repo
            # maybe we should pull to update this instead???
            # if system('cd {} && git pull'.format(dest)) != 0:
            #     print('Failed to update {}'.format(dest))
            print(f'User {uname} already exists')
        else:
            # clone the repo to the destination directory
            #system('git clone {} {}'.format(repo['ssh_url'], dest))
            system('cd {} && git submodule add {} {}'.format(
                args.local_directory,
                repo['ssh_url'],
                uname,
            ))
            time.sleep(2)


def sanity_check_notebook(fname):
    """
    Run some basic sanity checks over the code without actually running it.  Eg that it actually parses
    """

    converter = subprocess.Popen('jupyter nbconvert --stdin --stdout --to python'.split(),
                                 stdout=subprocess.PIPE, stderr=open(os.devnull, 'w'), stdin=open(fname, 'r'))
    try:
        out, err = converter.communicate(timeout=5)  # convert to just raw python without the notebook

        # Run the python through the python parser, if there is an error then return the error
        ast.parse(out)
        return '**Pass**'
    except SyntaxError as e:
        oo = out.decode('utf-8').split('\n')
        return '**Fail**: (-1)' + str(e) + '\n\n    ' + '\n    '.join(oo[max(0, e.lineno - 4):min(len(oo) - 1, e.lineno + 4)])
    except subprocess.TimeoutExpired:
        return 'Failed to convert to python code'
    finally:
        converter.kill()


# def generate_notebook_pdf(fname, out):
#     converter = subprocess.Popen('jupyter nbconvert --stdin --to pdf --output'.split() + [out],
#                                  stdin=open(fname, 'r'))

#     try:
#         converter.communicate(timeout=120)
#         print(f"generating pdf for notebook {fname} to {out}")
#     finally:
#         converter.kill()


def create_feedback_file():
    assert args.feedback_file and args.feedback_directory and args.notebook_name
    with open(args.feedback_file, 'r') as f:
        inp = f.read()
    for folder in glob.glob(args.local_directory + '/*'):
        other=''
        uname = folder.split('/')[-1]
        fd = os.path.join(args.feedback_directory, uname)
        fb_file = os.path.join(args.feedback_directory, uname, 'feedback.md')
        commit_hash = system_output(f'cd {folder} && git describe --always --abbrev=15').strip()
        if os.path.exists(fd):
            # check that the commit hash is in the grading file, otherwise something changed somehow
            contents = open(fb_file, 'r').read()
            if commit_hash not in contents:
                print(f'\033[1;31mUser {uname} changed commit hash\033[0;0m')
                # the alternate case is that the feedback file was already given and thus this is ok
            continue

        if 'FILL IN' in open(os.path.join(folder, 'README.md'), 'r').read():
            # then they failed to put their name in there
            print(f'\033[1;31mUser {uname} failed to update name\033[0;0m')
            other += '* (-5) Did not set name in README.md\n'

        commit = system_output(f'cd {folder} && git log -n 3')  # get the last 3 commits

        done = 'done' in commit.lower()  # check for the word done in the commit message
        override = uname in args.force_make_feedback

        if done or override:
            syntax_check = sanity_check_notebook(os.path.join(folder, args.notebook_name))
            os.mkdir(fd)
            with open(fb_file, 'w+') as f:
                f.write(inp.format(
                    syntax_check=syntax_check,
                    git_commit=commit_hash,
                    other=other,
                ))

# def open_students_code():
#     print("Open an emacs and do: M-x server-start")
#     assert args.notebook_name
#     fname = None
#     was_open = set()
#     while True:
#         feedback_file = set(get_open_emacs_files())
#         new_open = feedback_file - was_open
#         if new_open:
#             assert len(new_open) == 1  # there should only be one new file at a time
#             # compute the name of this notebook based off where the feedback file is and then
#             # save this as /tmp/active-notebook.pdf so that the pdf viewer will open the file
#             notebook = os.path.join(os.path.dirname(new_open[0]), args.notebook_name)
#             if os.path.exists(notebook):
#                 generate_notebook_pdf(notebook, "/tmp/active-notebook.pdf")
#         time.sleep(1)
#         was_open = feedback_file


def run_autograder():
    # TODO: make this take the answer key file instead of the run-script command, and then just make the run
    # scripts command take the answer key as an argument as well
    assert args.feedback_directory and args.notebook_name and args.autograder_script

    students = glob.glob(os.path.join(args.feedback_directory, '*/feedback.md'))

    unames = [s.split('/')[-2] for s in students]

    gen_names = [g for g in unames if not os.path.exists(os.path.join(args.feedback_directory, g, 'autograder.json'))]

    # run the autograder in parallel using parallel and a bash script that controls the actual operations
    gen = subprocess.Popen(f'parallel -j4 {args.autograder_script} {args.local_directory} {args.feedback_directory} {{}}'.split(),
                           stdin=subprocess.PIPE)
    gen.stdin.write(('\n'.join(gen_names)).encode('ascii'))
    gen.stdin.close()

    gen.wait()

    for s in unames:
        o = os.path.join(args.feedback_directory, s, 'autograder.json')
        if not os.path.exists(o):
            # this will just ignore these files where it doesn't have the output from the autograder
            print(f'\033[1;31mUser {s} did not finish running autograder\033[0;0m')
            continue

        with open(o, 'r') as f:
            ag = json.load(f)

        def rfunc(match):
            return '\n'.join(ag.get(match.group(1), []))

        with open(os.path.join(args.feedback_directory, s, 'feedback.md'), 'r') as f:
            c = f.read()
        r = re.sub(r'\[\[(.*)\]\]', rfunc, c)
        with open(os.path.join(args.feedback_directory, s, 'feedback.md'), 'w+') as f:
            f.write(r)


def grade_students():
    print("Open an emacs session and do: M-x server-start")
    assert args.notebook_name and args.answer_key
    students = glob.glob(os.path.join(args.feedback_directory, '*/feedback.md'))
    random.shuffle(students)

    dirn = os.path.dirname(__file__)
    # generate all of the pdfs for the student notebooks up front such that there isn't a switching cost

    unames = [s.split('/')[-2] for s in students]
    gen_names = [g for g in unames if not os.path.exists(f"/tmp/graded-notebook-{g}.html")]
    #gen = subprocess.Popen(f'parallel jupyter nbconvert {os.path.abspath(args.local_directory)}/{{}}/{args.notebook_name} --to html --output /tmp/graded-notebook-{{}}'.split(), stdin=subprocess.PIPE)
    gen = subprocess.Popen(f'parallel python {dirn}/grading/nb_written.py --answer {os.path.abspath(args.answer_key)} --student {os.path.abspath(args.local_directory)}/{{}}/{args.notebook_name} --output_html /tmp/graded-notebook-{{}}'.split(), stdin=subprocess.PIPE)

    gen.stdin.write(('\n'.join(gen_names)).encode('ascii'))
    gen.stdin.close()

    gen.wait()

    was_open = set()
    while True:
        feedback_file = set(get_open_emacs_files())
        if len(feedback_file) == 0 and len(students) > 0:
            # then there are no feedback files open, so we are going to choose one at random and then open it
            system('emacsclient -n {}'.format(students[0]))
            feedback_file = set([os.path.abspath(students[0])])
            students = students[1:]  # remove the first item from the list such that it will open the next one
        new_open = feedback_file - was_open
        if new_open:
            uname = next(iter(new_open)).split('/')[-2]
            assert len(new_open) == 1
            notebook = os.path.join(args.local_directory, uname, args.notebook_name)
            with open('/tmp/active-notebook2.html', 'w+') as f:
                with open(f'/tmp/graded-notebook-{uname}.html') as w:
                    # TODO: something that refreshes this file it it changes
                    f.write(w.read())
                    #f.write(f'<script src="{watch_script}"></script>')
                    f.write(f'<h1>{uname}</h1>')
            os.rename('/tmp/active-notebook2.html', '/tmp/active-notebook.html')
            # if os.path.exists(notebook):
            #     #generate_notebook_pdf(notebook, "/tmp/active-notebook.pdf")
            #     shutil.copy(f'/tmp/graded-notebook-{uname}.pdf', '/tmp/active-notebook.pdf')
        was_open = feedback_file
        time.sleep(.5)
        print(f'Students left to grade: {len(students)}')


# performing the processing on the feedback files after everything has been computed
def process_feedback_grades():
    assert args.collected_feedback and args.feedback_file
    students = {}
    problems = {}
    name_emails = {}
    problem_order = []
    problem_indent = {}
    # get the template and determine what the problems are
    with open(args.feedback_file, 'r') as f:
        for line in f:
            if line.startswith('#'):  # the problem sections are going to start with the headings
                m = re.match(r'([^\[]*)(\[([0-9]+|\?)/([0-9]+|\?)\])?.*', line)
                p = m.group(1).lstrip('#').strip()
                #import ipdb; ipdb.set_trace()
                if m.group(2):
                    problems[p] = m.group(3), m.group(4)
                else:
                    problems[p] = '?', '?'
                problem_order.append(p)
                problem_indent[p] = len(line) - len(line.lstrip('#'))  # compute the indent level of this problem

    for rm in glob.glob(args.local_directory + '/*/README.md'):
        username = os.path.split(os.path.dirname(rm))[1]
        name, email = 'unknown', 'unknown'
        with open(rm, 'r') as f:
            for line in f:
                l = re.match(r'.*Name[^ ]*(.*)', line)
                if l:
                    name = l.group(1).strip()
                l = re.match(r'.*Email[^ ]*(.*)', line)
                if l:
                    email = l.group(1).strip()
        name_emails[username] = name, email

    # compute the distributions on all of the problems
    for fbf in glob.glob(args.feedback_directory + '/*/feedback.md'):
        # info = {}  # all of the collected fields from this document
        problem = None  # The name of the problem
        global nested_sections, nested_scores  # bad hack, sigh
        nested_scores = np.array([])
        nested_sections = []
        info = {}
        username = os.path.split(os.path.dirname(fbf))[1]
        def pop_sections(l):
            global nested_sections, nested_scores
            while len(nested_sections) >= l:
                pscore = problems[nested_sections[-1]][1]
                info[nested_sections[-1]] = nested_scores[-1]
                # the nested_scores are negative values of the points missed
                # (or extra credit given)
                assert pscore == '?' or float(pscore) + nested_scores[-1] >= 0, f"there would be a negative score on {nested_sections[-1]} for {username}"
                nested_sections = nested_sections[:-1]
                nested_scores = nested_scores[:-1]
        with open(fbf, 'r') as f:
            for line in f:
                if line.startswith('#'):
                    # then this represents a problem, so we are going to change to that problem
                    m = re.match(r'([^\[]*)(\[([0-9]+|\?)/([0-9]+|\?)\])?.*', line)
                    problem = m.group(1).lstrip('#').strip()
                    indent_level = problem_indent[problem]
                    pop_sections(indent_level)
                    assert problem in problems, f"Problem '{problem}' not found in set of problems"
                    while len(nested_sections) < indent_level - 1:
                        nested_sections.append('UNKNOWN_SECTION')
                        nested_scores = np.append(nested_scores, [0])
                    nested_sections.append(problem)
                    nested_scores = np.append(nested_scores, [0])
                # grades holds the grades that are marked on this line
                grades = re.findall(r'\s\([\-\+][0-9\.]+\)\s', line)
                for g in grades:
                    # add these scores in to the accumulation
                    f = float(g[2:-2])
                    assert f <= 0
                    nested_scores += f
            pop_sections(1)  # pop everything such that it gets saved in the info
            info['github'] = username
            info['name'], info['email'] = name_emails[username]
            students[username] = info

    with open(args.collected_feedback, 'w+') as f:
        #fields = list(set(k for s in students for k in s.keys()))
        fields = ['github', 'name', 'email'] + problem_order
        # TODO: order this list such that the order is useful
        writer = csv.DictWriter(f, fieldnames=fields)
        header = {}
        for f in fields:
            header[f] = f.lstrip('#').strip()
        writer.writerow(header)

        # the total scores for each category
        totals = {}
        totals['email'] = totals['name'] = totals['github'] = 'Total points'
        for k, (_, t) in problems.items():
            totals[k] = t
        writer.writerow(totals)

        for s in sorted(students.keys()):
            writer.writerow(students[s])

    if args.feedback_compute_out_of:
        # then regenerate the feedback files based off what these items are out of
        for fbf in glob.glob(args.feedback_directory + '/*/feedback.md'):
            username = os.path.split(os.path.dirname(fbf))[1]
            s = students[username]
            lines = list(open(fbf, 'r'))
            for i in range(len(lines)):
                if lines[i].startswith('#'):
                    m = re.match(r'([^\[]*)(\[([0-9]+|\?)/([0-9]+|\?)\])?.*', lines[i])
                    p = m.group(1).lstrip('#').strip()
                    lines[i] = ('#' * problem_indent[p]) + ' ' + p.lstrip('#').strip() + f' [{float(problems[p][1]) + s[p]}/{problems[p][1]}]\n'

            with open(fbf, 'w+') as f:
                f.write(''.join(lines))



def release_feedback_files():
    # copy the feedback files to the users directory and upload it to their repos
    for fbf in glob.glob(args.feedback_directory + '/*/feedback.md'):
        uname = os.path.split(os.path.dirname(fbf))[1]
        t = os.path.join(args.local_directory, uname, 'feedback.md')
        if not os.path.exists(t):
            shutil.copy(fbf, t)
            # using @uname should create a notification on github
            system(f'cd {args.local_directory}/{uname} && git add feedback.md && git commit -m "Feedback for @{uname}"')


def main():
    if args.operation == 'clone':
        clone_operation()
    elif args.operation == 'create_feedback':
        create_feedback_file()
    elif args.operation == 'grade':
        grade_students()
    elif args.operation == 'process_feedback':
        process_feedback_grades()
    elif args.operation == 'release_feedback':
        release_feedback_files()
    elif args.operation == 'autograder':
        run_autograder()

if __name__ == '__main__':
    main()
