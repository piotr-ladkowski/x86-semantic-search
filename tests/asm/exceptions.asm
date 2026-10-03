; exceptions.asm - one tiny function per CPU exception a user-space program can provoke (Linux x86-64).
; Every function is called from test_exceptions.c in its own child process; none of them returns normally.
default rel
[warning -prefix-lock]       ; 'lock add eax, ebx' is wrong on purpose
global ex_ud2, ex_lock_reg, ex_old_opcode, ex_into, ex_div0, ex_div_overflow, ex_idiv_min
global ex_int3, ex_int_vector, ex_null_read, ex_readonly_write, ex_noncanonical, ex_misaligned_sse
global ex_hlt, ex_cli, ex_in, ex_call_null, ex_stack_noncanonical, ex_alignment_check

section .data
        align 16
buf:    times 32 db 0

section .text

ex_ud2:                         ; the instruction that exists only to raise #UD
        ud2

ex_lock_reg:                    ; LOCK with a register destination: #UD
        lock add eax, ebx

ex_old_opcode:                  ; 27h was DAA in 32-bit code; it is not an instruction in 64-bit mode
        db      0x27

ex_into:                        ; INTO cannot be used in 64-bit mode
        db      0xCE

ex_div0:                        ; #DE: divisor is zero
        mov     eax, 1
        xor     edx, edx
        xor     ecx, ecx
        div     ecx

ex_div_overflow:                ; #DE: the quotient does not fit in 64 bits (rdx >= divisor)
        mov     edx, 1
        xor     eax, eax
        mov     ecx, 1
        div     rcx

ex_idiv_min:                    ; #DE: the most negative number divided by -1
        mov     rax, 0x8000000000000000
        cqo
        mov     rcx, -1
        idiv    rcx

ex_int3:                        ; #BP: a debugger's breakpoint
        int3

ex_int_vector:                  ; INT n for a vector whose gate user code may not call: #GP
        int     0x21

ex_null_read:                   ; #PF: nothing is mapped at address 0
        xor     eax, eax
        mov     rax, [rax]

ex_readonly_write:              ; #PF: the page is mapped, but not writable (rdi = a read-only page)
        mov     byte [rdi], 1

ex_noncanonical:                ; #GP: bits 63:47 are not a copy of bit 47
        mov     rax, 0x8000000000000000
        mov     rax, [rax]

ex_misaligned_sse:              ; #GP: movaps needs a 16-byte aligned memory operand
        movaps  xmm0, [buf + 1]

ex_hlt:                         ; #GP: HLT needs privilege level 0
        hlt

ex_cli:                         ; #GP: CLI needs a privilege level at or below IOPL
        cli

ex_in:                          ; #GP: port I/O is privileged
        xor     edx, edx
        in      al, dx

ex_call_null:                   ; #PF: an instruction fetch from an unmapped address
        xor     eax, eax
        call    rax

ex_stack_noncanonical:          ; #SS: a stack access through a non-canonical rsp
        mov     rsp, 0x8000000000000000
        push    rax

ex_alignment_check:             ; #AC: only when EFLAGS.AC is set (and the OS enabled CR0.AM)
        pushfq
        or      qword [rsp], 0x40000
        popfq
        mov     eax, [buf + 1]
        ud2                     ; not reached if #AC fires

section .note.GNU-stack noalloc noexec nowrite progbits
