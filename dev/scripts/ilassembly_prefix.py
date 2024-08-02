#! python3
#pylint: disable=import-error,invalid-name,broad-except,superfluous-parens
#pylint: disable=global-statement
import sys
import errno
import subprocess
import os
import os.path as op
import codecs
import re

# pipenv dependencies
from docopt import docopt


__binname__ = op.splitext(op.basename(__file__))[0]  # grab script name
__version__ = '1.0'

class CMDArgs:
    """Data type to hold command line args"""
    def __init__(self, args):
        self.prefix = args['<prefix>']
        self.ilbins = args['<dll-file>']
        self.dasm = args['--dasm']
        self.nsfix = args['--nsfix']
        self.ilfix = args['--ilfix']
        self.resfix = args['--resfix']
        self.asm = args['--asm']
        self.rempk = args['--remove-pk']
        self.dotnetver = args['--dotnet-ver']
        self.ildasm_path = args['--ildasm-path']
        self.ilasm_path = args['--ilasm-path']
        self.debug = args['--debug']
        self.verbose = args['--verbose']

    def __repr__(self):
        return (f"CMDArgs(prefix={self.prefix}, ilbins={self.ilbins}, dasm={self.dasm}, "
                f"nsfix={self.nsfix}, ilfix={self.ilfix}, resfix={self.resfix}, asm={self.asm}, "
                f"rempk={self.rempk}, dotnetver={self.dotnetver}, ildasm_path={self.ildasm_path}, "
                f"ilasm_path={self.ilasm_path}, debug={self.debug}, verbose={self.verbose})")


# this tool tries to find the ildasm.exe and ilasm.exe
# but you can manually set their override paths here
ILDASM_EXE = None
# https://docs.microsoft.com/en-us/dotnet/framework/tools/ildasm-exe-il-disassembler
ILASM_EXE = None
# https://docs.microsoft.com/en-us/dotnet/framework/tools/ilasm-exe-il-assembler

# .net method to get their paths
# https://stackoverflow.com/a/28530783/2350244
ILDASM_ROOT = r"%PROGRAMFILES(X86)%\Microsoft SDKs\Windows"
ILASM_ROOT = r"C:\Windows\Microsoft.NET\Framework"

# tracking whether misc corrections have been applied to IL
# seems like the .net 4.8 ildasm has regressions
HAD_FIXES = False

def panic(msg, errcode=errno.EIO):
    """Panic, print message to stderr and exit"""
    print(msg, file=sys.stderr)
    sys.exit(errcode)

def find_ildasm_path():
    """Find full path of dotnet sdk binaries"""
    root = op.expandvars(ILDASM_ROOT)
    versions = []

    # Collect all version directories that match the pattern
    for ventry in os.listdir(root):
        if re.match(r"v\d+\.", ventry):
            versions.append(ventry)
    
    if not versions:
        panic("No suitable .NET SDK versions found in the specified root directory.")
    
    # Sort versions to find the latest one
    versions.sort(reverse=True)
    
    for version in versions:
        bin_dir = op.join(root, version, 'bin')
        if not op.exists(bin_dir):
            continue
        
        for netfxentry in os.listdir(bin_dir):
            if re.match(r"NETFX\s4\.7", netfxentry):
                ildasm_path = op.join(bin_dir, netfxentry, 'ildasm.exe')
                if op.exists(ildasm_path):
                    print(f"Using ildasm (.NET 4.7 SDK): {ildasm_path.lower()}")
                    return ildasm_path
            elif re.match(r"NETFX\s4\.8", netfxentry):
                panic(".NET 4.8 exists but seems to have regressions. Please install the .NET 4.7 SDK.")
    
    panic("Could not find ildasm.exe in any of the .NET SDK versions.")

def find_ilasm_path():
    """Find full path of dotnet sdk binaries"""
    root = op.expandvars(ILASM_ROOT)
    versions = []

    # Collect all version directories that match the pattern
    for ventry in os.listdir(root):
        if re.match(r"v4\.\d+", ventry):
            versions.append(ventry)
    
    if not versions:
        panic("No suitable .NET versions found in the specified root directory.")
    
    # Sort versions to find the latest one
    versions.sort(reverse=True)
    
    for version in versions:
        ilasm_path = op.join(root, version, 'ilasm.exe')
        if op.exists(ilasm_path):
            print(f"Using ilasm ({version.lower()}): {ilasm_path.lower()}")
            return ilasm_path
    
    panic("Could not find ilasm.exe in any of the .NET versions.")

def run_ilprocess(executable, args):
    """Run IL utility with given args"""
    # Combine the executable and arguments into a single list
    runargs = [executable] + args
    
    try:
        # Run the subprocess with the given arguments
        result = subprocess.run(runargs, capture_output=True, text=True)
        return result
    except FileNotFoundError:
        panic(f"Executable {executable} not found.")
    except subprocess.SubprocessError as e:
        panic(f"An error occurred while running the subprocess: {e}")

def ildasm(ns_prefix, il_binary):
    """Disassemble IL binary to .il file"""
    # Find the path to ildasm.exe
    ildasm_exe = find_ildasm_path() or ILDASM_EXE
    if not (ildasm_exe and op.exists(ildasm_exe)):
        panic("Cannot find ildasm")

    # Generate the output .il file name
    il_file_name = f"{ns_prefix}.{op.splitext(op.basename(il_binary))[0]}.il"
    il_file = op.join(op.dirname(il_binary), il_file_name)

    # Run the ildasm command to disassemble the IL binary
    res = run_ilprocess(ildasm_exe, [
        il_binary,
        '/NOBAR',
        '/TYPELIST',
        '/OUT={}'.format(il_file)
    ])

    # Check for errors in the disassembly process
    if res.returncode != 0:
        panic(f"Error disassembling {il_binary}", errcode=res.returncode)

    return il_file

def extract_namespaces(il_file):
    """Find namespaces listed in given IL file"""
    extern_ns_list = set()
    ns_list = set()
    record_ns = False

    with codecs.open(il_file, 'r', encoding='utf-8') as ilf:
        for illine in ilf:
            # Start recording namespaces
            if illine.startswith('.typelist'):
                record_ns = True
            # Stop recording namespaces
            elif illine.startswith('}'):
                record_ns = False

            # Record namespaces if currently recording
            if record_ns:
                tokens = illine.strip().split('.')
                if tokens and tokens[0].isalnum():
                    ns_list.add(tokens[0])

            # Grab external namespaces
            ext_ns_m = re.match(r'.assembly extern\s(.+)$', illine)
            if ext_ns_m:
                extern_ns_list.add(ext_ns_m.group(1))

            # Stop processing once .module is encountered
            if illine.startswith('.module'):
                break

    # Return the set of namespaces excluding the external ones
    return ns_list - extern_ns_list

def fix_resfiles(cwd, nsdict):
    """Fix name of extracted resource files based on given namespace rename dict"""
    for entry in os.listdir(cwd):
        entry_path = op.join(cwd, entry)
        if not op.isfile(entry_path):
            continue  # Skip if the entry is not a file

        for cur_ns, new_ns in nsdict.items():
            if entry.startswith(cur_ns) and not entry.endswith('.dll'):
                new_entry_name = entry.replace(cur_ns, new_ns)
                new_entry_path = op.join(cwd, new_entry_name)

                try:
                    os.rename(entry_path, new_entry_path)
                    print(f"Renamed {entry_path} to {new_entry_path}")
                except Exception as e:
                    print(f"Error renaming {entry_path} to {new_entry_path}: {e}")

# FIXME: https://developercommunity.visualstudio.com/solutions/806165/view.html
IL_FIXES = {
    r"ldc\.r4(\s+)inf": r"ldc.r4\g<1>(00 00 80 7F)",
    r"ldc\.r4(\s+)-inf": r"ldc.r4\g<1>(00 00 80 FF)",
    r"ldc\.r8(\s+)inf": r"ldc.r8\g<1>(00 00 00 00 00 00 F0 7F)",
    r"ldc\.r8(\s+)-inf": r"ldc.r8\g<1>(00 00 00 00 00 00 F0 FF)",
}

def apply_il_fixes(il_line):
    """Apply misc IL corrections"""
    global HAD_FIXES
    original_line = il_line  # Store the original line to compare later

    # Handle known issue with .NET 4.8
    if il_line.startswith('.custom (UNKNOWN_OWNER)'):
        HAD_FIXES = True
        return il_line, -1

    # Apply each IL fix pattern and its replacement
    for kpat, krepl in IL_FIXES.items():
        il_line = re.sub(kpat, krepl, il_line)

    # Check if any replacements were made
    if il_line != original_line:
        HAD_FIXES = True

    return il_line, 0

def fixns(il_file, ns_prefix):
    """Fixed the namespaces in given .il file"""
    illines = []
    cur_ns_list = extract_namespaces(il_file)
    nsdict = {x: '%s.%s' % (ns_prefix, x) for x in cur_ns_list}

    if cur_ns_list:
        skipping_pk = False
        with codecs.open(il_file, 'r', encoding='utf-8') as ilf:
            for illine in ilf.readlines():
                # Discard public key start
                if '.publickey =' in illine:
                    skipping_pk = True
                    continue
                elif skipping_pk and '.hash algorithm' in illine:
                    skipping_pk = False
                    continue
                if skipping_pk:
                    continue
                # Discard public key end

                # Apply IL fixes
                edited_line, err = apply_il_fixes(illine)
                if err == 0:
                    # Replace namespaces
                    for cur_ns, new_ns in nsdict.items():
                        edited_line = re.sub(
                            r"([\s:(])%s" % cur_ns,
                            r"\g<1>%s" % new_ns,
                            edited_line
                        )
                illines.append(edited_line)

        with codecs.open(il_file, 'w', encoding='utf-8') as ilf:
            ilf.writelines(illines)

    if HAD_FIXES:
        print("IL fixes have been applied")

    return nsdict

def ilasm(il_file):
    """Assemble IL binary from .il file"""
    ilasm_exe = find_ilasm_path() or ILDASM_EXE
    if not (ilasm_exe and op.exists(ilasm_exe)):
        panic("Can not find ilasm")
    il_name = op.splitext(op.basename(il_file))[0]
    cwd = op.dirname(il_file)
    new_il_binary_name = il_name + '.dll'
    new_il_binary = op.join(cwd, new_il_binary_name)
    ilasm_args = [
        '%s' % il_file,
        '/DLL',
        '/OUTPUT=%s' % new_il_binary,
    ]

    # Include the .res file if it exists
    il_res = op.join(cwd, il_name + '.res')
    if op.exists(il_res):
        ilasm_args.append('/RESOURCE="%s"' % il_res)

    res = run_ilprocess(ilasm_exe, ilasm_args)
    if res.returncode != 0 or 'Operation completed successfully' not in str(res.stdout):
        panic("Error assembling %s" % il_file, errcode=res.returncode)
    return new_il_binary

def cleanup(cwd, ns_prefix):
    """Cleanup temp files around given new IL binary"""
    # Define a list of known temporary file extensions
    temp_extensions = ['.il', '.res', '.pdb']
    
    for entry in os.listdir(cwd):
        entry_path = op.join(cwd, entry)
        
        # Check if the entry is a temporary file generated during the process
        if entry.startswith(ns_prefix) and op.isfile(entry_path):
            # Check for known temporary file extensions
            if any(entry.endswith(ext) for ext in temp_extensions):
                print("cleaning %s" % entry_path)
                os.remove(entry_path)

def ilpfxns(ns_prefix, il_binary):
    """Orchestrate prefixing namespace"""
    cwd = op.dirname(il_binary)  # Get the current working directory
    il_file = ildasm(ns_prefix, il_binary)  # Disassemble the IL binary

    # Fix namespaces
    fixedns_dict = fixns(il_file, ns_prefix)
    # Fix resource file names to include the prefix
    fix_resfiles(cwd, fixedns_dict)

    # Reassemble the IL binary
    new_il_binary = ilasm(il_file)

    # Remove temporary files
    cleanup(cwd, ns_prefix)
    
    return new_il_binary

def print_help():
    """Print help"""
    print(__doc__)
    sys.exit(errno.EINVAL)

if __name__ == "__main__":
    doc = """
    Usage:
        {cliname} <prefix> [options] <dll-file>...

    Options:
        --dasm              Only perform disassembly
        --nsfix             Only perform namespace changes (expects .il file)
        --ilfix             Only perform IL fixes (expects .il file)
        --resfix            Only perform res file changes (expects .res file)
        --asm               Only perform assembly (expects .il and .res files)
        --remove-pk         Only perform removing public key (expects .il file)
        --dotnet-ver=VER    Use this dotnet version sdk (default=4.7)
        --ildasm-path=PATH  Path to ildasm.exe
        --ilasm-path=PATH   Path to ilasm.exe
        --debug             Print debug messages
        --verbose           Print reports from ildasm and ilasm
        -h, --help          Show this help
        -v, --version       Show version

    """.format(cliname=__binname__)

    args = docopt(doc, version=__version__)
    cmdargs = CMDArgs(args)

    if cmdargs.debug:
        print(cmdargs)  # Print the arguments if in debug mode

    for targetdll in cmdargs.ilbins:
        print("\033[1m==> fixing %s\033[0m" % op.basename(targetdll))
        print(f"applying \"{cmdargs.prefix}\" prefix to IL namespaces")
        newdll = ilpfxns(cmdargs.prefix, targetdll)
        print(f"successfully generated new IL binary: {newdll.lower()}")