#!/usr/bin/env python3

# add a uuid to every cell in a notebook such that it could be used to track the cells between different instances

import json
import argparse
import uuid


def main():
    argsp = argparse.ArgumentParser()
    argsp.add_argument('--notebook', required=True)
    args = argsp.parse_args()

    input_file = json.load(open(args.notebook))

    for cell in input_file['cells']:
        if 'g.cell_uuid' not in cell['metadata']:
            cell['metadata']['g.cell_uuid'] = str(uuid.uuid4())

    with open(args.notebook, 'w') as f:
        json.dump(input_file, f, indent=1)


if __name__ == '__main__':
    main()
