#!/usr/bin/python
"""
Author:  Nathan Crapo
Date:    09-14-2011


Overview
========

The Emutec 'pjet' command has exhibited a lot of I/O problems.  It often hangs
on different image sizes.  Finding a usable file size is time consuming and
error prone.  Since the Promjet HW often locks up and requires a hard reset when
this happens, these bugs can burn a lot of development time.

Using an image that matches the size of the Promjet emulated memory works the
best.

'pjet' program arguments are awkward and cryptic.  This script converts human
readable arguments in 'Unix' format to pjet syntax so it's easier to use.

This script also allows the user to set commonly used settings in environment
variables so they don't have to be specified each time.

PJET_WIDTH={width}
PJET_SIZE={size}
PJET_SWAP={0/1}

Autodetection finds the 'right' settings, saves time, and makes the tool easy to
use.


Autodetection
=============

Bus width can be autodetected by comparing file names and data against known
platforms.

Device size can be set by inspecting input file size.  The smallest possible
setting is selected with autodetection.

Disable autodetection using manual mode to ensure explicit control of all
variables.

Autodetection will not be used for settings specified on the command line or
with environment variables.


Input File
==========

An input file must be specified as the single non-switch argument to the script.
Data can also be taken from stdin by using '-' as the file name.

Using stdin is useful for piping data from other commands, network pipes, etc.
Note that file name autodetection will not work in this case.


Carefully Control Settings
==========================

Settings are used in the following order of importance:
1)  User switches on the command line
2)  Environment variables
3)  Autodetection (or use manual mode to disable this)

The command will not complete without critical switches and will interact with
the user to set them.

Do a dry run with the -n (--fake) switch for times when you're paranoid.


Example Usage
=============

Use autodetection to set parameters and burn the u-boot image.  No switches
required - works 100%.

    prompt% burn.py u-boot-octeon_maple.bin


Write the maple u-boot to the second Promjet in the system.  The device number
correlates to the order of the lsusb command.  Autodetection sets other
pertinent parameters.

    prompt% burn.py -d 2 u-boot-octeon_mahogany.bin


Send an image over the network to a remote system with a Promjet via ssh.  Uses
stdin on the remote side to read the image in the burn.py script.  Also note
explicit control of width and swap settings.  Autodetection could have been used
for those two things instead.  Environment variable use is often difficult when
working with remote hosts.


    prompt% cat u-boot-octeon_maple.bin | ssh burn.py - -w16 -S


Another way to type the same command.  Argument order usually doesn't matter.
Arguments can be grouped with one '-' switch.  This is fairly standard Unix
stuff.

    prompt% cat u-boot-octeon_maple.bin | ssh burn.py - -Sw16


Use manual mode when you want to avoid autodetection.  Environment variables
still have effect if set, but will not over-write what you specify on the
command line.

    prompt% burn.py -m u-boot-octeon_not_maple.bin -s 512K -w16


If you want to see how the script will invoke pjet without actually calling it,
use the -n switch.  Added the verbose flag for as much info as possible.

    prompt% burn.py -nv u-boot-octeon_larch.bin



"""
import sys
import os
import re
import optparse



# Key: num memory locations, value: pjet command line arg.  Multiply the bus
# width (in bytes) by the number of locations to get total memory size.  For a
# 16b example: 1024K (mem locations) * 2 (B/location) = 2048KB.
DEVICE_SIZES = { '8K'   : 64,
                 '16K'  : 128,
                 '32K'  : 256,
                 '64K'  : 512,
                 '128K' : 10,
                 '256K' : 20,
                 '512K' : 40,
                 '1M'   : 80,
                 '2M'   : 160, # 16 also works
                 '4M'   : 320, # 32 also works
                 '8M'   : 640,
                 '16M'  : 1280,
                 '32M'  : 2560 }
DEVICE_WIDTHS = [ '1', '8', '16', '32', '64', '128' ]
IMAGE_TYPES =   { 'I' : 'Intel',
                  'B' : 'Binary',
                  'M' : 'Motorola' }
METRIC_SUFFIXES = { 'K' : 1024,
                    'M' : 1024 * 1024,
                    'G' : 1024 * 1024 * 1024 }
PJET_WIDTH_ENV_VAR = 'PJET_WIDTH'
PJET_SIZE_ENV_VAR = 'PJET_SIZE'
PJET_SWAP_ENV_VAR = 'PJET_SWAP'

class PlatformSpec():
    def __init__(self, name, width=8, swap=False, size=''):
        self.name = name
        self.width = width
        self.swap = swap
        self.size = size

PLATFORM_LIST = [ PlatformSpec('uboot-mvebu', width=1, size='16M'),
                  PlatformSpec('ash', width=8), PlatformSpec('balsa', width=8),
                  PlatformSpec('birch', width=8), PlatformSpec('fir', width=8),
                  PlatformSpec('beech', width=8), PlatformSpec('chestnut', width=8),
                  PlatformSpec('durian', width=8), PlatformSpec('ebony', width=8),
                  PlatformSpec('gombe', width=8), PlatformSpec('hemlock', width=8),
                  PlatformSpec('cherry', width=8), PlatformSpec('jarrah', width=8),
                  PlatformSpec('khaya', width=8), PlatformSpec('cedar', width=8),
		  PlatformSpec('greenheart',width=8),
                  PlatformSpec('hickory', width=8), PlatformSpec('karri', width=8),
                  PlatformSpec('camito', width=8), PlatformSpec('canarium', width=8),
                  PlatformSpec('iroko', width=16, swap=True), PlatformSpec('larch', width=16, swap=True),
                  PlatformSpec('maple', width=16, swap=True), PlatformSpec('medang', width=16, swap=True),
                  PlatformSpec('oak', width=8), PlatformSpec('poplar', width=8),
                  PlatformSpec('holly', width=16, swap=True),PlatformSpec('ayan', width=16, swap=True),
                  PlatformSpec('mahogany', width=16, swap=True), PlatformSpec('odoko', width=16, swap=True),
                  PlatformSpec('pacific', width=16, swap=True), PlatformSpec('alder', width=16, swap=True),
                  PlatformSpec('brazilwood', width=16, swap=True), 
                  PlatformSpec('okoume', width=16, swap=True), PlatformSpec('marblewood', width=16, swap=True),
                  PlatformSpec('ebb6600', width=16, swap=True), PlatformSpec('cn6600', width=16, swap=True),
                  PlatformSpec('thunder-bootfs-uboot-t81', width=1, size='16M')]



def main():
    """
    Wrap the pjet command to work around all its bugs with files of different
    sizes.  Also make passing arguments to it a little easier for humans.
    """
    device_size_descriptions = ", ".join(sorted_metric_device_sizes())
    widths = ", ".join(DEVICE_WIDTHS)
    image_types = ", ".join(['%s=%s' % (type_key, IMAGE_TYPES[type_key]) for type_key in IMAGE_TYPES.keys()])

    parser = optparse.OptionParser(usage="%prog {filename}", version="2.7")
    parser.add_option('-P', '--no_padding', dest='no_padding', action='store_true', help='Do not pad image. Useful to preserve content of the PJET)')
    parser.add_option('-S', '--swap', help='set swap on or off on xfer (on, off, 0, 1, yes, no, y, n)')
    parser.add_option('--enable-ice', action='store_true', help='Enable ICE feature')
    parser.add_option('-d', '--device', help='select device if multiple devices are present at one time')
    parser.add_option('-f', '--fill', default='0xFF', help='set fill byte value [default 0xFF]')
    parser.add_option('-s', '--size', help='set Promjet size [memory addresses] (%s)' % device_size_descriptions)
    parser.add_option('-w', '--width', help='Promjet bus width (%s)' % widths)
    parser.add_option('-t', '--type', default='B', help='Image type (%s) [default B]' % image_types)
    parser.add_option('-m', '--manual-mode', action='store_true', help='Manually set all parameters from the command line - no autodetection')
    parser.add_option('-n', dest='fake_run', action='store_true', help='Dont run pjet command - just print what would happen to stdout')
    parser.add_option('-v', '--verbose', action='store_true', help='Print verbose output')
    parser.add_option('--pjet-command', help='Specify pjet binary to run')


    # ----- Options -----
    (options, args) = parser.parse_args()

    if len(args) < 1:
        parser.error('incorrect number of arguments: need a file to work on')
    options.input_filename = args[0]

    # Need to read the input filename to do autodetection
    programmer_data = get_input_file_data(options.input_filename)

    error = basic_option_check(options)
    if error:
        parser.error('%s' % error) # app terminates

    # Options are specified three possible ways: on the command line, env vars,
    # and with autodetection.  Priority is given in the order listed.
    detect_env_options(options)
    if not options.manual_mode:
        autodetect_options(options, programmer_data)

    error = mandatory_option_check(options)
    if error:
        parser.error('%s' % error) # app terminates

    programmer_data_length = len(programmer_data)

    # ----- Act with pjet -----
    pjet_options = get_pjet_options(options, programmer_data_length) + " /dev/stdin"
    if not options.verbose:
        pjet_options += " > /dev/null"
    if options.pjet_command:
        command = "%s %s" % (options.pjet_command, pjet_options)
    else:
        command = "pjet %s" % pjet_options

    # Do this now so users can see warnings about the process if they're using
    # pjet or not
    if not options.no_padding:
        programmer_data = modify_data_for_programmer(options, programmer_data)


    # We may just want to print what would happen and stop
    if options.fake_run:
        print command
        sys.exit(0)

    if options.verbose:
        print command

    # Send data to the Promjet via the pjet command.  Work around all its bugs
    # and cryptic control.
    try:
        pjet_handle = os.popen(command, "w")
        pjet_handle.write(programmer_data)
        pjet_handle.close()
    except:
        sys.stderr.write("Could not write image to promjet\n")
        sys.exit(-1)



# --------------- Helpers ---------------

def sorted_device_size_lists():
    """
    Return sorted device size lists in byte and metric representation
    """
    # Create dict: key=bytes, value=size string (w/ metric suffix)
    devsize = {}
    for s in DEVICE_SIZES:
        devsize[number_with_metric_suffix_to_val(s)] = s

    byte_size_list = sorted(devsize)
    metric_size_list = [ devsize[s] for s in byte_size_list ]
    return byte_size_list, metric_size_list


def max_device_size():
    """
    Return the max device size as defined in DEVICE_SIZES.  Programmer only has
    to maintain one list and this follow.
    """
    byte_list, metric_list = sorted_device_size_lists()
    return metric_list[-1]


def sorted_metric_device_sizes():
    """
    Create list from DEVICE_SIZES key values (metric sizes), sort from smallest
    to largest and return.
    """
    byte_list, metric_list = sorted_device_size_lists()
    return metric_list


def get_input_file_data(filename):
    """
    Read a file or stdin into a string buffer and return it.  Limit host memory
    use to maximum promjet device size.
    """
    if filename == '-':
        filename = '/dev/stdin'

    handle = open(filename, "rb")
    # Limit host memory use, but allow trancations in later code
    max_buffer_len = number_with_metric_suffix_to_val(max_device_size()) + 1
    data = handle.read(max_buffer_len)
    handle.close()
    return data


def number_with_metric_suffix_to_val(number_str):
    """
    Take a string like 256K and convert it to a raw number using its metric
    suffix.

    Raise an exception for invalid input.
    """
    if len(number_str) < 1:
        raise ValueError, "Empty string cannot be converted to a number"
    metric_suffix = number_str[-1].upper()
    if metric_suffix.isalpha():
        number = int(number_str[:-1])
    if metric_suffix in METRIC_SUFFIXES.keys():
        number = number * METRIC_SUFFIXES[metric_suffix]
    elif metric_suffix:
        raise ValueError, "unknown suffix %s (%s)" % (metric_suffix,
                                  ", ".join(METRIC_SUFFIXES.keys()))
    return number


def device_spec_to_num_bytes(num_mem_locations, width):
    """
    Take a string like 256K and convert it to a number of memory locations
    (addresses).  Multiply by the number of bytes per location to determine the
    amount of memory in bytes.

    Raise an exception for invalid input.
    """
    # width 1 means SPI with data size 8
    calculated_width = int(width)
    if int(width) == 1:
        calculated_width = 8

    num_mem_locations = number_with_metric_suffix_to_val(num_mem_locations)
    num_bytes = num_mem_locations * (calculated_width / 8)
    return num_bytes


def pad_data_to_size(data, num_bytes, padding_byte):
    """
    Increase data buffer to specified number of bytes using the padding_byte.
    If the incoming data is larger than the device size already, just return
    what was passed in.
    """
    padding_len = num_bytes - len(data)
    if padding_len < 1:
        return data
    data_out = data + str(('%c' % padding_byte) * padding_len)
    return data_out


def get_pjet_options(options, data_length):
    """
    Take command line options that have _already_ been sanity checked and turn
    them into an option string for the pjet command.  Use environment variables
    or autodetection (in that order) to set device width and swapping unless
    instructed not to with --manual-mode.
    """
    hw_jumper_options = ""
    if not options.enable_ice:
        hw_jumper_options = hw_jumper_options + "N"
    if int(options.width) == 1:
        hw_jumper_options = hw_jumper_options + "P"

    hw_jumper_size = DEVICE_SIZES[options.size.upper()]

    fill_value = re.sub('^0x', '', options.fill).upper()

    geometry_options = ""
    try:
        if options.swap and strtobool(options.swap):
            geometry_options = geometry_options + "S"
    except ValueError as e:
        sys.stderr.write("Warning: can't understand swap setting: %s\n" % str(e))

    if options.width and int(options.width) != 1:
        geometry_width = options.width
        pjet_options = "I=%s%s T=%s W=%s%s" % (hw_jumper_options, hw_jumper_size, options.type, geometry_options, geometry_width)
    else:
        pjet_options = "I=%s%s T=%s" % (hw_jumper_options, hw_jumper_size, options.type)

    if not options.no_padding:
        pjet_options = pjet_options + (" F=%s" % fill_value)
    else:
        pjet_options = pjet_options + (" L=%X" % data_length)

    if options.device:
        pjet_options = pjet_options + (" X=%s" % options.device)

    return pjet_options


def basic_option_check(options):
    """
    Make sure user options look okay.  Return an error string indicating the
    problem if not.
    """
    if options.size and not options.size.upper() in DEVICE_SIZES:
        return "device size %s is invalid. (%s)" % (options.size.upper(), ", ".join(sorted_metric_device_sizes()))
    if options.width and not options.width in DEVICE_WIDTHS:
        return "device width %s is invalid (%s)" % (options.width, ", ".join(DEVICE_WIDTHS))
    device_num = 0
    if options.device:
        try:
            device_num = int(options.device)
        except ValueError:
            device_num = 0
        if device_num < 1:
            return "invalid device number %s.  Must be between 1 and n" % options.device
    return ""


def mandatory_option_check(options):
    """
    There are a few options that _must_ be set to run pjet
    """
    if not options.size:
        return "missing device size"
    if not options.width:
        return "missing device width"


def detect_env_options(options):
    """
    Some settings can be made with an ENV variable.  Command line switches from
    the user have priority.  Don't blindly overwrite.
    """
    if not options.width:
        env_width = os.getenv(PJET_WIDTH_ENV_VAR)
        if env_width and env_width in DEVICE_WIDTHS:
            options.width = env_width
            if options.verbose:
                print "Setting width to %s based on %s ENV variable" % (env_width, PJET_WIDTH_ENV_VAR)
        if env_width and not env_width in DEVICE_WIDTHS:
            sys.stderr.write("Warning: %s of %s not a supported setting (%s)\n" %
                             (PJET_WIDTH_ENV_VAR, env_width, ', '.join(DEVICE_WIDTHS)))

    # Width should go first since we need it here
    if not options.size:
        env_size = os.getenv(PJET_SIZE_ENV_VAR)
        if env_size and env_size in DEVICE_SIZES:
            options.size = env_size
            if options.verbose:
                print "Setting size to %s based on %s ENV variable" % (env_size, PJET_SIZE_ENV_VAR)
        if env_size and not env_size in DEVICE_SIZES:
            sys.stderr.write("Warning: %s of %s not a supported setting (%s)\n" %
                             (PJET_SIZE_ENV_VAR, env_size, ', '.join(sorted_metric_device_sizes())))

    if not options.swap:
        env_swap = os.getenv(PJET_SWAP_ENV_VAR)
        if env_swap:
            options.swap = env_swap
            if options.verbose:
                print "Swapping set to %s based on %s ENV variable" % (options.swap, PJET_SWAP_ENV_VAR)


def autodetect_find_platform(options, data):
    """
    Find platform spec by comparing filename and image data with platform name.
    """
    for platform in PLATFORM_LIST:
        binary_search = re.compile(b"SonicWALL,%s" % platform.name.capitalize())
        if binary_search.search(data):
            return platform

    for platform in PLATFORM_LIST:
        if os.path.basename(options.input_filename).lower().find(platform.name) >= 0:
            return platform

    return None


def autodetect_size(data_length, width):
    """
    Find the smallest device size that will completely contain data_length
    bytes.  If no device size will contain the data, return the largest device
    size.  Return value is human readable metric string: '1M' for example.
    """
    # width 1 means SPI with data size 8
    calculated_width = int(width)
    if int(width) == 1:
        calculated_width = 8
    # Mem size depends on bus width
    memory_size = int(data_length) / (calculated_width / 8)

    # Must compare smallest to largest
    device_bytes_smallest_to_largest, metric_sizes = sorted_device_size_lists()
    for s in device_bytes_smallest_to_largest:
        if s >= memory_size:
            i = device_bytes_smallest_to_largest.index(s)
            return metric_sizes[i]
    return max_device_size()


def autodetect_options(options, data):
    """
    Try to determine size, width, and swap setting from inputs.  Command line
    switches from the user have priority, so don't override options that already
    exist.
    """
    platform = autodetect_find_platform(options, data)
    if platform is None:
        return

    if options.verbose:
        print "Autodetction found platform:", platform.name

    if not options.width:
        options.width = platform.width
        if options.verbose:
            print "Autodetect width:", options.width

    if not options.swap:
        options.swap = str(platform.swap)
        if options.verbose:
            print "Autodetect swap:", options.swap

    if not options.size and platform.size:
        options.size = platform.size
        if options.verbose:
            print "Size from platform data:", platform.size

    # Need width or we can't autosize
    if not options.size and options.width:
        options.size = autodetect_size(len(data), options.width)
        if options.verbose:
            print "Autodetect device size:", options.size
    if not options.size and not options.width and options.verbose:
        sys.stderr.write("Warning: unable to autosize from input file because we don't have a bus width\n")


def modify_data_for_programmer(options, data):
    """
    Perform truncation if needed, and then pad to promjet buffer size.  The pjet
    command seems to have a much easier time reading files if the file is
    exactly the size as the memory it's emulating.
    """
    promjet_buffer_size = device_spec_to_num_bytes(options.size, options.width)
    if len(data) > promjet_buffer_size:
        sys.stderr.write("Warning: input file larger than device - truncating data to fit\n")
        # TODO - test truncation to make sure it works
        data = data[0:(promjet_buffer_size - 1)]

    pre_padded_len = len(data)
    data = pad_data_to_size(data, promjet_buffer_size, int(options.fill, 16))
    padding_len = len(data) - pre_padded_len

    if options.verbose and padding_len:
        print "Padding data with %d bytes of pattern %s." % (padding_len, options.fill)
    return data


def strtobool(str):
    """
    Convert a string to bool value.  Return Bool or raises an exception
    """
    TRUE_STRINGS = [ 'YES', 'Y', '1', 'ON', 'TRUE' ]
    FALSE_STRINGS = [ 'NO', 'N', '0', 'OFF', 'FALSE' ]
    if str.upper() in TRUE_STRINGS:
        return True
    elif str.upper() in FALSE_STRINGS:
        return False
    else:
        raise ValueError, "%s not one of (%s)" % (str.upper(), ', '.join(TRUE_STRINGS + FALSE_STRINGS))



if __name__ == "__main__":
    main()
