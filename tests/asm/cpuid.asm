; cpuid.asm - the example from the CPUID page (System V AMD64, Linux)
default rel
global has_bmi2, rbx_survives_has_bmi2

section .text

has_bmi2:                       ; int has_bmi2(void): 1 if this CPU has BMI2, else 0
        push    rbx             ; cpuid overwrites rbx, which the caller expects preserved
        xor     eax, eax        ; leaf 0
        cpuid                   ; eax = highest basic leaf
        mov     r8d, eax
        xor     eax, eax        ; answer 0 ...
        cmp     r8d, 7
        jb      .done           ; ... if leaf 7 does not exist
        mov     eax, 7          ; leaf 7
        xor     ecx, ecx        ; sub-leaf 0: cpuid reads ecx for this leaf
        cpuid
        mov     eax, ebx
        shr     eax, 8
        and     eax, 1          ; eax = bit 8 of ebx (BMI2)
.done:  pop     rbx
        ret

rbx_survives_has_bmi2:          ; int rbx_survives_has_bmi2(void): 1 if has_bmi2 kept rbx intact
        push    rbx
        mov     rbx, 0x1122334455667788
        call    has_bmi2
        mov     rax, 0x1122334455667788
        cmp     rbx, rax
        sete    al
        movzx   eax, al
        pop     rbx
        ret

section .note.GNU-stack noalloc noexec nowrite progbits
