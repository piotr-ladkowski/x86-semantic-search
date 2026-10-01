/* Driver for the Linux example functions (regs.asm, sysv.asm, frame.asm, partial.asm). */
#include <stdio.h>
#include <string.h>
unsigned long shl_by(unsigned long, unsigned long);
void fill_bytes(void *, int, unsigned long);
void copy_bytes(void *, const void *, unsigned long);
unsigned long mulhi(unsigned long, unsigned long);
void divmod(long, long, long *, long *);
void cpu_vendor(char *);
long sum_array(const long *, long);
long add3(long, long, long);
long sum7(long, long, long, long, long, long, long);
long keep_rbx(long);
void say_answer(void);
long frame_demo(long);
void copy_qwords(void *, const void *, unsigned long);
void copy_backward(void *, const void *, unsigned long);
unsigned long my_strlen(const char *);
int mem_equal(const void *, const void *, unsigned long);
void partial_demo(unsigned long out[3]);

int main(void) {
    char buf[8] = "XXXXXXX", dst[8] = {0}, v[13];
    long a[] = {1, 2, 3, 4}, q, r;
    unsigned long p[3];
    fill_bytes(buf, 'a', 4);
    copy_bytes(dst, "hello", 6);
    divmod(-7, 2, &q, &r);
    cpu_vendor(v);
    partial_demo(p);
    printf("shl_by(3,4)=%lu fill=%s copy=%s mulhi=%lu divmod=%ld,%ld sum_array=%ld vendor_len=%zu\n",
           shl_by(3, 4), buf, dst, mulhi(~0UL, 2), q, r, sum_array(a, 4), strlen(v));
    printf("add3=%ld sum7=%ld keep_rbx=%ld frame_demo=%ld\n", add3(1, 2, 3),
           sum7(1, 2, 3, 4, 5, 6, 7), keep_rbx(9), frame_demo(1234));
    printf("partial: %016lx %016lx %016lx\n", p[0], p[1], p[2]);
    {
        char fwd[7] = "abcdef", back[7] = "abcdef";
        unsigned long qs[3] = {1, 2, 3}, qd[3] = {0, 0, 0};
        copy_bytes(fwd + 2, fwd, 4);
        copy_backward(back + 2, back, 4);
        copy_qwords(qd, qs, 3);
        printf("strings: strlen=%lu,%lu equal=%d,%d,%d overlap_fwd=%s overlap_back=%s qwords=%lu%lu%lu\n",
               my_strlen("hello"), my_strlen(""), mem_equal("abc", "abc", 3), mem_equal("abc", "abd", 3),
               mem_equal("abc", "abd", 0), fwd, back, qd[0], qd[1], qd[2]);
    }
    say_answer();
    fflush(stdout);
    return 0;
}
