#define _GNU_SOURCE
/* Provoke each CPU exception in exceptions.asm in a child process and print what Linux delivers. */
#include <signal.h>
#include <ucontext.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/wait.h>
#include <unistd.h>

void ex_ud2(void), ex_lock_reg(void), ex_old_opcode(void), ex_into(void), ex_div0(void);
void ex_div_overflow(void), ex_idiv_min(void), ex_int3(void), ex_int_vector(void), ex_null_read(void);
void ex_readonly_write(void *), ex_noncanonical(void), ex_misaligned_sse(void), ex_hlt(void);
void ex_cli(void), ex_in(void), ex_call_null(void), ex_stack_noncanonical(void);
void ex_alignment_check(void);

static const char *sig_name(int s) {
    switch (s) {
    case SIGILL: return "SIGILL"; case SIGFPE: return "SIGFPE"; case SIGSEGV: return "SIGSEGV";
    case SIGBUS: return "SIGBUS"; case SIGTRAP: return "SIGTRAP"; default: return "?";
    }
}
static const char *code_name(int sig, int c) {
    if (c == SI_KERNEL) return "SI_KERNEL";
    switch (sig) {
    case SIGILL: return c == ILL_ILLOPN ? "ILL_ILLOPN" : c == ILL_ILLOPC ? "ILL_ILLOPC" : "ILL_other";
    case SIGFPE: return c == FPE_INTDIV ? "FPE_INTDIV" : c == FPE_INTOVF ? "FPE_INTOVF" : "FPE_other";
    case SIGSEGV: return c == SEGV_MAPERR ? "SEGV_MAPERR" : c == SEGV_ACCERR ? "SEGV_ACCERR" : "SEGV_other";
    case SIGBUS: return c == BUS_ADRALN ? "BUS_ADRALN" : "BUS_other";
    case SIGTRAP: return c == TRAP_BRKPT ? "TRAP_BRKPT" : "TRAP_other";
    }
    return "?";
}

static const char *current;
static void handler(int sig, siginfo_t *si, void *ctx) {
    ucontext_t *uc = ctx;
    /* the CPU's own account of the event: its vector number and the error code it pushed */
    long long vector = uc->uc_mcontext.gregs[REG_TRAPNO], err = uc->uc_mcontext.gregs[REG_ERR];
    char out[200];
    int n = snprintf(out, sizeof out, "%-22s vector=%-2lld err=%#-5llx %s %s addr=%s\n", current,
                     vector, err, sig_name(sig), code_name(sig, si->si_code),
                     si->si_code == SI_KERNEL ? "-" : si->si_addr == NULL ? "0" : "nonzero");
    write(1, out, n);
    _exit(0);
}

static void run(const char *name, void (*fn)(void), void *arg) {
    fflush(stdout);
    pid_t pid = fork();
    if (pid == 0) {
        static char stack[65536];
        stack_t ss = {.ss_sp = stack, .ss_size = sizeof stack};
        sigaltstack(&ss, NULL); /* so even a broken rsp can run the handler */
        struct sigaction sa = {.sa_sigaction = handler, .sa_flags = SA_SIGINFO | SA_ONSTACK};
        sigemptyset(&sa.sa_mask);
        for (int s = 1; s < 32; s++) if (s != SIGKILL && s != SIGSTOP) sigaction(s, &sa, NULL);
        current = name;
        if (arg) {
            (void)*(volatile char *)arg; /* touch it first: now the page is present, so a write is a protection fault */
            ((void (*)(void *))fn)(arg);
        } else {
            fn();
        }
        printf("%-22s returned normally\n", name);
        fflush(stdout);
        _exit(0);
    }
    int st;
    waitpid(pid, &st, 0);
}

/* With no handler installed the signal ends the process: report which signal did it. */
static void run_default(const char *name, void (*fn)(void)) {
    fflush(stdout);
    pid_t pid = fork();
    if (pid == 0) {
        fn();
        _exit(0);
    }
    int st;
    waitpid(pid, &st, 0);
    if (WIFSIGNALED(st)) printf("%-22s default action: killed by %s\n", name, sig_name(WTERMSIG(st)));
    else printf("%-22s default action: exited normally\n", name);
}

int main(void) {
    void *ro = mmap(NULL, 4096, PROT_READ, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    run("ud2", ex_ud2, NULL);
    run("lock add eax, ebx", ex_lock_reg, NULL);
    run("db 0x27 (old DAA)", ex_old_opcode, NULL);
    run("db 0xCE (INTO)", ex_into, NULL);
    run("div by zero", ex_div0, NULL);
    run("div quotient too big", ex_div_overflow, NULL);
    run("idiv INT64_MIN / -1", ex_idiv_min, NULL);
    run("int3", ex_int3, NULL);
    run("int 0x21", ex_int_vector, NULL);
    run("read [0]", ex_null_read, NULL);
    run("write read-only page", (void (*)(void))ex_readonly_write, ro);
    run("non-canonical read", ex_noncanonical, NULL);
    run("movaps misaligned", ex_misaligned_sse, NULL);
    run("hlt", ex_hlt, NULL);
    run("cli", ex_cli, NULL);
    run("in al, dx", ex_in, NULL);
    run("call 0", ex_call_null, NULL);
    run("push, bad rsp", ex_stack_noncanonical, NULL);
    run("unaligned with AC set", ex_alignment_check, NULL);
    run_default("ud2 (no handler)", ex_ud2);
    run_default("read [0] (no handler)", ex_null_read);
    return 0;
}
