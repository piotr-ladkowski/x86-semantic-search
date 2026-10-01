; regs.asm - tiny functions showing registers with built-in jobs (System V AMD64, Linux)
default rel
global shl_by, fill_bytes, copy_bytes, copy_qwords, copy_backward, my_strlen, mem_equal
global mulhi, divmod, cpu_vendor, sum_array

section .text

shl_by:                         ; unsigned long shl_by(unsigned long x, unsigned long n)
        mov     rax, rdi        ; x
        mov     ecx, esi        ; a variable shift count must be in CL
        shl     rax, cl
        ret

fill_bytes:                     ; void fill_bytes(void *dst, int byte, size_t n)
        mov     rcx, rdx        ; rep uses rcx as its repeat count
        mov     eax, esi        ; stosb stores AL
        rep stosb               ; repeat rcx times: [rdi] = al, rdi += 1
        ret

copy_bytes:                     ; void copy_bytes(void *dst, const void *src, size_t n)
        mov     rcx, rdx        ; count
        rep movsb               ; repeat rcx times: [rdi] = [rsi], rsi += 1, rdi += 1
        ret

copy_qwords:                    ; void copy_qwords(void *dst, const void *src, size_t n_qwords)
        mov     rcx, rdx        ; the count is in qwords, not bytes
        rep movsq               ; repeat rcx times: [rdi] = [rsi] (8 bytes), rsi += 8, rdi += 8
        ret

copy_backward:                  ; void copy_backward(void *dst, const void *src, size_t n)
        lea     rsi, [rsi + rdx - 1]    ; start at the LAST byte of the source ...
        lea     rdi, [rdi + rdx - 1]    ; ... and of the destination
        mov     rcx, rdx
        std                     ; DF = 1: the pointers move down
        rep movsb
        cld                     ; put DF back to 0 (the System V ABI requires it clear on return)
        ret

my_strlen:                      ; size_t my_strlen(const char *s)
        mov     rdx, rdi        ; remember where the string starts
        xor     eax, eax        ; scas compares with AL: look for the zero byte
        mov     rcx, -1         ; "no limit" on the count
        repne scasb             ; repeat while [rdi] != al, advancing rdi
        lea     rax, [rdi - 1]  ; rdi is one past the zero byte
        sub     rax, rdx        ; length = end - start
        ret

mem_equal:                      ; int mem_equal(const void *a, const void *b, size_t n)
        mov     rcx, rdx
        mov     eax, 1          ; an empty comparison counts as equal
        jrcxz   .done           ; n == 0: repe would run zero times and leave the flags untouched
        repe cmpsb              ; compare [rsi] with [rdi] until a byte differs or rcx reaches 0
        sete    al              ; ZF = 1 only if the last pair compared was equal
        movzx   eax, al
.done:  ret

mulhi:                          ; unsigned long mulhi(unsigned long a, unsigned long b)
        mov     rax, rdi        ; mul's implicit multiplicand is rax
        mul     rsi             ; rdx:rax = rax * rsi
        mov     rax, rdx        ; return the high 64 bits
        ret

divmod:                         ; void divmod(long a, long b, long *quot, long *rem)
        mov     r8, rdx         ; idiv overwrites rdx, so park the 'quot' pointer in r8
        mov     rax, rdi        ; dividend
        cqo                     ; rdx:rax = rax sign-extended
        idiv    rsi             ; rax = quotient, rdx = remainder
        mov     [r8], rax
        mov     [rcx], rdx
        ret

cpu_vendor:                     ; void cpu_vendor(char out[13])
        push    rbx             ; cpuid overwrites rbx, which the caller expects preserved
        xor     eax, eax        ; leaf 0: vendor string
        cpuid                   ; the 12 characters come back in ebx, edx, ecx (in that order)
        mov     [rdi], ebx
        mov     [rdi + 4], edx
        mov     [rdi + 8], ecx
        mov     byte [rdi + 12], 0
        pop     rbx
        ret

sum_array:                      ; long sum_array(const long *p, long n)
        xor     eax, eax        ; total = 0
        test    rsi, rsi
        jz      .done           ; n == 0: nothing to add
.next:  add     rax, [rdi]
        add     rdi, 8
        dec     rsi
        jnz     .next
.done:  ret

section .note.GNU-stack noalloc noexec nowrite progbits
