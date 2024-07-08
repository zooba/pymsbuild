import sys
import _winapi

def main():
    print("Invoked with an entry point")
    print("Executable:", sys.executable)
    print("Args:", sys.argv[1:])
    if sys.executable != sys.argv[0]:
        print("WARNING: executable does not match argv[0]")
    print("Prefix:", sys.prefix)
    print("sys.path:", *sys.path, sep="\n- ")
    print("DLL:", _winapi.GetModuleFileName(sys.dllhandle))

if __name__ == "__main__":
    print("Invoked directly")
    sys.exit(2)
