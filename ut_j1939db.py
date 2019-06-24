import struct
import sys
import json
import bitstring

DA_MASK = 0x0000FF00
SA_MASK = 0x000000FF
PF_MASK = 0x00FF0000

j1939db = {}


def init_j1939db():
    global j1939db
    with open("J1939db.json", 'r') as j1939_file:
        j1939db = json.load(j1939_file)


def parse_j1939_id(can_id):
    sa = (SA_MASK & can_id)
    pf = (PF_MASK & can_id) >> 16
    da = (DA_MASK & can_id) >> 8

    if pf >= 240:  # PDU2 format
        pgn = pf * 256 + da
        da = 0xFF
    else:
        pgn = pf * 256
    return pgn, da, sa


def is_connection_management_message(message_id):
    return (message_id & PF_MASK) == 0x00EC0000


def is_data_transfer_message(message_id):
    return (message_id & PF_MASK) == 0x00EB0000


def is_transport_message(message_id):
    return is_data_transfer_message(message_id) or is_connection_management_message(message_id)


def is_bam_cts_message(message_bytes):
    return message_bytes[0] == 32


def get_pgn_acronym(pgn):
    global j1939db
    try:
        acronym = j1939db["J1939PGNdb"]["{}".format(pgn)]["Label"]
        if acronym == '':
            acronym = "Unknown"
        return acronym
    except KeyError:
        return "Unknown"


def get_pgn_name(pgn):
    global j1939db
    try:
        name = j1939db["J1939PGNdb"]["{}".format(pgn)]["Name"]
        if name == '':
            name = get_pgn_acronym(pgn)
        return name
    except KeyError:
        return get_pgn_acronym(pgn)


def get_spn_list(pgn):
    global j1939db
    try:
        return sorted(j1939db["J1939PGNdb"]["{}".format(pgn)]["SPNs"])
    except KeyError:
        return []


def get_spn_name(spn):
    global j1939db
    try:
        return j1939db["J1939SPNdb"]["{}".format(spn)]["Name"]
    except KeyError:
        return "Unknown"


def get_spn_acronym(spn):
    global j1939db
    try:
        return j1939db["J1939SPNdb"]["{}".format(spn)]["Acronym"]
    except KeyError:
        return "Unknown"


def get_address_name(address):
    global j1939db
    try:
        address = "{:3d}".format(address)
        return j1939db["J1939SATabledb"][address.strip()]
    except KeyError:
        return "Unknown"


def get_formatted_address_and_name(address):
    if address == 255:
        formatted_address = "(255)"
        address_name = "All"
    else:
        formatted_address = "({:3d})".format(address)
        try:
            address_name = get_address_name(address)
        except KeyError:
            address_name = "Unknown"
    return formatted_address, address_name


def describe_message_id(message_id):
    description = {}

    pgn, da, sa = parse_j1939_id(message_id)
    pgn_acronym = get_pgn_acronym(pgn)
    pgn_name = get_pgn_name(pgn)
    da_formatted_address, da_address_name = get_formatted_address_and_name(da)
    sa_formatted_address, sa_address_name = get_formatted_address_and_name(sa)

    description['PGN'] = "%s(%s)" % (pgn_acronym, pgn)
    description['DA'] = "%s%s" % (da_address_name, da_formatted_address)
    description['SA'] = "%s%s" % (sa_address_name, sa_address_name)
    return description


def lookup_all_spn_params(callback, spn):
    global j1939db

    die = False
    # look up items in the database
    name = get_spn_name(spn)
    units = j1939db["J1939SPNdb"]["{}".format(spn)]["Units"]
    spn_start = j1939db["J1939SPNdb"]["{}".format(spn)]["StartBit"]
    spn_end = j1939db["J1939SPNdb"]["{}".format(spn)]["EndBit"]
    spn_length = j1939db["J1939SPNdb"]["{}".format(spn)]["SPNLength"]
    scale = j1939db["J1939SPNdb"]["{}".format(spn)]["Resolution"]
    offset = j1939db["J1939SPNdb"]["{}".format(spn)]["Offset"]
    fmt = ''
    rev_fmt = ''
    if spn_length <= 8:
        fmt = "B"
        rev_fmt = "B"
    elif spn_length <= 16:
        fmt = ">H"
        rev_fmt = "<H"
    elif spn_length <= 32:
        fmt = ">L"
        rev_fmt = "<L"
    elif spn_length <= 64:
        fmt = ">Q"
        rev_fmt = "<Q"
    else:
        die = True
        if callback is not None:
            callback("Not a plottable SPN.")
    shift = 64 - spn_start - spn_length
    mask = 0
    for m in range(min(spn_length, 63)):
        mask += 1 << (63 - m - spn_start)
        # print("Mask: 0x{:016X}".format(mask))
    if scale <= 0:
        scale = 1
    return die, fmt, mask, name, offset, rev_fmt, scale, shift, spn_end, spn_length, spn_start, units


def get_spn_bytes(message_data, spn):
    spn_start = j1939db["J1939SPNdb"]["{}".format(spn)]["StartBit"]
    spn_end = j1939db["J1939SPNdb"]["{}".format(spn)]["EndBit"]

    cut_data = bitstring.BitString(message_data)[spn_start : spn_end + 1]
    cut_data.byteswap()

    return cut_data


def get_spn_value(message_data, spn):
    scale = j1939db["J1939SPNdb"]["{}".format(spn)]["Resolution"]
    operational_min = j1939db["J1939SPNdb"]["{}".format(spn)]["OperationalLow"]
    operational_max = j1939db["J1939SPNdb"]["{}".format(spn)]["OperationalHigh"]

    if scale <= 0:
        scale = 1
    offset = j1939db["J1939SPNdb"]["{}".format(spn)]["Offset"]

    cut_data = get_spn_bytes(message_data, spn)
    value = cut_data.uint * scale + offset
    if value < operational_min or value > operational_max:
        raise ValueError
    return value


def get_spn_value_alt(frame_bytes, fmt, mask, offset, rev_fmt, scale, shift):
    # print(entry)
    # times.append(entry[0])
    # print("Entry: " + "".join("{:02X} ".format(d) for d in entry[1]))
    decimal_value = struct.unpack(">Q", frame_bytes)[0] & mask
    # the < takes care of reverse byte orders
    # print("masked decimal_value: {:08X}".format(decimal_value ))
    shifted_decimal = decimal_value >> shift
    # reverse the byte order
    reversed_decimal = struct.unpack(fmt, struct.pack(rev_fmt, shifted_decimal))[0]
    # print("shifted_decimal: {:08X}".format(shifted_decimal))
    spn_value = reversed_decimal * scale + offset
    return spn_value


def describe_message_data(message_id, message_data):
    pgn, da, sa = parse_j1939_id(message_id)

    description = dict()
    for spn in get_spn_list(pgn):
        spn_name = get_spn_name(spn)
        spn_units = j1939db["J1939SPNdb"]["{}".format(spn)]["Units"]

        spn_value = get_spn_value(message_data, spn)
        description[spn_name] = "%s (%s)" % (spn_value, spn_units)
        if spn_units.lower() in ("bit", "binary",):
            try:
                enum_descriptions = j1939db["J1939BitDecodings"]["{}".format(spn)]
                spn_value_description = enum_descriptions[str(int(spn_value))].strip()
                description[spn_name] = "%d (%s)" % (spn_value, spn_value_description)
            except KeyError:
                description[spn_name] = "%d (Unknown)" % spn_value
        elif spn_units.lower() in ("manufacturer determined", "byte", ""):
            description[spn_name] = "%s" % get_spn_bytes(message_data, spn)
        elif spn_units.lower() in ("request dependent",):
            description[spn_name] = "%s (%s)" % (get_spn_bytes(message_data, spn), spn_units)
        elif spn_units.upper() in ("ASCII",):
            description[spn_name] = "%s" % get_spn_bytes(message_data, spn).tobytes()

    return description


def get_bam_processor(process_bam_found):
    new_pgn = {}
    new_data = {}
    new_packets = {}
    new_length = {}

    def process_for_bams(message_bytes, message_id, sa, timestamp):
        if is_connection_management_message(message_id):
            if is_bam_cts_message(message_bytes):  # BAM,CTS
                new_pgn[sa] = (message_bytes[7] << 16) + (message_bytes[6] << 8) + message_bytes[5]
                new_length[sa] = (message_bytes[2] << 8) + message_bytes[1]
                new_packets[sa] = message_bytes[3]
                new_data[sa] = [0xFF for i in range(7 * new_packets[sa])]

        elif is_data_transfer_message(message_id):
            # print("{:08X}".format(message_id) + "".join(" {:02X}".format(d) for d in message))
            if sa in new_data.keys():
                for b, i in zip(message_bytes[1:], range(7)):
                    try:
                        new_data[sa][i + 7 * (message_bytes[0] - 1)] = b
                    except Exception as e:
                        print (e)
                if message_bytes[0] == new_packets[sa]:
                    data_bytes = bytes(new_data[sa][0:new_length[sa]])
                    process_bam_found(data_bytes, sa, new_pgn[sa], timestamp)

    return process_for_bams
