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
