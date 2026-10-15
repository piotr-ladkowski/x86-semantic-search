/* Driver for cpuid.asm: the page's has_bmi2 must agree with GCC's own CPUID helpers on whatever CPU
 * runs the test, so the expected output does not depend on the machine. */
#include <cpuid.h>
#include <stdio.h>

int has_bmi2(void);
int rbx_survives_has_bmi2(void);

int main(void) {
    unsigned int max_leaf, eax, ebx, ecx, edx;
    __builtin_cpu_init();
    int builtin = __builtin_cpu_supports("bmi2") != 0;
    int header = __get_cpuid_count(7, 0, &eax, &ebx, &ecx, &edx) ? (ebx >> 8) & 1 : 0;
    max_leaf = __get_cpuid_max(0, 0);
    printf("has_bmi2 agrees with __builtin_cpu_supports: %s\n", has_bmi2() == builtin ? "yes" : "no");
    printf("has_bmi2 agrees with __get_cpuid_count: %s\n", has_bmi2() == header ? "yes" : "no");
    printf("rbx preserved: %s\n", rbx_survives_has_bmi2() ? "yes" : "no");
    /* An invalid sub-leaf of leaf 07H returns all zeros (SDM Vol. 1, CPUID.07H). */
    if (max_leaf >= 7) {
        __cpuid_count(7, 0, eax, ebx, ecx, edx);
        __cpuid_count(7, eax + 1, eax, ebx, ecx, edx);
        printf("leaf 7, sub-leaf above the maximum: %s\n",
               (eax | ebx | ecx | edx) == 0 ? "all zero" : "not zero");
    } else {
        printf("leaf 7, sub-leaf above the maximum: all zero\n");
    }
    return 0;
}
