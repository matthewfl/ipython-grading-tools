#!/usr/bin/env python3

import json
import argparse
import re
import sys

# this is probably going to be so brittle
# just going to parse the ipython notebook source file format
# and remove the student start and end statements

def strip(lines):
    i = 0
    keep = True
    FAIL = False
    while i < len(lines):
        start = re.match(r'(.*)### STUDENT(S){0,1} (START|BEGIN)', lines[i])
        end = re.match(r'(.*)### STUDENT(S){0,1} (END|FINISH)', lines[i])
        comment = re.match(r'(.*)###', lines[i])
        todo = re.match(r'(.*)TODO', lines[i])
        if start:
            lines[i] = start.group(1) + '### STUDENTS START\n'
            i += 1
            keep = False
            # then we want to insert a line here?
            # this should be something like just match the
            # length of the line and then add some not implemented
            # error that needs to get replaced
        elif end:
            assert not keep  # check that we were in a remove block
            lines.insert(i, end.group(1) + 'raise NotImplementedError()  # REPLACE ME\n')
            lines[i+1] = end.group(1) + '### STUDENTS END\n'
            i += 2
            keep = True
        elif comment:
            # keep these comments
            assert not todo
            i += 1
        else:
            if keep:
                if todo:  # should not have /todo/ comments in the notebook when it is being given to students
                    print('\033[1;31m TODO' + lines[i] + '\033[0m')
                    FAIL = True
                i += 1
            else:
                del lines[i]
    assert keep
    return FAIL


def main():
    argsp = argparse.ArgumentParser()
    argsp.add_argument('--input', type=str, required=True)
    argsp.add_argument('--output', type=str, required=True)
    args = argsp.parse_args()

    FAIL = False

    if args.input.endswith('.ipynb'):
        input_file = json.load(open(args.input))
        for cell in input_file['cells']:
            cell['metadata']['deletable'] = False  # prevents these cells from getting deleted
            # if the cells were first annotated with some uuid, then that could be used to perform tracking ebtween different version sof the notebooks
            if cell['cell_type'] == 'code':
                cell['outputs'] = []
                cell['execution_count'] = None
                FAIL = FAIL or strip(cell['source'])

        # filter out cells which mention the autograder
        cells = [c for c in input_file['cells'] if cell['cell_type'] != 'code' or 'autograder' not in ''.join(c['source']).lower()]
        input_file['cells'] = cells

        if not FAIL:
            with open(args.output, 'w+') as f:
                json.dump(input_file, f, indent=1)
    elif args.input.endswith('.py'):
        input_file = list(open(args.input))
        FAIL = strip(input_file)
        if not FAIL:
            with open(args.output, 'w+') as f:
                f.write(''.join(input_file))
    else:
        print(f'Unsure how to handle file type {args.input}')
        return 1

    return 1 if FAIL else 0

if __name__ == '__main__':
    sys.exit(main())
