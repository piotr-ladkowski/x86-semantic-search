#include <stdio.h>
long long add3(long long, long long, long long);
long long sum5(long long, long long, long long, long long, long long);
long long keep_rsi(long long);
void say_answer(void);
int main(void) {
    printf("add3=%lld sum5=%lld keep_rsi=%lld\n", add3(1, 2, 3), sum5(1, 2, 3, 4, 5), keep_rsi(9));
    say_answer(); fflush(stdout); return 0;
}
