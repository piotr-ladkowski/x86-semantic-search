#!/bin/sh
# Runs INSIDE the toolchain container (see `make verify-asm`). Builds every example program from the
# articles, runs it, and compares the output with the expected text. Windows builds run under Wine.
cp -r /work /tmp/build && cd /tmp/build || exit 2
fail=0
check() {  # check <name> <expected> <actual>
    if [ "$2" = "$3" ]; then echo "ok    $1"; else echo "FAIL  $1"; echo "   expected: $2"; echo "   actual:   $3"; fail=1; fi
}

# ---- Linux -----------------------------------------------------------------------------------
nasm -f elf64 hello.asm -o hello.o && ld hello.o -o hello
out=$(./hello); check "linux hello (no libc) output" "Hello, doc/x86!" "$out"
./hello >/dev/null; check "linux hello (no libc) exit status" 0 $?

nasm -f elf64 hello_libc.asm -o hello_libc.o
log=$(gcc hello_libc.o -o hello_libc 2>&1); check "linux hello_libc link has no warnings" "" "$log"
out=$(./hello_libc); check "linux hello_libc output" "Hello from libc" "$out"
gcc -no-pie hello_libc.o -o hello_libc_nopie 2>/dev/null
out=$(./hello_libc_nopie); check "linux hello_libc -no-pie output" "Hello from libc" "$out"

for f in regs sysv frame partial; do nasm -f elf64 $f.asm -o $f.o || fail=1; done
gcc -O1 test_linux.c regs.o sysv.o frame.o partial.o -o test_linux
check "linux register/ABI functions" "$(cat expected_linux.txt)" "$(./test_linux)"

# ---- CPU exceptions as Linux reports them (docs: the "CPU exceptions" article) -----------------------
nasm -f elf64 exceptions.asm -o exceptions.o && gcc -O1 test_exceptions.c exceptions.o -o test_exceptions
check "linux: CPU exceptions arrive as these signals" "$(cat expected_exceptions.txt)" "$(./test_exceptions 2>&1)"

# ---- statements the NASM-on-Linux article makes about tools and mistakes ----------------------------
contains() {  # contains <name> <needle> <haystack>
    case "$3" in *"$2"*) echo "ok    $1" ;; *) echo "FAIL  $1"; echo "   expected to contain: $2"; echo "   actual:   $3"; fail=1 ;; esac
}
contains "toolchain: NASM version the article quotes" "2.16.01" "$(nasm -v)"
contains "toolchain: ld version the article quotes" "2.40" "$(ld --version | head -1)"
contains "toolchain: GCC version the article quotes" "12.2" "$(gcc --version | head -1)"

sed '/^section .note.GNU-stack/d' hello_libc.asm > nostack_libc.asm && nasm -f elf64 nostack_libc.asm -o nostack_libc.o
contains "linux: gcc warns when .note.GNU-stack is missing" \
    "missing .note.GNU-stack section implies executable stack" "$(gcc nostack_libc.o -o nostack_libc 2>&1)"
sed '/^section .note.GNU-stack/d' hello.asm > nostack.asm && nasm -f elf64 nostack.asm -o nostack.o
check "linux: plain ld prints no warning for a _start program without the note" "" "$(ld nostack.o -o nostack 2>&1)"

contains "linux: the gcc warning also says the behaviour is deprecated" \
    "NOTE: This behaviour is deprecated" "$(gcc nostack_libc.o -o nostack_libc 2>&1)"
sed 's/^        xor     eax, eax .*/        mov     eax, 7/' hello_libc.asm > ret7.asm && nasm -f elf64 ret7.asm -o ret7.o && gcc ret7.o -o ret7
./ret7 >/dev/null; check "linux: the value main returns becomes the exit status" 7 $?

printf 'bits 64\nmov ah, sil\n' > highbyte.asm
contains "nasm rejects mixing a high-byte register with a REX-only register" \
    "cannot use high byte register in rex instruction" "$(nasm -f elf64 highbyte.asm -o highbyte.o 2>&1)"

sed 's/^global _start//' hello.asm > noglobal.asm && nasm -f elf64 noglobal.asm -o noglobal.o
contains "linux: ld warns when global _start is missing" \
    "cannot find entry symbol _start; defaulting to" "$(ld noglobal.o -o noglobal 2>&1)"

printf 'global _start\nsection .text\n_start:\n        ret\nsection .note.GNU-stack noalloc noexec nowrite progbits\n' > retstart.asm
nasm -f elf64 retstart.asm -o retstart.o && ld retstart.o -o retstart
./retstart 2>/dev/null; check "linux: ret from _start crashes with SIGSEGV (status 139)" 139 $?

nasm -f elf64 hello.asm -o hello_l.o -l hello.lst
contains "linux: the listing shows B8 01 00 00 00 for mov eax, 1" "B801000000" "$(cat hello.lst)"
contains "linux: objdump shows the rip-relative lea" "lea    rsi,[rip+0x" "$(objdump -d -M intel hello)"
nasm -f elf64 -g -F dwarf hello.asm -o hello_g.o
contains "linux: -g -F dwarf adds debug sections" ".debug_info" "$(readelf -S hello_g.o)"

# ---- Windows (cross-built with MinGW-w64, run under Wine) --------------------------------------
export WINEDEBUG=-all WINEDLLOVERRIDES="mscoree,mshtml=" WINEPREFIX=/tmp/wineprefix
wine=/usr/lib/wine/wine64
nasm -f win64 hello_win.asm -o hello_win.obj && x86_64-w64-mingw32-gcc hello_win.obj -o hello_win.exe
out=$($wine ./hello_win.exe 2>/dev/null | tr -d '\r'); check "windows hello (C runtime) output" "Hello from Windows" "$out"

nasm -f win64 hello_win32.asm -o hello_win32.obj &&
  x86_64-w64-mingw32-gcc -nostdlib -o hello_win32.exe hello_win32.obj -lkernel32 -Wl,-e,start -Wl,--subsystem,console
out=$($wine ./hello_win32.exe 2>/dev/null | tr -d '\r'); check "windows hello (Win32 only) output" "Hello, Win32" "$out"

nasm -f win64 win64.asm -o win64.obj && x86_64-w64-mingw32-gcc -O1 test_win64.c win64.obj -o test_win64.exe
out=$($wine ./test_win64.exe 2>/dev/null | tr -d '\r'); check "windows ABI functions" "$(cat expected_windows.txt)" "$out"

[ $fail -eq 0 ] && echo "ALL EXAMPLES VERIFIED" || echo "SOME EXAMPLES FAILED"
exit $fail
