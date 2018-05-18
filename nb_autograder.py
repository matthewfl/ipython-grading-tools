#!/usr/bin/env ipython

# use ipython as the env as we might want to evaluate the code, in which case we want to have ipython magic

# this extracts all of the code from the notebook and merges it with the answer key such that we can evaluate autograder
# directives.
# we will check that any cell taken from the answer key holds the `### AUTOGRADER` at the top of the cell

import json
import argparse
import os
import subprocess
import sys
import ast

from nbconvert.filters import ipython2python

def read_notebook(fname):
    ret = []
    with open(fname, 'r') as f:
        j = json.load(f)
        for cell in j['cells']:
            if cell['cell_type'] == 'code':
                uid = cell['metadata'].get('g.cell_uuid')
                ret.append((uid, [x+'\n' for x in ipython2python(''.join(cell['source'])).splitlines()]))
    return ret


def indent_student_notebook(cells):
    ret = []
    for uid, code in cells:
        # wrap the code in an if statement so we can disable it
        # then wrap in a try except block to catch any possible exceptions
        # and increase the indent
        ncode = (['if autograder.eval_cell:\n',
                 ' try:\n'] +
                ['  ' + x for x in code] +
                ['\n',
                 '  pass\n',  # this is done in the case that there is no code in a cell, then this should still be ok
                 ' except:\n',
                 '  autograder.track_exception(False)\n'])
        try:
            ast.parse(''.join(ncode))
        except SyntaxError:
            # if there is a syntax in the resulting file then nothing is going to run, so take this error and report it when trying to run this cell

            # check that the syntax error is in the student's code and not in the conversion that we are performing on the code
            try:
                ast.parse(''.join(code))
                assert False, "Expected a syntax error in the students code, but somehow the combination failed"
            except SyntaxError as a:
                e = a

            ncode = (['if autograder.eval_cell:\n',
                      ' try:\n',
                      f'  raise SyntaxError({json.dumps(str(e))})\n',
                      '  pass\n',
                      ' except:\n',
                      '  autograder.track_exception(False)\n'] +
                     ['# ' + x for x in code])

        ret.append((uid, ncode))
    return ret


def merge_notebooks(student, answer):
    # assume that there are no new cells that are getting added to the students notebook
    # otherwise we are going to have a harder time merging the two notebooks
    # if the uid is None in the student's notebook then we are just include that, as that
    # will be something that the student added
    #
    # this currently depends on the fact that student's can't rearrange a notebook or delete cells

    # some students have rearranged cells in their notebook, so don't use this version of the merging operation
    ret = []
    i = 0
    j = 0
    uuids = set()
    while i < len(student) and j < len(answer):
        uids = student[i][0]
        uida = answer[j][0]

        # check that there is not a mismatch with including the same cell in the notebook twice
        assert uids not in uuids
        assert uida not in uuids

        if uids is None:
            # this cell was not provided, something the student added, so include it in the final output
            ret.append(student[i])
            i += 1
        elif uids == uida:
            # these are the same cell, take the students version
            ret.append(student[i])
            uuids.add(uids)
            i += 1
            j += 1
        else:
            # assume that this is something additional in the answer key
            uuids.add(answer[j][0])
            if '### AUTOGRADER' in ''.join(answer[j][1]):  # check that we are only including the autograder cells
                ret.append(answer[j])
            j += 1

    # finish reading the two input streams
    while i < len(student):
        assert student[i][0] not in uuids
        uuids.add(student[i][0])
        ret.append(student[i])
        i += 1
    while j < len(answer):
        assert answer[j][0] not in uuids
        uuids.add(answer[j][0])
        assert '### AUTOGRADER' in ''.join(answer[j][1])  # check that we are only including the autograder cells
        ret.append(answer[j])
        j += 1

    return ret


def merge_notebooks2(student, answer):
    # O(n^2) merge operation but allows for deleting of cells, and only performs the merges on the autograder cells instead
    # of all of them
    ret = student[:]
    #uidsl = {u[0], i for i, u in enumerate(ret)}
    for i, cell in list(enumerate(answer))[::-1]:
        if '### AUTOGRADER' in ''.join(cell[1]):
            # then this is an autograder cell, should include it
            following_uids = set([u[0] for u in answer[i:]])
            inserted = False
            for j, r in enumerate(ret):
                if r[0] in following_uids:
                    # then we found a place to insert this cell as the uuid of the next cell follows where this cell is located
                    ret.insert(j, cell)
                    inserted = True
                    break
            if not inserted:
                # it did not insert this into the notebook, so just push it to the back of the execution
                ret.append(cell)
    return ret

def merge_notebooks3(student, answer):
    # do O(n^2) merge, but from top to bottom such that we hopefully have all of the required cells in place before adding something
    ret = student[:]
    student_uids = set([u[0] for u in student])
    answer_uids = set([u[0] for u in answer if '### AUTOGRADER' in ''.join(u[1])])
    all_uids = student_uids | answer_uids
    for i, cell in enumerate(answer):
        if '### AUTOGRADER' in ''.join(cell[1]):
            # then this is an autograder cell, should include it
            prev_uids = set([u[0] for u in answer[:i]]) & all_uids
            insert_at = None
            if prev_uids:
                assert None not in prev_uids, prev_uids  # then failed to run the generate uids script on the answer key
                for j, r in enumerate(ret):
                    if r[0] in prev_uids:
                        insert_at = j + 1
                if insert_at is None:
                    # if we didn't find any of the required cells just put this at the bottom
                    insert_at = len(cell)
            else:
                insert_at = 0
            ret.insert(insert_at, cell)
    return ret


def get_code_string(cells, answers):
    # take the "template" of the answer key, and replace all of the cells with the content that we just generated
    # then use the normal convert function to generate the cells from the notebook
    # this way it still has the proper magic operations converted inside of the notebook
    # with open(answers, 'r') as f:
    #     j = json.load(f)
    # j['cells'] = []
    # for uid, code in cells:
    #     j['cells'].append({
    #         'cell_type': 'code',
    #         'metadata': {'g.cell_uuid': uid },
    #         'outputs': [],
    #         'source': [f'### cell {uid}\n'] + code,
    #         'execution_count': None,
    #     })

    # converter = subprocess.run('jupyter nbconvert --stdin --to python --stdout'.split(),
    #                            input=json.dumps(j,indent=1),
    #                            stdout=subprocess.PIPE,
    #                            encoding='utf-8',
    #                            timeout=10)

    # assert converter.returncode == 0
    # return converter.stdout

    return 'import autograder\n\n' + ''.join([f'\n\n### cell {uid}\n\n{"".join(code)}\n\n' for uid, code in cells])


def main():
    argsp = argparse.ArgumentParser()
    argsp.add_argument('--answer', type=str, required=True, help='the notebook answer key with autograding directives')
    argsp.add_argument('--student', type=str, required=True, help='the students notebook')
    argsp.add_argument('--evaluate', action='store_true', default=False, help='if to pass the autograder code to the eval function')
    argsp.add_argument('--output', type=str, help='Where to save the generated output program')
    argsp.add_argument('--autograder-output', type=str, help='where the autograder should save its generated output')
    argsp.add_argument('--import_path', type=str, help='list of paths to add to the import directory', default=[], nargs='*')
    args = argsp.parse_args()

    answers = read_notebook(args.answer)
    students = indent_student_notebook(read_notebook(args.student))

    result = merge_notebooks3(students, answers)
    code = get_code_string(result, args.answer)

    if args.output:
        with open(args.output, 'w+') as f:
            f.write(code)

    if args.autograder_output:
        os.environ['AUTOGRADER_SAVE_FILE'] = args.autograder_output

    if args.evaluate:
        sys.path += args.import_path
        globs = {}
        try:
            import autograder
            globs['autograder'] = autograder
        except ImportError:
            pass
        g = globals().get('get_ipython')
        if g is not None:
            globs['get_ipython'] = g

        exec(code, globs)


if __name__ == '__main__':
    main()
