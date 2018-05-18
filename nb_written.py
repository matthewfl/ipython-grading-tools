#!/usr/bin/env python3

import json
import argparse
import subprocess


def read_notebook(fname):
    with open(fname, 'r') as f:
        return json.load(f)


def slice_notebook(student, answer):
    selected_cells = set()
    selecting = False
    for cell in answer['cells']:
        if cell['cell_type'] == 'code':
            c = ''.join(cell['source'])
            if '### AUTOGRADER' in c:
                if '### ANSWERS START' in c:
                    selecting = True
                elif '### ANSWERS END' in c:
                    selecting = False
        if selecting:
            selected_cells.add(cell['metadata'].get('g.cell_uuid'))
    i = 0
    while i < len(student['cells']):
        uid = student['cells'][i]['metadata'].get('g.cell_uuid')
        if not (uid is None or uid in selected_cells):
            del student['cells'][i]
        else:
            i += 1


def main():
    argsp = argparse.ArgumentParser()
    argsp.add_argument('--answer', type=str, required=True, help='the notebook answer key with autograding directives')
    argsp.add_argument('--student', type=str, required=True, help='the students notebook')
    argsp.add_argument('--output_html', type=str, required=True, help='The output html that was sliced out of the student\'s notebook')
    args = argsp.parse_args()

    answers = read_notebook(args.answer)
    student = read_notebook(args.student)

    # delete the cells that we do not care about
    slice_notebook(student, answers)

    converter = subprocess.run('jupyter nbconvert --stdin --to html --output'.split() + [args.output_html],
                               input=json.dumps(student,indent=1),
                               encoding='utf-8',
                               timeout=10)


if __name__ == '__main__':
    main()
