#!/usr/bin/env python3

import sys
import bitstring
import argparse

parser = argparse.ArgumentParser(description='Process some integers.')
parser.add_argument('candump', help='candump log')
args = parser.parse_args()


def count_bit_stuffs(bits):
    bits_stuffed = 0

    previous_bit = -1
    consecutive_bits = 0
    for bit in bits:
        if previous_bit == -1:
            continue

        if previous_bit == bit:
            consecutive_bits += 1
        else:
            consecutive_bits = 0

        if consecutive_bits == 5:
            bits_stuffed += 1
            consecutive_bits = 1
            previous_bit = (not bit)
        else:
            previous_bit = bit

    return bits_stuffed


def total_bits_on_wire(bits):
    total = 0

    total = total + 1   # start bit
    total = total + bits.len
    total = total + 1   # RTR
    total = total + 6   # control bits
    total = total + 15  # CRC
    total = total + count_bit_stuffs(bits)
    total = total + 3   # delimiter, ACK etc.
    total = total + 7   # end of frame
    total = total + 3   # intermission

    return total


with open(args.candump, 'r') as f:
    bits_sum = 0

    start_time = sys.maxsize
    end_time = 0
    for line in f.readlines():
        try:
            timestamp = float((line.split(' ')[0]).replace('(','').replace(')',''))
            message_id = bitstring.BitString(hex=line.split(' ')[2].split('#')[0])
            message_data = bitstring.BitString(hex=line.split(' ')[2].split('#')[1])

        except IndexError:
            continue
        except ValueError:
            continue

        all_data = message_id.copy()
        all_data.append(message_data)

        bits_sum = bits_sum + total_bits_on_wire(all_data)

        start_time = min(timestamp, start_time)
        end_time = max(timestamp, end_time)

    theoretical_max = 250000 * (end_time - start_time)

    print("load: %s" % (bits_sum / theoretical_max))