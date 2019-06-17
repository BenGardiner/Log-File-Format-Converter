#!/usr/bin/env python3

import bitstring
import argparse
import json
import ut_j1939db

ut_j1939db.init_j1939db()


def str2bool(v):
    return v.lower() in ("yes", "true", "t", "1")


parser = argparse.ArgumentParser(description='Process some integers.')
parser.add_argument('candump', help='candump log')
parser.add_argument('--candata', type=str2bool, const=True, default=False, nargs='?', help='print input can data')
parser.add_argument('--pgn',     type=str2bool, const=True, default=True, nargs='?', help='print source/destination/type description')
parser.add_argument('--spn',     type=str2bool, const=True, default=True, nargs='?', help='print signals description')
parser.add_argument('--format',  type=str2bool, const=True, default=False, nargs='?', help='format each structure (otherwise single-line)')

args = parser.parse_args()

with open(args.candump, 'r') as f:
    for line in f.readlines():
        try:
            message_id = bitstring.BitString(hex=line.split(' ')[2].split('#')[0])
            message_data = bitstring.BitString(hex=line.split(' ')[2].split('#')[1])

        except IndexError:
            continue

        desc_line = ''
        if args.candata:
            desc_line = desc_line + line.rstrip() + " ; "
            if args.format:
                desc_line = desc_line + '\n'

        if args.pgn:
            pgn_desc = ut_j1939db.describe_message_id(message_id.uint)
            if args.format:
                pgn_desc = str(json.dumps(pgn_desc, indent=4))
            else:
                pgn_desc = str(pgn_desc)

            desc_line = desc_line + pgn_desc

        if args.pgn and args.spn:
            if args.format:
                desc_line = desc_line + '\n'
            else:
                desc_line = desc_line + " // "

        if args.spn:
            spn_desc = ut_j1939db.describe_message_data(message_id.uint, message_data.bytes)
            if args.format:
                spn_desc = str(json.dumps(spn_desc, indent=4))
            else:
                spn_desc = str(spn_desc)

            desc_line = desc_line + spn_desc

        print(desc_line)
